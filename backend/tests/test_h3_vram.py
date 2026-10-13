"""H3 生成前显存预检测试。"""

import pytest

from app.services import h3_pipeline


def test_vram_enough_passes(monkeypatch):
    monkeypatch.setattr(h3_pipeline, "_gpu_free_mib_smi", lambda: 8192)
    monkeypatch.setattr(h3_pipeline, "_unload_ollama", lambda: None)
    assert h3_pipeline._ensure_h3_vram(min_free_mib=4096) == 8192


def test_vram_unload_then_enough(monkeypatch):
    values = iter([1024, 5120])
    monkeypatch.setattr(h3_pipeline, "_gpu_free_mib_smi", lambda: next(values))
    calls = {"n": 0}

    def unload():
        calls["n"] += 1

    monkeypatch.setattr(h3_pipeline, "_unload_ollama", unload)
    assert h3_pipeline._ensure_h3_vram(min_free_mib=4096) == 5120
    assert calls["n"] == 1


def test_vram_still_low_raises(monkeypatch):
    monkeypatch.setattr(h3_pipeline, "_gpu_free_mib_smi", lambda: 1000)
    monkeypatch.setattr(h3_pipeline, "_unload_ollama", lambda: None)
    with pytest.raises(RuntimeError, match="显存不足"):
        h3_pipeline._ensure_h3_vram(min_free_mib=4096)
