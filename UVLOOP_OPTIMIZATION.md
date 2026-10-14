---
title: Uvicorn uvloop CPU optimization
description: Install the tested event loop version for supported API runtimes
---

## Runtime dependency

`api/requirements.txt` pins `uvloop==0.21.0` for CPython on non-Windows platforms,
matching the tested optimized image. Docker, the devcontainer and both setup
scripts already install this manifest.

All existing Uvicorn entrypoints keep their default `--loop auto` behavior.
Installing uvloop makes Uvicorn select it on supported platforms without changing
worker counts, ports, reload behavior or service orchestration. Windows retains
the original asyncio implementation. Custom commands that explicitly force
`--loop asyncio` must remove that override to use this optimization.

## Verification

The targeted test exercises Uvicorn's actual auto-loop configuration and then
delivers a frame through real Pipecat FrameProcessors on that running loop.
Importing uvloop alone is not considered proof of activation.

This PR is independent of the five SDK source patches. After all six PRs merge,
the standard installation builds the patched SDK and installs the pinned event
loop. Rebuild existing images and rerun dependency setup; checking out source
does not change an already-running container.
