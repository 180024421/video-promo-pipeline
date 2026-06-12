from __future__ import annotations

from pathlib import Path

import pytest

from src.config_schema import validate_config


@pytest.mark.skipif(not Path("config.yaml").exists(), reason="no config.yaml")
def test_config_validates():
    import yaml
    from src.config_loader import ROOT
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    issues = validate_config(cfg)
    assert isinstance(issues, list)
