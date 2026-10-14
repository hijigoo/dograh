"""Verify the process-local cache and actual Silero recurrent-state isolation."""

from concurrent.futures import ThreadPoolExecutor
from importlib import resources

import numpy as np
import pytest
from pipecat.audio.vad import cpu_session_cache as cache
from pipecat.audio.vad.silero import SileroOnnxModel


@pytest.fixture(autouse=True)
def empty_cache():
    cache._Sessions.entries.clear()
    yield
    cache._Sessions.entries.clear()


def test_given_concurrent_same_model_when_loading_then_only_one_cpu_session_is_created(
    monkeypatch, tmp_path
):
    calls = []
    session = object()

    def create_session(path, *, providers, sess_options):
        calls.append(
            (
                providers,
                sess_options.inter_op_num_threads,
                sess_options.intra_op_num_threads,
            )
        )
        return session

    monkeypatch.setattr(cache.onnxruntime, "InferenceSession", create_session)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(cache.get_cpu_session, [tmp_path / "model.onnx"] * 32)
        )

    assert all(result is session for result in results)
    assert calls == [(["CPUExecutionProvider"], 1, 1)]


def test_given_five_models_when_reusing_hot_model_then_cache_stays_bounded_and_evicts_lru(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        cache.onnxruntime, "InferenceSession", lambda *args, **kwargs: object()
    )
    paths = [tmp_path / f"{index}.onnx" for index in range(5)]
    first = cache.get_cpu_session(paths[0])
    for path in paths[1:4]:
        cache.get_cpu_session(path)
    assert cache.get_cpu_session(paths[0]) is first

    cache.get_cpu_session(paths[4])

    assert len(cache._Sessions.entries) == 4
    assert str(paths[0].resolve()) in cache._Sessions.entries
    assert str(paths[1].resolve()) not in cache._Sessions.entries


def test_given_constructor_failure_when_loading_then_failure_is_not_cached(
    monkeypatch, tmp_path
):
    def fail(*args, **kwargs):
        raise RuntimeError("invalid ONNX model")

    monkeypatch.setattr(cache.onnxruntime, "InferenceSession", fail)
    with pytest.raises(RuntimeError, match="invalid ONNX"):
        cache.get_cpu_session(tmp_path / "invalid.onnx")
    assert not cache._Sessions.entries


def test_given_same_silero_model_when_inferring_then_only_session_is_shared():
    path = str(resources.files("pipecat.audio.vad.data").joinpath("silero_vad.onnx"))
    first, second = SileroOnnxModel(path), SileroOnnxModel(path)
    untouched = second._state.copy()

    first(np.zeros(256, dtype=np.float32), 8000)

    assert first.session is second.session
    assert first._state is not second._state
    assert first._context is not second._context
    np.testing.assert_array_equal(second._state, untouched)
    first.reset_states()
    assert second._last_sr == 0


def test_given_non_cpu_provider_when_constructing_then_cache_is_not_used(monkeypatch):
    session = object()
    monkeypatch.setattr(
        cache.onnxruntime, "InferenceSession", lambda *args, **kwargs: session
    )
    monkeypatch.setattr(
        cache, "get_cpu_session", lambda path: pytest.fail("CPU cache used")
    )

    model = SileroOnnxModel("provider-model", force_onnx_cpu=False)

    assert model.session is session
    assert not cache._Sessions.entries
