"""Verify that only the original empty process callback is omitted."""

import asyncio
from contextlib import suppress
from types import MethodType

from pipecat.frames.frames import Frame
from pipecat.observers.base_observer import BaseObserver, FrameProcessed, FramePushed
from pipecat.pipeline._observer_filter import is_noop_process
from pipecat.pipeline.worker_observer import Proxy, WorkerObserver
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


def test_given_original_or_inherited_callback_when_classifying_then_only_exact_noop_is_skipped():
    class Inherited(BaseObserver):
        pass

    class Override(BaseObserver):
        async def on_process_frame(self, data):
            return None

    assert is_noop_process(BaseObserver())
    assert is_noop_process(Inherited())
    assert not is_noop_process(Override())


def test_given_instance_override_when_classifying_then_callback_is_retained():
    observer = BaseObserver()

    async def callback(self, data):
        return None

    observer.on_process_frame = MethodType(callback, observer)

    assert not is_noop_process(observer)


def test_given_replaced_base_function_code_when_classifying_then_callback_is_retained(
    monkeypatch,
):
    async def replacement(self, data):
        data.frame.metadata["observed"] = True

    monkeypatch.setattr(BaseObserver.on_process_frame, "__code__", replacement.__code__)

    assert not is_noop_process(BaseObserver())


def test_given_mixed_observers_when_processing_then_active_callbacks_and_push_are_preserved():
    async def exercise():
        class Active(BaseObserver):
            def __init__(self):
                super().__init__()
                self.processed = []

            async def on_process_frame(self, data):
                self.processed.append(data.frame.id)

        worker, noop, active = WorkerObserver(), BaseObserver(), Active()
        noop_queue, active_queue = asyncio.Queue(), asyncio.Queue()
        task = asyncio.create_task(worker._proxy_task_handler(active_queue, active))
        worker._proxies = {
            noop: Proxy(queue=noop_queue, task=task, observer=noop),
            active: Proxy(queue=active_queue, task=task, observer=active),
        }
        processor, frame = FrameProcessor(), Frame()
        processed = FrameProcessed(processor, frame, FrameDirection.DOWNSTREAM, 0)
        pushed = FramePushed(processor, processor, frame, FrameDirection.DOWNSTREAM, 0)
        try:
            await worker.on_process_frame(processed)
            await asyncio.wait_for(active_queue.join(), 2)
            assert noop_queue.empty()
            assert active.processed == [frame.id]
            await worker.on_push_frame(pushed)
            assert noop_queue.get_nowait() is pushed
            noop_queue.task_done()
            await asyncio.wait_for(active_queue.join(), 2)
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    asyncio.run(exercise())


def test_given_noop_observer_when_pipeline_starts_then_non_process_events_are_delivered():
    async def exercise():
        worker, observer, queue = WorkerObserver(), BaseObserver(), asyncio.Queue()
        idle = asyncio.create_task(asyncio.sleep(30))
        worker._proxies = {observer: Proxy(queue=queue, task=idle, observer=observer)}
        try:
            await worker.on_pipeline_started()
            assert queue.qsize() == 1
        finally:
            idle.cancel()
            with suppress(asyncio.CancelledError):
                await idle

    asyncio.run(exercise())
