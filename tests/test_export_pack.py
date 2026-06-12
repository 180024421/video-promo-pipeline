from src.export_pack import pack_job_zip


def test_pack_job_zip(tmp_path):
    (tmp_path / "demo.txt").write_text("hello", encoding="utf-8")
    cfg = {"export": {"zip_enabled": True}}
    z = pack_job_zip(tmp_path, cfg)
    assert z is not None
    assert z.exists()
