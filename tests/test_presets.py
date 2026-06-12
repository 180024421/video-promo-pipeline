from src.presets import apply_preset, list_presets


def test_list_presets():
    presets = list_presets()
    ids = {p["id"] for p in presets}
    assert "tech_tutorial" in ids


def test_apply_preset():
    cfg = apply_preset({}, "tech_tutorial")
    assert cfg.get("workflow", {}).get("preset") == "tech_tutorial"
