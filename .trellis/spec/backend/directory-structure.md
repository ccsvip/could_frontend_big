# Directory Structure

> How backend code is organized in this project.

---

## Overview

The backend follows a standard Django REST Framework project layout with a `config/` directory for project-level settings and configuration, and `apps/` for all Django applications. Business logic lives in `services/` modules within each app, not in views or serializers.

Key principles:
- **Thin views, thick services** — ViewSets/APIViews delegate to `services/` modules
- **App-per-domain** — each self-contained feature domain gets its own Django app under `apps/`
- **Configuration externalized** — settings split by environment (`base.py` / `dev.py` / `prod.py`)
- **Async via Celery** — background tasks go in `tasks.py` within each app
- **File storage via MinIO** — uploaded files in `media/`, served through MinIO

---

## Top-Level Structure

```
backend/
├── config/                # Django project configuration
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py        # Shared settings (all environments)
│   │   ├── dev.py         # Development overrides
│   │   └── prod.py        # Production overrides
│   ├── urls.py            # Root URL configuration (/api/v1/ prefix)
│   ├── asgi.py            # ASGI entry point (single /ws/realtime/ route)
│   ├── wsgi.py            # WSGI entry point
│   ├── celery.py          # Celery app instance and configuration
│   ├── exceptions.py      # Custom DRF exception handler
│   ├── pagination.py      # StandardPageNumberPagination (max page_size 100)
│   ├── realtime.py        # WebSocket consumer for real-time events
│   ├── sentry.py          # Sentry integration setup
│   ├── request_id.py      # Request-ID middleware
│   ├── business_cache.py  # Business-level caching utilities
│   └── tests/             # Config-level tests
├── apps/                  # All Django applications
│   ├── accounts/          # Authentication, users, JWT, permissions
│   ├── tenants/           # Multi-tenant management and membership
│   ├── devices/           # Device management and runtime configuration
│   ├── resources/         # Media resources, command dispatch, MinIO
│   ├── knowledge_base/    # RAG, document indexing, vector search
│   ├── ai_models/         # ASR, TTS, LLM, chatbot integrations
│   ├── app_updates/       # OTA app update signing and distribution
│   └── audit/             # Operation audit logging
├── common/                # Reserved for shared utilities (currently empty)
├── vendor/                # Third-party vendored code
│   └── sherpa-onnx/       # ONNX runtime for speech models
├── media/                 # Uploaded files (not in VCS)
│   ├── app-updates/       # OTA update packages
│   └── resources/         # User-uploaded media resources
├── static/                # Static files (source)
├── staticfiles/           # Collected static files (production)
├── templates/             # Django templates
│   └── 404.html           # Custom 404 page
├── manage.py              # Django management script
├── requirements.txt       # Python dependencies
├── Dockerfile             # Container build
└── .env                   # Environment variables (not in VCS)
```

---

## Standard App Internal Structure

Every Django app under `apps/` follows a consistent internal layout:

```
apps/<app_name>/
├── __init__.py
├── models.py              # Django ORM models
├── views.py               # DRF ViewSets or APIViews
├── serializers.py         # DRF serializers
├── urls.py                # App-level URL routing (optional)
├── admin.py               # Django admin registration
├── apps.py                # App config class
│                          #   name = 'apps.<app_name>'
│                          #   verbose_name in Chinese
├── services/              # Business logic layer
│   ├── __init__.py
│   ├── <module>.py        # One service module per responsibility
│   └── ...
├── tasks.py               # Celery async task definitions
├── tests/                 # Test directory (preferred)
│   ├── __init__.py
│   ├── test_<subject>.py  # One file per subject
│   └── ...
├── migrations/            # Django database migrations
│   ├── __init__.py
│   └── ...
├── point_views.py         # Additional views (some apps split)
├── point_serializers.py   # Additional serializers (some apps split)
├── filters.py             # DRF filter backends (optional)
├── exceptions.py          # App-specific exceptions (optional)
├── choices.py             # Enum/model choice definitions (optional)
├── constants.py           # App-specific constants (optional)
└── signals.py             # Django signal handlers (optional)
```

### Variations

- **Small apps** (e.g., `audit/`) — may use a single `tests.py` file instead of a `tests/` directory
- **View/Serializer splits** — some apps split across `views.py`/`point_views.py` or `serializers.py`/`point_serializers.py` when the number of endpoints warrants separation
- **No separate `urls.py`** — some apps are routed directly from `config/urls.py` via `path()` entries

---

## Module Organization Rules

### Creating new code

| Scenario | Location |
|---|---|
| New feature domain | New app under `apps/<name>/` |
| New endpoint for existing domain | View in `apps/<domain>/views.py` or `point_views.py` |
| Business / orchestration logic | Module in `apps/<domain>/services/<module>.py` |
| Data transformation (request/response) | Serializer in `apps/<domain>/serializers.py` |
| Background / periodic job | Task function in `apps/<domain>/tasks.py` |
| Global config or middleware | Module in `config/` (e.g., `config/middleware.py`) |
| Third-party dependency fork | Vendored in `vendor/<name>/` |
| Shared utility (multiple apps) | `common/<module>.py` (currently reserved) |

### Where logic MUST NOT go

| Prohibited location | Reason |
|---|---|
| Business logic in `views.py` | Violates separation of concerns |
| Business logic in `serializers.py` | Serializers are for data shaping |
| DRF views in `models.py` | Model layer must be presentation-agnostic |
| Settings in individual apps | Use `config/settings/` and `django.conf.settings` |

### Rules of thumb

1. **New feature** → new app under `apps/` or new module in an existing app's `services/`
2. **Business logic** goes in `services/`, NOT in views or serializers
3. Each app has its own `tests/` directory (or `tests.py` for small apps)
4. Test files named `test_<subject>.py`

---

## Naming Conventions

| Artifact | Convention | Example |
|---|---|---|
| Django app | `apps.<snake_case>` | `apps.knowledge_base` |
| App directory | `snake_case` | `knowledge_base/` |
| Python modules | `snake_case` | `minio_client.py` |
| View classes | `PascalCase` + domain suffix | `DeviceViewSet`, `UserAPIView` |
| Serializer classes | `PascalCase` + `Serializer` | `DeviceSerializer` |
| Model classes | `PascalCase` singular | `Device`, `Tenant` |
| Service modules | `snake_case` describing responsibility | `command_dispatch.py`, `device_registration.py` |
| Celery task functions | `snake_case` | `sync_device_config`, `index_document` |
| Test files | `test_<subject>.py` | `test_models.py`, `test_views.py` |
| Test classes | `Test<PascalCaseSubject>` | `TestDeviceViewSet` |
| Test methods | `test_<scenario>_<expectation>` | `test_create_device_returns_201` |
| URL prefixes | `/api/v1/<version>/<resource>/` | `/api/v1/tenants/` |
| App config `name` | `'apps.<name>'` | `'apps.devices'` |
| App config `verbose_name` | Chinese (project convention) | `'设备管理'` |

---

## URL Routing

```
/api/v1/                     # Root API prefix (config/urls.py)
  accounts/                  # Auth, user management
  tenants/                   # Tenant management
  devices/                   # Device CRUD and control
  resources/                 # Media resource operations
  knowledge-base/            # RAG and document management
  ai-models/                 # ASR, TTS, LLM configuration
  app-updates/               # OTA update management
  audit/                     # Audit log queries

/ws/realtime/                # WebSocket endpoint (config/asgi.py -> config/realtime.py)
```

- Top-level prefix is `/api/v1/` configured in `config/urls.py`
- App-level routes are defined in each app's `urls.py` and included from `config/urls.py`
- DefaultRouter is used for ViewSet-based endpoints where applicable
- Single WebSocket route at `/ws/realtime/` handled by the consumer in `config/realtime.py`

---

## Key Infrastructure Modules

| Module (under `config/`) | Responsibility |
|---|---|
| `settings/base.py` | All shared Django settings |
| `settings/dev.py` | Development-only overrides (DEBUG, SQL logging, CORS) |
| `settings/prod.py` | Production-only overrides (SECURE, sentry, staticfiles) |
| `urls.py` | Root URL configuration with `/api/v1/` prefix |
| `asgi.py` | ASGI application with WebSocket routing |
| `celery.py` | Celery app instance, Redis broker configuration |
| `exceptions.py` | Custom `exception_handler` wrapping DRF's handler |
| `pagination.py` | `StandardPageNumberPagination` (page_size max 100) |
| `realtime.py` | WebSocket consumer for real-time event broadcasting |
| `sentry.py` | Sentry SDK initialization and configuration |
| `request_id.py` | Middleware that injects request-id into log records |
| `business_cache.py` | High-level cache helpers for business operations |

---

## Services Layer Pattern

Each app's `services/` directory contains one or more Python modules. A service module:

- Is a plain Python module (not a class-based "service object" unless composition is warranted)
- Exposes public functions that accept typed parameters and return data (dicts, model instances, or None)
- May use Django ORM, Celery tasks, MinIO client, or external APIs
- Does NOT import from views, serializers, or URL configuration
- Does NOT raise HTTP exceptions directly (returns error values or raises app-specific exceptions)

```
apps/resources/services/
├── __init__.py
├── minio_client.py          # MinIO file upload/download/delete
├── command_dispatch.py      # Device command dispatch
└── resource_processor.py    # Resource processing pipeline
```

---

## Examples

Well-organized apps:
- `apps/resources/` — clean separation of models, views, serializers, and services; MinIO interaction fully in `services/minio_client.py`
- `apps/accounts/` — permission hierarchy split from user models; services layer for registration and invitation flows
- `apps/devices/` — ViewSets delegate to services; runtime configuration handled in services layer
