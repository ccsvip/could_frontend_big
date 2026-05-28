from __future__ import annotations

import inspect
import mimetypes
import os
import pkgutil
import tempfile
from importlib import import_module
from pathlib import Path

from django.apps import apps as django_apps
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import models


def has_knowledge_base_app() -> bool:
    try:
        django_apps.get_app_config('knowledge_base')
        return True
    except LookupError:
        return False


def get_knowledge_document_model():
    app_config = django_apps.get_app_config('knowledge_base')
    for model in app_config.get_models():
        field_names = {field.name for field in model._meta.get_fields()}
        if {'processing_status', 'download_count'}.issubset(field_names):
            return model
    raise AssertionError('未找到知识库文档模型，请确保模型包含 processing_status 与 download_count 字段')


def get_document_file_field_name(model) -> str:
    for field in model._meta.fields:
        if isinstance(field, models.FileField):
            return field.name
    raise AssertionError('知识库文档模型缺少 FileField')


def build_document_upload(
    filename: str,
    *,
    content: bytes = b'knowledge-base-document',
    declared_size: int | None = None,
):
    content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    if declared_size is None or declared_size <= len(content):
        return SimpleUploadedFile(filename, content, content_type=content_type), None

    handle = tempfile.NamedTemporaryFile(delete=False)
    try:
        handle.seek(declared_size - 1)
        handle.write(b'0')
        handle.flush()
    finally:
        handle.close()

    file_handle = open(handle.name, 'rb')
    return File(file_handle, name=filename), handle.name


def cleanup_source_file(source_path: str | None):
    if source_path and os.path.exists(source_path):
        os.remove(source_path)


def create_document_instance(
    *,
    user,
    title: str,
    filename: str,
    content: bytes = b'knowledge-base-document',
    declared_size: int | None = None,
    **overrides,
):
    model = get_knowledge_document_model()
    file_field_name = get_document_file_field_name(model)
    field_names = {field.name for field in model._meta.fields}
    upload, source_path = build_document_upload(filename, content=content, declared_size=declared_size)

    try:
        payload = {}
        if 'title' in field_names:
            payload['title'] = title
        if 'description' in field_names:
            payload.setdefault('description', '')
        if 'uploaded_by' in field_names:
            payload['uploaded_by'] = user
        if 'processing_status' in field_names:
            payload['processing_status'] = resolve_status_value(model)
        if 'processing_result' in field_names:
            payload.setdefault('processing_result', '')
        if 'download_count' in field_names:
            payload['download_count'] = 0

        payload[file_field_name] = upload
        payload.update(overrides)
        instance = model.objects.create(**payload)

        update_fields = []
        if 'file_name' in field_names and getattr(instance, 'file_name', '') != filename:
            instance.file_name = filename
            update_fields.append('file_name')
        if 'file_extension' in field_names:
            extension = Path(filename).suffix.lower().lstrip('.')
            if getattr(instance, 'file_extension', '') != extension:
                instance.file_extension = extension
                update_fields.append('file_extension')
        if 'file_size' in field_names and declared_size is not None and getattr(instance, 'file_size', None) != declared_size:
            instance.file_size = declared_size
            update_fields.append('file_size')

        if update_fields:
            instance.save(update_fields=update_fields)

        return instance
    finally:
        try:
            upload.close()
        except Exception:
            pass
        cleanup_source_file(source_path)


def resolve_status_value(model) -> str:
    field = model._meta.get_field('processing_status')
    choices = list(getattr(field, 'choices', []))
    if not choices:
        return 'pending'

    values = [choice[0] for choice in choices]
    if 'pending' in values:
        return 'pending'
    return values[0]


def get_response_bytes(response) -> bytes:
    if hasattr(response, 'streaming_content'):
        return b''.join(response.streaming_content)
    return response.content


def discover_access_seed():
    migrations_package = import_module('apps.knowledge_base.migrations')
    candidate_functions = []

    for module_info in sorted(pkgutil.iter_modules(migrations_package.__path__), key=lambda item: item.name):
        if not module_info.name[:4].isdigit():
            continue
        module = import_module(f'apps.knowledge_base.migrations.{module_info.name}')
        for function_name, function in inspect.getmembers(module, inspect.isfunction):
            if function_name.startswith('seed') and 'access' in function_name:
                candidate_functions.append(function)

    if not candidate_functions:
        raise AssertionError('未找到知识库 access data seed 函数')

    return candidate_functions[-1]

