---
title: VAD input coalescing
description: Avoid executor round trips that cannot complete a Silero model window
---

## Source changes

`50-vad-coalescing.patch` modifies only
`src/pipecat/audio/vad/vad_analyzer.py`.

Inputs smaller than the next complete model window accumulate on the event loop
under a per-analyzer lock. Complete windows still run the original
`_run_analyzer` on the original per-call executor. Model-window bytes, inference
counts, thresholds, volume smoothing and state transitions are unchanged.

A running cancelled job remains a barrier before any following input mutates
the buffer. A queued job that has not started is cancelled rather than processing
a cancelled input later. Worker failures propagate. No shared executor or
cross-call state is introduced.

This inlines the previously tested coalescing helper into the owning analyzer.
The pending barrier is also cleared after a completed failed job. Tests compare
actual inputs and states with the unchanged original window algorithm and cover
both running and queued cancellation. Merge the lazy-TRACE installation-plumbing
PR before deployment.
