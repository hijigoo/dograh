---
title: Dograh CPU optimization patch stack
description: Reproducible source-level CPU optimizations for the pinned Pipecat dependency
---

## Installation and review boundary

The `perf/cpu-optimization` integration branch collects six separate performance
changes. Pipecat remains the original pinned Git submodule. SDK changes are
reviewable unified diffs under `patches/pipecat`; their headers identify the exact
upstream source files being changed.

Docker, local setup, CI dependency installation, and devcontainer setup prepare a
separate SDK copy and install it automatically. No runtime monkey-patching or
editing of the original submodule is required. Unsupported source fingerprints
fail installation rather than silently omitting an optimization.

The lazy-TRACE PR supplies the shared installation plumbing. Merge it before the
other SDK feature PRs; each feature remains a separate patch and regression test.
The other topic branches start from the same original integration baseline, not
from a branch containing other performance changes.

## Lazy TRACE formatting

`10-lazy-trace.patch` changes the downstream and upstream push log statements in
`src/pipecat/processors/frame_processor.py`. It delays interpolation until TRACE
is enabled. Log levels, emitted text, frame delivery and callback order remain
unchanged.

## Validation

Use the repository virtual environment and initialize the Pipecat submodule first:

```bash
uv pip install -r tests/cpu_optimization/requirements.txt -e pipecat
python scripts/prepare_pipecat.py
PYTHONPATH="$PWD/.pipecat-optimized/src:$PWD" \
  python -m pytest tests/cpu_optimization -q
```

Preparation records the pinned source commit, patch hashes and generated Python
source hashes in `.pipecat-optimized/.dograh-patches.json`. Re-running preparation
is idempotent. A changed patch stack rebuilds only an owned, unedited generated
copy. Keep development edits in reviewable patches; preparation refuses to
discard edits made directly in the generated source.

These changes port the six source optimizations measured in the earlier study.
Benchmark-only loop/proxy proof exporters, profiler instrumentation, machine
addresses, worker counts and capacity-test topology are not application features
and are not imported here. Local regression tests do not constitute a new Azure
capacity measurement or promise the same latency on different infrastructure.
