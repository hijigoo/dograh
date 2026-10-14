---
title: Exact no-op observer filter
description: Omit only the unchanged inherited BaseObserver process callback
---

## Source changes

`40-noop-observer-filter.patch` modifies
`src/pipecat/pipeline/worker_observer.py` and adds
`src/pipecat/pipeline/_observer_filter.py`.

Only `FrameProcessed` notifications targeting the exact original
`BaseObserver.on_process_frame` implementation are omitted. Method identity and
code-object identity are both checked. Overrides, instance callbacks and a
modified base function retain delivery. Push, setup and pipeline lifecycle
notifications remain enabled, including for observers with an empty process
callback.

This uses the same predicate and fanout semantics as the tested optimization.
Benchmark-only filter-statistics file exports are intentionally not included.
The leading-context insertion hunk is independent of the queue put expression,
so it composes with the observer-nowait patch applied earlier by the installer.
Merge the lazy-TRACE installation-plumbing PR before deployment.
