# Hook Guidelines

> How custom hooks and data fetching are used in this project.

---

## Overview

This project uses **React 18 functional components** with hooks for state and lifecycle. Custom hooks are rare: only 1 exists (`useAgentAudio`). Data fetching is done **inline in components** via `useState` + `useEffect` + direct API module calls. There is **no React Query, SWR, or any server-state library**.

Custom hooks are extracted only when state+effect logic is shared across components or when managing complex lifecycle resources (WebSocket, microphone, audio playback).

---

## Current State

| Aspect | Approach |
|--------|----------|
| Custom hooks | 1 found: `useAgentAudio` in `web/src/views/application-management/` |
| Data fetching | Inline `useState` + `useEffect` + direct `fetchXxx()` API calls |
| Server state lib | None (no React Query / SWR / Zustand async) |
| Hook location | Co-located with the view (same directory), not in a global `hooks/` |
| Naming | `useXxx` camelCase per standard React convention |

---

## Naming Conventions

- **Function name**: `useXxx` with PascalCase following `use`, e.g. `useAgentAudio`, `useDeviceStream`.
- **Return value**: Always an object `{ state, action }` or `{ value, setter }`. Never return an array (avoids destructuring order confusion).
- **File name**: `use-<kebab-case>.ts` — lowercase kebab matching the hook name, e.g. `use-agent-audio.ts`.

---

## Hook Location

Hooks are **co-located with the feature module** that owns them:

```
web/src/views/application-management/
├── index.tsx              # view component
├── use-agent-audio.ts     # hook (audio + WebSocket lifecycle)
├── playback-request-guard.ts
├── audio-utils.ts
```

This follows the project's module-per-feature layout. Do **not** create a top-level `src/hooks/` directory — shared utility logic that is not tied to any view lives in `src/utils/` or a co-located module helper file.

Exception: if a hook is used by **exactly 2+ modules** and neither owns it, place it adjacent to the simpler consumer and import from there. If it grows beyond that, extract to `src/utils/`.

---

## When to Extract a Custom Hook

Extract only when one of these conditions is met:

### 1. Same state+effect logic appears in 2+ components
If two views independently duplicate the same `useState` + `useEffect` + API call pattern, extract it.

### 2. Complex lifecycle management
Resources that require careful setup/teardown: WebSocket connections, microphone streams, audio playback contexts, timers, polling intervals, AbortController trees.

Example from the codebase (`useAgentAudio`):
- Manages a WebSocket connection for ASR (automatic speech recognition)
- Owns `MediaStream` lifecycle (request → connect → stop → cleanup)
- Manages `AudioContext` + `AudioWorkletNode` with module loading
- Orchestrates TTS streaming playback queue with per-segment abort controllers
- Cleans up everything on unmount via a single `useEffect` return

### 3. Business logic tightly coupled to component lifecycle but independent of rendering
Business rules that must interact with `useEffect`/`useRef` but do not produce JSX directly. Example: a hook that tracks user idle time, manages a polling loop, or coordinates multi-step realtime protocols.

### When NOT to extract
- **Single-use logic**: A `useEffect` + `useState` pair used in only one component should stay inline. Extracting it adds indirection without benefit.
- **Pure computations**: Use `useMemo` inline, not a custom hook.
- **Simple toggle/boolean state**: Keep `useState` inline.

---

## Standard Hook Structure

Based on the project's only hook (`useAgentAudio`), the pattern is:

```typescript
import { useCallback, useEffect, useRef, useState } from 'react';

// Types (co-located, inline, or imported from the module)
type State = { ... };
type Actions = { ... };

export function useMyFeature(): { state: State; actions: Actions } {
  // --- State ---
  const [state, setState] = useState<Type>(initialValue);

  // --- Refs (for mutable values that should not trigger re-render) ---
  const ref = useRef<Type | null>(null);

  // --- Actions (useCallback-wrapped) ---
  const doSomething = useCallback(() => {
    // logic using refs and setState
  }, [deps]);

  // --- Lifecycle ---
  useEffect(() => {
    // side effects: connect, subscribe, start
    return () => {
      // cleanup: disconnect, unsubscribe, stop
    };
  }, [deps]);

  // --- Return ---
  return { state, doSomething };
}
```

### Key rules

1. **`useRef` for mutable resources** — DOM references, WebSocket instances, MediaStream objects, AbortControllers, accumulated data. Never put these in `useState`.
2. **`useCallback` for every returned function** — Prevents unnecessary re-renders in consumers. Always specify deps.
3. **Single cleanup `useEffect`** — The hook returns one cleanup effect that tears down all resources. Do NOT scatter cleanup across multiple effects.
4. **Return an object** — Named properties avoid destructuring order bugs: `const { recording, startRecording } = useAgentAudio()`.

---

## Data Fetching Pattern (Inline)

Since there is no React Query, data fetching follows this inline pattern:

```typescript
import { useCallback, useEffect, useState } from 'react';
import { fetchSomeData } from '../../api/modules/some-module';

const MyComponent = () => {
  const [data, setData] = useState<SomeType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchSomeData({ page: 1 });
      setData(result.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  // ...render
};
```

This pattern appears in nearly every view. Key characteristics:

- **`useCallback` wraps the load function** — Stable reference for `useEffect` deps.
- **`void` prefix** — Explicitly discard the returned promise.
- **`setLoading(true)` before fetch** — Always, even if it was already true (restores loading state on retry).
- **API call via module** — Never call `httpClient` directly in a component. Import from `../../api/modules/<module>.ts`.
- **Error as user-facing string** — Ant Design `message.error()` for toasts, or local `error` state for inline display.
- **No stale-data dedup** — Simple fetch-on-mount. Stale closure is avoided by putting `loadData` in deps.

---

## Paginated List Pattern

When a view manages a paginated list, the pattern is:

```typescript
const [items, setItems] = useState<RecordType[]>([]);
const [loading, setLoading] = useState(false);
const [page, setPage] = useState(1);
const [pageSize] = useState(10);   // const — never changes per view
const [total, setTotal] = useState(0);
const [keyword, setKeyword] = useState('');

const query = useMemo<ListQuery>(
  () => ({ page, keyword, ...filters }),
  [page, keyword, filters],
);

const loadItems = useCallback(async () => {
  setLoading(true);
  try {
    const res = await fetchList(query);
    setItems(res.results);
    setTotal(res.count);
  } finally {
    setLoading(false);
  }
}, [query]);

useEffect(() => {
  void loadItems();
}, [loadItems]);
```

This project uses manual pagination state (`page`, `pageSize`, `total`) and passes `page` as a query parameter. The `useMemo` query object acts as the dependency bag.

---

## Refs Usage Pattern

Common ref patterns from the codebase:

### DOM refs
```typescript
const elementRef = useRef<HTMLDivElement | null>(null);
```

### Mutable accumulators (avoid re-render)
```typescript
const transcriptRef = useRef('');   // accumulates text without re-rendering on every word
```

### Resource lifecycle handles
```typescript
const socketRef = useRef<WebSocket | null>(null);
const streamRef = useRef<MediaStream | null>(null);
const audioContextRef = useRef<AudioContext | null>(null);
const abortControllerRef = useRef<AbortController | null>(null);
```

These are cleaned up in the single `useEffect` return or in a dedicated `stopXxx` callback. Multiple refs for similar resources (e.g., multiple AbortControllers for different operations) are preferred over one generic ref.

### Callback refs (for passing to child callbacks)
```typescript
const doneCallbackRef = useRef<((text: string) => void) | null>(null);
```

This pattern avoids stale closures when callbacks are passed into WebSocket event handlers or deferred operations.

---

## Zustand Store Subscription

Hooks read global state via Zustand selectors, not the full store:

```typescript
const token = useAuthStore((state) => state.token);
const tenant = useAuthStore((state) => state.tenant);
const tenantScopeId = useTenantScopeStore((state) => state.tenantId);
```

- Always use selector functions (`(state) => state.field`), never `useAuthStore()` without a selector.
- Select individual fields, not entire objects, to avoid unnecessary re-renders.
- This applies to hooks and components alike.

---

## Common Mistakes

### Not cleaning up resources in useEffect return
**Bad**: WebSocket connection or interval started in `useEffect` but never closed on unmount. Creates resource leaks and "Cannot perform a React state update on an unmounted component" warnings.

**Good** (from `useAgentAudio`):
```typescript
useEffect(() => {
  return () => {
    stopRecording({ suppressDone: true, cancel: true });
    stopPlayback();
  };
}, [stopPlayback, stopRecording]);
```

### Over-generalizing (extracting a hook for single-use logic)
**Bad**: A 5-line `useEffect` + `useState` pair that only one component uses, extracted into a named hook. Adds indirection with zero reuse benefit.

**Good**: Keep inline. Extract only when the second consumer appears.

### Using useState for values that should be refs
**Bad**: `const [socket, setSocket] = useState<WebSocket | null>(null)` — causes unnecessary re-renders every time the socket reference updates.

**Good**: `const socketRef = useRef<WebSocket | null>(null)`.

### Calling httpClient directly in the component
**Bad**: `const res = await httpClient.get(...)` inside a view. Bypasses the API module layer, making the code harder to find and type-check.

**Good**: `const res = await fetchApplications({ page: 1 })` from `api/modules/applications.ts`.

### Missing deps in useCallback
React's exhaustive-deps lint rule is **enabled** (`tsc -b` is strict). Missing deps cause stale closures. Always include every reactive value used inside a `useCallback` or `useEffect`.

### Cleaning up refs without nulling sibling refs
When stopping a multi-resource process (e.g., audio streaming), null out **all** related refs, not just the primary one. The `stopRecording` function in `useAgentAudio` sets `workletNodeRef`, `sourceRef`, `gainRef`, `streamRef`, `audioContextRef`, and `socketRef` to `null` — an example of thorough cleanup.
