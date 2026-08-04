from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.test import TestCase

from apps.devices.models import Device, WakeWord
from apps.tenants.models import Tenant


class WakeWordTenantBindingRepairTests(TestCase):
    def test_removes_only_cross_tenant_wake_word_device_bindings(self):
        tenant = Tenant.objects.create(name='Tenant A', code='wake-word-tenant-a')
        other_tenant = Tenant.objects.create(name='Tenant B', code='wake-word-tenant-b')
        device = Device.objects.create(tenant=tenant, code='WAKE-WORD-TENANT-DEVICE', name='Tenant A Device')
        unbound_device = Device.objects.create(tenant=None, code='UNBOUND-WAKE-WORD-DEVICE', name='Unbound Device')
        own_wake_word = WakeWord.objects.create(
            tenant=tenant,
            text='你好小灵',
            encoded_text='n ǐ h ǎo x iǎo l íng',
        )
        foreign_wake_word = WakeWord.objects.create(
            tenant=other_tenant,
            text='你好小乐',
            encoded_text='n ǐ h ǎo x iǎo l è',
        )
        unbound_wake_word = WakeWord.objects.create(
            tenant=None,
            text='你好小明',
            encoded_text='n ǐ h ǎo x iǎo m íng',
        )
        own_wake_word.devices.add(device, unbound_device)
        foreign_wake_word.devices.add(device)
        unbound_wake_word.devices.add(device)

        migration = import_module(
            'apps.devices.migrations.0026_remove_cross_tenant_wake_word_bindings'
        )
        schema_editor = SimpleNamespace(connection=connection)
        migration.remove_cross_tenant_wake_word_device_bindings(apps, schema_editor)
        migration.remove_cross_tenant_wake_word_device_bindings(apps, schema_editor)

        self.assertTrue(own_wake_word.devices.filter(id=device.id).exists())
        self.assertFalse(own_wake_word.devices.filter(id=unbound_device.id).exists())
        self.assertFalse(foreign_wake_word.devices.filter(id=device.id).exists())
        self.assertFalse(unbound_wake_word.devices.filter(id=device.id).exists())
        self.assertTrue(WakeWord.objects.filter(id=foreign_wake_word.id).exists())
        self.assertTrue(WakeWord.objects.filter(id=unbound_wake_word.id).exists())
        self.assertTrue(Device.objects.filter(id=unbound_device.id).exists())
