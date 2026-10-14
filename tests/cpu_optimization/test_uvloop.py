"""Verify Uvicorn auto selection on an actual Pipecat frame-delivery coroutine."""

import asyncio
import sys
from importlib.metadata import version
from pathlib import Path

import pytest
import uvicorn
from pipecat.frames.frames import Frame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or sys.implementation.name != "cpython",
    reason="uvloop supports CPython on Unix; Uvicorn retains asyncio elsewhere",
)


def test_given_pinned_uvloop_when_starting_uvicorn_auto_then_pipeline_uses_uvloop():
    class Receiver(FrameProcessor):
        def __init__(self):
            super().__init__()
            self.received = []

        async def queue_frame(
            self, frame, direction=FrameDirection.DOWNSTREAM, callback=None
        ):
            self.received.append((frame.id, direction))

    async def exercise():
        sender, receiver, frame = FrameProcessor(), Receiver(), Frame()
        sender.link(receiver)
        await sender._FrameProcessor__internal_push_frame(
            frame, FrameDirection.DOWNSTREAM
        )
        return (
            type(asyncio.get_running_loop()).__module__,
            receiver.received,
            frame.id,
        )

    async def application(scope, receive, send):
        raise AssertionError("Loop-selection test must not start application services")

    previous = asyncio.get_event_loop_policy()
    try:
        uvicorn.Config(application, loop="auto").setup_event_loop()
        module, delivered, frame_id = asyncio.run(exercise())
    finally:
        asyncio.set_event_loop_policy(previous)

    assert version("uvloop") == "0.21.0"
    assert module == "uvloop"
    assert delivered == [(frame_id, FrameDirection.DOWNSTREAM)]


def test_given_api_dependency_manifest_when_installing_then_uvloop_pin_is_platform_scoped():
    requirements = Path(__file__).resolve().parents[2] / "api/requirements.txt"

    assert (
        'uvloop==0.21.0; sys_platform != "win32" and platform_python_implementation == "CPython"'
        in requirements.read_text()
    )
