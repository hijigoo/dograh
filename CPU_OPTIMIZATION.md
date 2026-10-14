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

| Optimization | Topic branch | SDK or runtime files changed |
| --- | --- | --- |
| Lazy TRACE | `cpu-opt/01-lazy-trace` | `processors/frame_processor.py` |
| CPU ONNX session cache | `cpu-opt/02-onnx-session-cache` | `audio/vad/silero.py`, `audio/vad/cpu_session_cache.py` |
| Observer queue fast path | `cpu-opt/03-observer-nowait` | `pipeline/worker_observer.py` |
| Exact no-op filter | `cpu-opt/04-noop-observer-filter` | `pipeline/worker_observer.py`, `pipeline/_observer_filter.py` |
| VAD coalescing | `cpu-opt/05-vad-coalescing` | `audio/vad/vad_analyzer.py` |
| uvloop | `cpu-opt/06-uvloop` | `api/requirements.txt`, existing Uvicorn auto-loop entrypoints |

`perf/cpu-optimization` is the integration target, not an individual feature.
The six independent review branches use `cpu-opt/NN-` to distinguish them from
that target. Their numbering follows the source-patch installation order.

SDK paths in the table are relative to `pipecat/src/pipecat`. Build order is
explicit in patch filenames, so merging the independently committed patch files
does not introduce a submodule-pointer conflict or runtime import override.

## Lazy TRACE formatting

`10-lazy-trace.patch` changes the downstream and upstream push log statements in
`src/pipecat/processors/frame_processor.py`. It delays interpolation until TRACE
is enabled. Log levels, emitted text, frame delivery and callback order remain
unchanged.

## API image builds

Run from the repository root on the CPU optimization branch:

```bash
git submodule update --init --recursive
docker build -f api/Dockerfile -t dograh-api:cpu-optimized .
```

The Dockerfile applies all patches in `patches/pipecat` and installs the prepared
SDK during image build. It does not run regression tests or deploy the image.
Configure your deployment to use the built image and recreate its API container.
Restarting an existing container does not apply a changed patch stack.

CPU 최적화 브랜치의 저장소 루트에서 위 명령을 실행합니다. Pipecat 서브모듈을 초기화한 뒤
API 이미지를 빌드합니다.

Dockerfile은 이미지 빌드 중에 `patches/pipecat`의 모든 패치를 적용하고, 패치가 적용된
SDK를 설치합니다. 회귀 테스트를 실행하거나 이미지를 배포하는 명령은 아닙니다.
배포 설정이 빌드한 이미지를 사용하도록 지정한 뒤 API 컨테이너를 재생성해야 합니다.
기존 컨테이너를 재시작하는 것만으로는 변경된 패치가 적용되지 않습니다.

## Validation

Use the repository virtual environment and initialize the Pipecat submodule first:

```bash
uv pip install -r tests/cpu_optimization/requirements.txt -e pipecat
python scripts/prepare_pipecat.py
uv pip install --no-deps -e .pipecat-optimized
python -m pytest tests/cpu_optimization -q
```

This validates the installed, prepared SDK without a `PYTHONPATH` override.

`PYTHONPATH`로 소스 경로를 덮어쓰지 않고, 패치를 적용해 실제 설치한 SDK를 검증합니다.

Preparation records the pinned source commit, patch hashes and generated Python
source hashes in `.pipecat-optimized/.dograh-patches.json`. Re-running preparation
is idempotent. A changed patch stack rebuilds only an owned, unedited generated
copy. Keep development edits in reviewable patches; preparation refuses to
discard edits made directly in the generated source.

The focused GitHub Actions workflow targets both `main` and
`perf/cpu-optimization`. Its hosted results are separate from local verification.
After merging all six PRs, rerun dependency setup or rebuild the API image.
Checking out the merged branch alone does not replace already installed packages
or a running container.

These changes port the six source optimizations measured in the earlier study.
Benchmark-only loop/proxy proof exporters, profiler instrumentation, machine
addresses, worker counts and capacity-test topology are not application features
and are not imported here. Local regression tests do not constitute a new Azure
capacity measurement or promise the same latency on different infrastructure.
