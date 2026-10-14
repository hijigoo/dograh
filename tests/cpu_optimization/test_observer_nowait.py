"""Exercise actual fanout queues, ordering, subclass behavior and backpressure."""

import asyncio
from contextlib import suppress

from pipecat.frames.frames import Frame
from pipecat.observers.base_observer import BaseObserver, FramePushed
from pipecat.pipeline.worker_observer import Proxy, WorkerObserver
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class RecordingQueue(asyncio.Queue):
    """Keep a subclass's custom put behavior observable."""

    def __init__(self):
        super().__init__()
        self.puts = 0

    async def put(self, item):
        self.puts += 1
        await super().put(item)


async def proxy(worker, observer, queue):
    """Use the real consumer so join and callback order are tested together."""
    task = asyncio.create_task(worker._proxy_task_handler(queue, observer))
    worker._proxies = {observer: Proxy(queue=queue, task=task, observer=observer)}
    return task


async def stop(task):
    """Close only this test's task."""
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def test_given_unbounded_queue_when_fanning_out_then_fifo_and_join_are_preserved():
    async def exercise():
        class Observer(BaseObserver):
            def __init__(self):
                super().__init__()
                self.events = []

            async def on_pipeline_started(self):
                self.events.append("start")

        worker, observer, queue = WorkerObserver(), Observer(), asyncio.Queue()
        task = await proxy(worker, observer, queue)
        try:
            await worker.on_pipeline_started()
            await worker.on_pipeline_started()
            await asyncio.wait_for(queue.join(), 2)
            assert observer.events == ["start", "start"]
            assert queue.qsize() == 0
        finally:
            await stop(task)

    asyncio.run(exercise())


def test_given_queue_subclass_when_fanning_out_then_custom_put_is_retained():
    async def exercise():
        worker, observer, queue = WorkerObserver(), BaseObserver(), RecordingQueue()
        task = await proxy(worker, observer, queue)
        try:
            await worker.on_pipeline_started()
            await asyncio.wait_for(queue.join(), 2)
            assert queue.puts == 1
        finally:
            await stop(task)

    asyncio.run(exercise())


def test_given_exact_unbounded_queue_when_sending_then_put_coroutine_is_not_called(
    monkeypatch,
):
    async def exercise():
        worker, observer, queue = WorkerObserver(), BaseObserver(), asyncio.Queue()
        task = await proxy(worker, observer, queue)

        async def forbidden_put(item):
            raise AssertionError(
                "Unbounded enqueue allocated an unnecessary put coroutine"
            )

        monkeypatch.setattr(queue, "put", forbidden_put)
        processor = FrameProcessor()
        event = FramePushed(processor, processor, Frame(), FrameDirection.DOWNSTREAM, 0)
        try:
            await worker.on_pipeline_started()
            await worker.on_push_frame(event)
            await asyncio.wait_for(queue.join(), 2)
            assert queue.empty()
        finally:
            await stop(task)

    asyncio.run(exercise())


def test_given_full_bounded_queue_when_sending_then_backpressure_and_cancellation_are_preserved():
    async def exercise():
        worker, observer, queue = (
            WorkerObserver(),
            BaseObserver(),
            asyncio.Queue(maxsize=1),
        )
        idle = asyncio.create_task(asyncio.sleep(30))
        worker._proxies = {observer: Proxy(queue=queue, task=idle, observer=observer)}
        queue.put_nowait("occupied")
        sender = asyncio.create_task(worker.on_pipeline_started())
        try:
            await asyncio.sleep(0)
            assert not sender.done()
            await stop(sender)
            assert queue.get_nowait() == "occupied"
            assert queue.empty()
        finally:
            await stop(idle)

    asyncio.run(exercise())


def test_given_repeated_push_when_observer_wants_once_then_first_push_filter_is_preserved():
    async def exercise():
        class Observer(BaseObserver):
            def __init__(self):
                super().__init__(observe_every_push=False)
                self.events = []

            async def on_push_frame(self, event):
                self.events.append(event.frame.id)

        worker, observer, queue = WorkerObserver(), Observer(), asyncio.Queue()
        task = await proxy(worker, observer, queue)
        processor, frame = FrameProcessor(), Frame()
        event = FramePushed(processor, processor, frame, FrameDirection.DOWNSTREAM, 0)
        try:
            await worker.on_push_frame(event)
            await worker.on_push_frame(event)
            await asyncio.wait_for(queue.join(), 2)
            assert observer.events == [frame.id]
        finally:
            await stop(task)

    asyncio.run(exercise())
