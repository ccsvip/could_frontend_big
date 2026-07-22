# Testing Strategy

> Testing conventions, patterns, and infrastructure for the backend.

---

## Overview

This project uses **Django's built-in unittest framework** (not pytest). Tests run inside Docker containers via `docker compose exec backend`. There is no separate test settings module — `config.settings.dev` is the test-time settings file.

---

## Table of Contents

- [Test Framework](#test-framework)
- [Running Tests](#running-tests)
- [Test Location & Naming](#test-location--naming)
- [Test Data Creation](#test-data-creation)
- [Test Utilities](#test-utilities)
- [Authentication in Tests](#authentication-in-tests)
- [Common Test Patterns](#common-test-patterns)
- [Mock Strategy](#mock-strategy)
- [WebSocket Testing](#websocket-testing)
- [Coverage](#coverage)
- [CI](#ci)
- [Known Gaps & Risks](#known-gaps--risks)

---

## Test Framework

**Framework**: Django unittest (`django.test`)

**Runner**: `python manage.py test`

**Settings file**: `config.settings.dev` (no separate `test.py` settings module)

```python
# backend/config/settings/dev.py
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]
```

**No pytest**: pytest usage is explicitly forbidden per project convention (`AGENTS.md`). There is no `pytest.ini`, `setup.cfg`, `conftest.py`, or `pyproject.toml` for test configuration. The `.pytest_cache/` directory exists in `.gitignore` but is stale/accidental.

**Forbidden**:
```bash
# ❌ Never run pytest
docker compose exec backend pytest apps.<app>.tests

# ❌ Never run tests on the host
python manage.py test apps.<app>.tests
```

**Test base classes used**:

| Class | When to use | Example |
|-------|-------------|---------|
| `APITestCase` | HTTP API endpoint tests | `class DeviceAuthTests(TenantTestMixin, APITestCase)` |
| `TestCase` | Non-API service tests, access data tests, WebSocket tests | `class ASRRealtimeTests(TenantTestMixin, TestCase)` |
| `SimpleTestCase` | No-database tests (config, WebSocket protocol logic) | `class RealtimeWebSocketTests(SimpleTestCase)` |

If a test needs both HTTP client and tenant context, inherit from both `TenantTestMixin` and `APITestCase`:
```python
class MyTests(TenantTestMixin, APITestCase):
    pass
```

---

## Running Tests

All test commands run inside the Docker backend container. Use `--keepdb` to preserve the test database between runs for faster iteration.

**Run all tests for a single app**:
```bash
docker compose exec backend python manage.py test apps.<app>.tests --keepdb
```

**Run a single test file**:
```bash
docker compose exec backend python manage.py test apps.<app>.tests.test_<subject> --keepdb
```

**Run a single test class or method**:
```bash
docker compose exec backend python manage.py test apps.<app>.tests.test_<subject>.ClassName.test_method --keepdb
```

**Run all backend tests**:
```bash
docker compose exec backend python manage.py test apps --keepdb
docker compose exec backend python manage.py test config.tests --keepdb
```

**Run config-level tests (WebSocket, Celery, Sentry, cache)**:
```bash
docker compose exec backend python manage.py test config.tests --keepdb
```

---

## Test Location & Naming

### Location

Tests live **inside each app**, either as a `tests/` directory or a single `tests.py` file:

```
backend/
  apps/
    <app_name>/
      tests/                              # preferred (most apps)
        __init__.py
        test_<subject>.py
        test_<subject>.py
      tests.py                            # legacy (accounts app only)
    tenants/
      test_utils.py                       # shared test utilities
  config/
    tests/                                # config-level tests
      test_realtime_websocket.py
      test_realtime_command_dispatch.py
      test_celery_scheduler.py
      test_sentry_before_send.py
      test_business_cache.py
      test_cache_settings.py
```

### Naming

- Test files: `test_<subject>.py` (lowercase, underscores)
- Test classes: `class <Subject>Tests(...)` (PascalCase, `Tests` suffix)
- Test methods: `def test_<behavior>(self)` (snake_case, `test_` prefix)

### Shared Test Utilities

- **`backend/apps/tenants/test_utils.py`** — contains `TenantTestMixin`, the primary shared test utility across apps
- Each app may define its own helper functions at the top of `test_<subject>.py` (e.g., `build_upload()` in `test_backend_management_flow_api.py`)

---

## Test Data Creation

**Direct ORM** — use `Model.objects.create()` everywhere. There is **no factory_boy**, no model factories, and no fixture files.

```python
# Good — direct model creation
self.user = User.objects.create_user(username='test-user', password='test123456')
self.tenant = Tenant.objects.create(name='测试公司', code='test-company')
self.device = Device.objects.create(code='DEVICE-001', name='Test Device', tenant=self.tenant)
```

**Superuser creation** for platform-level admin endpoints:
```python
self.superuser = User.objects.create_superuser('admin', 'a@x.com', 'pw12345678')
```

**Avoid** raw SQL queries or `TestCase.fixtures`. Every test explicitly creates the models it needs.

---

## Test Utilities

### `TenantTestMixin` (from `apps.tenants.test_utils`)

The primary shared mixin for providing tenant context in tests:

```python
from apps.tenants.test_utils import TenantTestMixin

class MyApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='test123456')
        self.setup_tenant(self.user)  # creates Tenant, Membership, grants permissions
```

**Methods**:

| Method | Description |
|--------|-------------|
| `setup_tenant(user, *, is_tenant_admin=False)` | Creates a `Tenant` (code=`'test-tenant'`, name=`'测试公司'`), creates `Membership` for the user, calls `grant_all_scope_to_tenant()`. Returns the `Tenant`. |
| `grant_all_scope_to_tenant()` | Grants **all** existing `Menu` and `PermissionPoint` records to `self.tenant`. Call this again after creating new permissions in tests. |

**Note**: The mixin was introduced during PR-2 (row-level tenant isolation) to backfill tenant context for older tests. It provides the minimum setup needed so that request-processing code resolves to the correct tenant.

### `@override_settings`

Used per-class or per-method to modify Django settings for a test:

```python
@override_settings(BUSINESS_CACHE_ENABLED=False)
class CrossTenantIsolationTests(APITestCase):
    ...
```

```python
@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='app-update-tests-'))
class AppReleaseManagementTests(TestCase):
    ...
```

### `setUpTestData` (class-level data)

Use `@classmethod def setUpTestData(cls)` for data shared across all test methods, avoiding re-creation per test:

```python
@override_settings(BUSINESS_CACHE_ENABLED=False)
class CrossTenantIsolationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant_a = Tenant.objects.create(name='公司A', code='comp-a')
        cls.tenant_b = Tenant.objects.create(name='公司B', code='comp-b')
        # ... create shared data
```

### Per-test `setUp`

Individual test setup for user/session state:
```python
def setUp(self):
    self.user = User.objects.create_user(username='tester', password='test123456')
    self.setup_tenant(self.user)
    self.client.force_authenticate(user=self.user)
```

---

## Authentication in Tests

### Authenticated requests (most tests)

Use `self.client.force_authenticate(user)` to attach a user to the DRF test client:

```python
self.client.force_authenticate(user=self.user)
# subsequent self.client.get/post/patch/delete will be authenticated
```

### Device/runtime endpoints (no user login)

Set `user=None` to simulate device-code-authenticated requests:

```python
self.client.force_authenticate(user=None)
response = self.client.post('/api/v1/ai-models/tts/runtime/', ...)
```

### CSRF-sensitive endpoints

Use `APIClient(enforce_csrf_checks=True)` for endpoints that must work without CSRF even when a session cookie exists:

```python
from rest_framework.test import APIClient

client = APIClient(enforce_csrf_checks=True)
self.assertTrue(client.login(username='user', password='pw'))
response = client.post('/api/v1/auth/account-applications/', ...)
```

### Token-based auth (JWT)

Some tests use `AccessToken` from `rest_framework_simplejwt` directly:

```python
from rest_framework_simplejwt.tokens import AccessToken

token = AccessToken.for_user(self.user)
self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
```

### Permission grants

For permission-controlled endpoints, create `PermissionPoint` records and assign them via role:

```python
def grant_permissions(self, *codes: str):
    permission_points = [PermissionPoint.objects.get(code=code) for code in codes]
    role = Role.objects.create(name='test', code='test')
    role.permission_points.set(permission_points)
    UserRole.objects.create(user=self.user, role=role)
```

Or use the `TenantTestMixin` shortcut:
```python
self.setup_tenant(self.user)   # grants ALL permissions via grant_all_scope_to_tenant()
```

---

## Common Test Patterns

### 1. API endpoint tests

```python
class DeviceAuthorizationApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='device-admin', password='test123456')
        self.setup_tenant(self.user)
        self.grant_permissions('devices.view', 'devices.create', 'devices.update')
        self.client.force_authenticate(user=self.user)

    def test_list_devices_returns_own_tenant_only(self):
        response = self.client.get('/api/v1/devices/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
```

### 2. Service-layer tests

```python
class AgentKnowledgeRetrievalTests(TenantTestMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='kb-tester', password='test123456')
        self.setup_tenant(self.user)

    def test_retrieve_relevant_chunks_returns_scoped_results(self):
        chunks = retrieve_relevant_chunks(self.tenant, query, top_k=3)
        self.assertEqual(len(chunks), 2)
```

### 3. Access data / migration tests

```python
class ChatAccessDataTests(TestCase):
    def test_seed_menu_creates_expected_entries(self):
        self.assertFalse(Menu.objects.filter(key='/ai-models/chat').exists())
```

### 4. Config-level no-database tests

```python
class RealtimeWebSocketTests(SimpleTestCase):
    @override_settings(ASR_BASE_URL='wss://test.example.com')
    def test_websocket_connects_with_correct_url(self):
        ...
```

---

## Mock Strategy

**Toolkit**: `unittest.mock` (stdlib)

### Context manager (preferred for method-level mocks)

```python
with patch('apps.accounts.views.notify_account_application.delay') as notify_delay:
    response = self.client.post('/api/v1/auth/account-applications/', payload, format='json')
    notify_delay.assert_called_once()
```

### Multiple context managers

Use `with (...)` for multiple mocks:

```python
with (
    patch('apps.resources.tasks.notify_command_event_task.delay') as event_delay,
    patch('apps.resources.tasks.notify_command_change_task.delay') as change_delay,
):
    response = self.client.post(...)
```

### Decorator (for class-wide invariants)

```python
@patch('apps.resources.services.feishu.send_feishu_card', return_value=True)
class MyTestClass(APITestCase):
    def test_something(self, mock_send_card):
        ...
```

### `setUp`/`tearDown` (for long-lived mocks)

```python
class BackendManagementFlowApiTests(TenantTestMixin, APITestCase):
    def setUp(self):
        self.command_notification_delay_patcher = patch('apps.resources.tasks.notify_command_event_task.delay')
        self.command_notification_delay = self.command_notification_delay_patcher.start()
        self.command_change_delay_patcher = patch('apps.resources.tasks.notify_command_change_task.delay')
        self.command_change_delay = self.command_change_delay_patcher.start()
        # ... create test data ...

    def tearDown(self):
        self.command_notification_delay_patcher.stop()
        self.command_change_delay_patcher.stop()
```

### Common mock targets

| Target | Pattern | Example |
|--------|---------|---------|
| Celery tasks | `patch('apps.<app>.views.<task>.delay')` | `patch('apps.accounts.views.notify_account_application.delay')` |
| HTTP clients | Custom dummy classes | `_DummyHttpxClient`, `DummyThirdPartyClient` |
| WebSocket upstreams | `UnifiedASRUpstream`, `UnifiedTTSUpstream` etc. (defined in the test file itself) | `patch('module.UnifiedASRUpstream')` |
| Feishu webhook | `patch('apps.resources.services.feishu.send_feishu_card')` | `@patch('apps.resources.services.feishu.send_feishu_card', return_value=True)` |
| File operations | `@patch('module.function')` | `@patch('apps.resources.views.os.remove')` |

### Dummy client pattern (for HTTP mocking)

Define a replacement class that records calls for later assertion:

```python
class DummyThirdPartyClient:
    calls = []

    def __init__(self, responses):
        self._responses = responses

    def get(self, url, **kwargs):
        DummyThirdPartyClient.calls.append({'method': 'GET', 'url': url, 'kwargs': kwargs})
        return self._responses.pop(0)

    def post(self, url, **kwargs):
        DummyThirdPartyClient.calls.append({'method': 'POST', 'url': url, 'kwargs': kwargs})
        return self._responses.pop(0)

# In test:
DummyThirdPartyClient.calls = []
with patch('apps.ai_models.services.third_party_chatbots.httpx.Client',
           return_value=DummyThirdPartyClient(responses)):
    response = self.client.post(...)
    self.assertEqual(DummyThirdPartyClient.calls[0]['method'], 'GET')
```

Async variant (`_DummyHttpxClient`) is used for streaming SSE/async HTTP endpoints in `test_agent_application_api.py` and `test_chat_api.py`.

---

## WebSocket Testing

**Tools**:
- `asgiref.testing.ApplicationCommunicator` — simulates the ASGI protocol in tests
- `asgiref.sync.async_to_sync` — bridges async WebSocket code into sync test methods

### Pattern

```python
from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator

async def run_websocket():
    from config.asgi import application

    communicator = ApplicationCommunicator(
        application,
        {
            'type': 'websocket',
            'path': '/ws/realtime/',
            'query_string': b'',
            'headers': [],
        },
    )

    # Connect
    await communicator.send_input({'type': 'websocket.connect'})
    response = await communicator.receive_output()
    assert response['type'] == 'websocket.accept'

    # Send a message
    await communicator.send_input({
        'type': 'websocket.receive',
        'text': json.dumps({'type': 'some.event', ...}),
    })

    # Receive a response
    response = await communicator.receive_output()
    data = json.loads(response['text'])
    assert data['type'] == 'expected.response'

    # Close
    await communicator.send_input({'type': 'websocket.disconnect'})

# In test method:
def test_websocket_behavior(self):
    async_to_sync(run_websocket)()
```

### Upstream mock patterns for WebSocket tests

Define dummy async context manager classes in the test file to mock upstream ASR/TTS WebSocket connections:

```python
class UnifiedASRUpstream:
    def __init__(self):
        self._events = asyncio.Queue()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def send(self, event):
        await self._events.put(event)

    async def recv(self):
        event = await asyncio.wait_for(self._events.get(), timeout=1)
        return event

    async def close(self):
        pass
```

WebSocket tests reside in two locations:
- **`backend/config/tests/`** — protocol-level tests (`test_realtime_websocket.py`, `test_realtime_command_dispatch.py`)
- **Per-app `tests/`** — application-level tests (`test_asr_realtime.py`, `test_tts_api.py`, `test_device_authorization_api.py`)

---

## Coverage

**Coverage is not configured.** There is no `.coveragerc`, `pyproject.toml`, or pytest-cov config.

Coverage artifacts are gitignored:
```
.coverage
.coverage.*
htmlcov/
coverage.xml
*.cover
```

To run coverage manually (research / report generation only):
```bash
docker compose exec backend pip install coverage
docker compose exec backend coverage run --source='.' manage.py test apps --keepdb
docker compose exec backend coverage report
```

The project does not enforce any coverage threshold.

---

## CI

**No CI pipeline is implemented.** The `.github/` directory is empty. There are no GitHub Actions, GitLab CI, Jenkins, or CircleCI configurations.

The only automated quality gates are:
1. **TypeScript compilation**: `npm run build` (runs `tsc -b && vite build`)
2. **Pre-commit hook**: `scripts/pre-commit` — token check only

There is no automated test runner in CI, no linting step, and no build validation beyond the frontend TypeScript check.

---

## Known Gaps & Risks

### Backend

| Gap | Impact | Mitigation |
|-----|--------|------------|
| No pytest — no `@pytest.mark.parametrize` | Tests are verbose, repeated patterns require manual loops | Use helper methods that iterate over cases; accept boilerplate |
| No factory_boy — `Model.objects.create()` used everywhere | Schema changes (required fields, new constraints) break every test that creates that model | Update tests during migrations; no mitigation beyond diligence |
| No coverage measurement | Untested code paths go unnoticed | Coverage must be added before any CI pipeline; not currently gated |
| No CI pipeline | No automated test execution; tests only run on developer machines | Manual `docker compose exec` before commits; no regression safety net |
| `TenantTestMixin` grants ALL permissions | Cannot test fine-grained permission denial without extra setup | Revoke specific permissions after `setup_tenant()` by clearing `self.tenant.permission_points` |

### Frontend

| Gap | Impact |
|-----|--------|
| No test runner (no vitest, jest, or equivalent) | Zero frontend test coverage |
| No frontend test files | All QA relies on manual testing or type-checking |
| Only 5 manual test scripts in `scripts/` | No automated UI validation |

---

## Appendices

### A. Quick Reference Commands

```bash
# Run a single app's tests
docker compose exec backend python manage.py test apps.devices.tests --keepdb

# Run config-level tests
docker compose exec backend python manage.py test config.tests --keepdb

# Run all backend tests
docker compose exec backend python manage.py test apps config.tests --keepdb

# Run a single test class
docker compose exec backend python manage.py test apps.devices.tests.test_device_authorization_api.DeviceAuthorizationApiTests --keepdb

# Run a single test method
docker compose exec backend python manage.py test apps.devices.tests.test_device_authorization_api.DeviceAuthorizationApiTests.test_device_list_scoped_to_own_tenant --keepdb
```

### B. File Inventory

| Location | Description |
|----------|-------------|
| `backend/apps/tenants/test_utils.py` | `TenantTestMixin` — shared tenant setup |
| `backend/apps/<app>/tests/` | Per-app test directory (preferred layout) |
| `backend/apps/accounts/tests.py` | Legacy single-file test layout |
| `backend/config/tests/` | Config-level tests (WebSocket, Celery, Sentry, cache) |
