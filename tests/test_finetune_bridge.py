from __future__ import annotations

import json
from pathlib import Path

from src.finetune_bridge import apply_bridge_to_config, bridge_summary, load_bridge


def test_finetune_bridge(tmp_path: Path, monkeypatch):
    bridge_dir = tmp_path / "data"
    bridge_dir.mkdir()
    bridge_file = bridge_dir / "finetune_bridge.json"
    bridge_file.write_text(
        json.dumps({
            "recommended_lm_studio_model": "my-promo-model",
            "recommended_lora": "promo-v2",
            "eval_score": 0.88,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.finetune_bridge.BRIDGE_PATH", bridge_file)
    monkeypatch.setattr("src.finetune_bridge.load_bridge", lambda path=None: json.loads(bridge_file.read_text(encoding="utf-8")))

    cfg = {"lm_studio": {"model": ""}, "finetune": {"auto_apply_bridge": True, "bridge_file": str(bridge_file)}}
    merged = apply_bridge_to_config(cfg)
    assert merged["lm_studio"]["model"] == "my-promo-model"

    summary = bridge_summary()
    assert summary["available"] is True
    assert summary["recommended_model"] == "my-promo-model"
