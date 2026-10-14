---
title: CPU ONNX session cache
description: Reuse immutable CPU sessions while preserving per-call Silero state
---

## Source changes

`20-session-cache.patch` modifies `src/pipecat/audio/vad/silero.py` and adds
`src/pipecat/audio/vad/cpu_session_cache.py`.

Only the explicit CPU-provider branch reuses a process-local ONNX session.
The cache is locked, bounded to four entries, and keyed by canonical path or
model bytes. CPU intra/inter-op thread counts remain one. The model file must
remain immutable at its path during a process lifetime.

Each call still owns its Silero wrapper, recurrent state, context, sample-rate
history and resets. Non-CPU execution providers retain their original behavior.
Errors constructing a session propagate and are not cached.

Merge the lazy-TRACE installation-plumbing PR before deployment. The shared
installer automatically discovers this independent source patch. Tests cover
threaded reuse, eviction, construction errors and real Silero state isolation.
