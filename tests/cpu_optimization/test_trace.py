"""Exercise the installed FrameProcessor hot path, not a logging imitation."""

import asyncio

from loguru import logger
from pipecat.frames.frames import Frame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class CountedFrame(Frame):
    """Expose formatting work without changing the frame semantics."""

    def __post_init__(self):
        super().__post_init__()
        self.formats = 0

    def __str__(self):
        self.formats += 1
        return "counted-frame"


class Receiver(FrameProcessor):
    """Capture delivery without requiring a full telephony pipeline."""

    def __init__(self):
        super().__init__()
        self.received = []

    async def queue_frame(
        self, frame, direction=FrameDirection.DOWNSTREAM, callback=None
    ):
        self.received.append((frame, direction))


def test_given_disabled_trace_when_delivering_frames_then_formatting_is_deferred():
    async def exercise():
        sender, receiver, frame = FrameProcessor(), Receiver(), CountedFrame()
        sender.link(receiver)
        await sender._FrameProcessor__internal_push_frame(
            frame, FrameDirection.DOWNSTREAM
        )
        assert receiver.received == [(frame, FrameDirection.DOWNSTREAM)]
        assert frame.formats == 0

    sink = logger.add(lambda message: None, level="INFO")
    try:
        asyncio.run(exercise())
    finally:
        logger.remove(sink)


def test_given_enabled_trace_when_delivering_both_directions_then_log_text_is_preserved():
    async def exercise():
        sender, receiver, frame = FrameProcessor(), Receiver(), CountedFrame()
        sender.link(receiver)
        await sender._FrameProcessor__internal_push_frame(
            frame, FrameDirection.DOWNSTREAM
        )
        await receiver._FrameProcessor__internal_push_frame(
            frame, FrameDirection.UPSTREAM
        )
        return frame

    messages = []
    sink = logger.add(
        lambda message: messages.append(message.record["message"]), level="TRACE"
    )
    try:
        frame = asyncio.run(exercise())
    finally:
        logger.remove(sink)
    assert frame.formats == 2
    assert any(
        message.startswith("Pushing counted-frame downstream from ")
        for message in messages
    )
    assert any(
        message.startswith("Pushing counted-frame upstream from ")
        for message in messages
    )
