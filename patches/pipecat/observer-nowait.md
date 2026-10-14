---
title: Observer enqueue fast path
description: Avoid put coroutine overhead only for exact unbounded asyncio queues
---

## Source changes

`30-observer-nowait.patch` changes the push and general fanout enqueue sites in
`src/pipecat/pipeline/worker_observer.py`.

Only `type(queue) is asyncio.Queue` with `maxsize == 0` uses `put_nowait`.
Bounded queues and subclasses retain their awaited `put` behavior. Consumer
callbacks, FIFO, `get`, `task_done`, join, first-push filtering and cleanup are
unchanged.

The shared installer applies this patch before the no-op observer filter. Merge
the lazy-TRACE installation-plumbing PR before deployment. Targeted tests exercise
the real WorkerObserver and cover ordering, join, custom queues, backpressure and
cancellation.
