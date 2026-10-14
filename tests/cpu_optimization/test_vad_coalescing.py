"""Compare the original model-window algorithm and exercise cancellation barriers."""

import asyncio
from threading import Event

import pytest
from pipecat.audio.vad.vad_analyzer import VADAnalyzer, VADParams


class Analyzer(VADAnalyzer):
    """Record model inputs while retaining the original VAD state machine."""

    def __init__(self):
        super().__init__(params=VADParams(start_secs=0.032, stop_secs=0.032))
        self.inputs = []
        self.set_sample_rate(8000)

    def num_frames_required(self):
        return 256

    def voice_confidence(self, buffer):
        self.inputs.append(buffer)
        return 1.0 if buffer[0] else 0.0

    def _get_smoothed_volume(self, audio):
        return 1.0


def test_given_short_chunks_when_accumulating_then_no_executor_job_is_submitted(
    monkeypatch,
):
    async def exercise():
        analyzer = Analyzer()
        monkeypatch.setattr(
            analyzer._executor,
            "submit",
            lambda *args: pytest.fail("unnecessary worker"),
        )
        try:
            await analyzer.analyze_audio(b"\x00" * 100)
            await analyzer.analyze_audio(b"\x00" * 100)
            assert analyzer._vad_buffer == b"\x00" * 200
            assert not analyzer.inputs
        finally:
            await analyzer.cleanup()

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "sizes", [[160] * 15, [512, 1024, 80, 432, 1024], [300, 300, 300, 300]]
)
def test_given_window_boundaries_when_coalescing_then_inputs_and_states_match_original(
    sizes,
):
    async def exercise():
        actual, reference = Analyzer(), Analyzer()
        try:
            for index, size in enumerate(sizes):
                chunk = bytes([index % 2]) * size
                expected = reference._run_analyzer(chunk)
                assert await actual.analyze_audio(chunk) == expected
                assert actual.inputs == reference.inputs
                assert actual._vad_buffer == reference._vad_buffer
        finally:
            await actual.cleanup()
            await reference.cleanup()

    asyncio.run(exercise())


def test_given_running_worker_when_cancelled_then_next_input_waits_for_state_barrier():
    async def exercise():
        class Blocking(Analyzer):
            def __init__(self):
                super().__init__()
                self.started, self.release = Event(), Event()

            def _run_analyzer(self, buffer):
                if not self.started.is_set():
                    self.started.set()
                    if not self.release.wait(3):
                        raise RuntimeError("test worker release timed out")
                return super()._run_analyzer(buffer)

        analyzer = Blocking()
        first = asyncio.create_task(analyzer.analyze_audio(b"\x01" * 512))
        try:
            for _ in range(100):
                if analyzer.started.is_set():
                    break
                await asyncio.sleep(0.005)
            assert analyzer.started.is_set()
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            second = asyncio.create_task(analyzer.analyze_audio(b"\x00" * 512))
            await asyncio.sleep(0.01)
            assert not second.done()
            analyzer.release.set()
            await asyncio.wait_for(second, 2)
            assert analyzer.inputs == [b"\x01" * 512, b"\x00" * 512]
        finally:
            analyzer.release.set()
            await analyzer.cleanup()

    asyncio.run(exercise())


def test_given_queued_worker_when_cancelled_then_unstarted_input_is_not_processed():
    async def exercise():
        analyzer = Analyzer()
        gate = Event()
        occupied = analyzer._executor.submit(gate.wait, 3)
        task = asyncio.create_task(analyzer.analyze_audio(b"\x01" * 512))
        try:
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            gate.set()
            await asyncio.wrap_future(occupied)
            await analyzer.analyze_audio(b"\x00" * 512)
            assert analyzer.inputs == [b"\x00" * 512]
        finally:
            gate.set()
            await analyzer.cleanup()

    asyncio.run(exercise())


def test_given_worker_error_when_analyzing_then_error_propagates_and_pending_state_is_cleared(
    monkeypatch,
):
    async def exercise():
        analyzer = Analyzer()

        def fail(buffer):
            raise ValueError("invalid model input")

        monkeypatch.setattr(analyzer, "_run_analyzer", fail)
        try:
            with pytest.raises(ValueError, match="invalid model input"):
                await analyzer.analyze_audio(b"\x00" * 512)
            assert analyzer._analysis_pending is None
        finally:
            await analyzer.cleanup()

    asyncio.run(exercise())
