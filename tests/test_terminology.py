from src.terminology import apply_replacements, apply_to_segments


def test_apply_replacements_case_insensitive():
    reps = {"adb": "ADB", "spring boot": "Spring Boot"}
    assert "ADB" in apply_replacements("use adb here", reps)
    assert "Spring Boot" in apply_replacements("learn spring boot", reps)


def test_apply_to_segments():
    segs = [{"start": 0, "end": 1, "text": "adb ide"}]
    out = apply_to_segments(segs, {"adb ide": "adb-ide"})
    assert out[0]["text"] == "adb-ide"
