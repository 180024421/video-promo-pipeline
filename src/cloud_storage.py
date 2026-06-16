"""云存储集成：S3 / OSS / COS。"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _s3_upload(local: Path, *, endpoint: str, bucket: str, key: str, access_key: str, secret_key: str) -> str:
    import urllib.request

    url = f"{endpoint.rstrip('/')}/{bucket}/{key.lstrip('/')}"
    data = local.read_bytes()
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Content-Type", "application/octet-stream")
    import base64, hashlib, hmac

    body_hash = hashlib.sha256(data).hexdigest()
    req.add_header("x-amz-content-sha256", body_hash)
    from urllib.parse import urlparse

    parsed = urlparse(url)
    region = "us-east-1"
    scope = f"{region}/s3/aws4_request"
    import datetime as dt

    now = dt.datetime.now(dt.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    req.add_header("x-amz-date", amz_date)
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_req = f"PUT\n/{key}\n\nhost:{parsed.netloc}\nx-amz-content-sha256:{body_hash}\nx-amz-date:{amz_date}\n\n{signed_headers}\n{body_hash}"
    string_to_sign = f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n{hashlib.sha256(canonical_req.encode()).hexdigest()}"

    def sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    k_date = sign(("AWS4" + secret_key).encode(), date_stamp)
    k_region = sign(k_date, region)
    k_service = sign(k_region, "s3")
    k_signing = sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    req.add_header(
        "Authorization",
        f"AWS4-HMAC-SHA256 Credential={access_key}/{date_stamp}/{region}/s3/aws4_request,SignedHeaders={signed_headers},Signature={signature}",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        resp.read()
    return url


def _boto3_upload(local: Path, scfg: dict[str, Any], key: str) -> str:
    import boto3
    from botocore.client import Config

    client = boto3.client(
        "s3",
        endpoint_url=scfg.get("endpoint") or None,
        aws_access_key_id=scfg.get("access_key", ""),
        aws_secret_access_key=scfg.get("secret_key", ""),
        config=Config(signature_version="s3v4"),
    )
    bucket = scfg.get("bucket", "")
    client.upload_file(str(local), bucket, key.lstrip("/"))
    base = scfg.get("public_base_url", "").rstrip("/")
    if base:
        return f"{base}/{key.lstrip('/')}"
    return f"{scfg.get('endpoint', '').rstrip('/')}/{bucket}/{key.lstrip('/')}"


def upload_to_storage(local: Path, cfg: dict[str, Any], *, remote_key: str | None = None) -> dict[str, Any]:
    """上传文件到云存储，支持 S3/OSS/COS。"""
    scfg = (cfg.get("cloud_storage") or cfg.get("storage")) or {}
    if not scfg.get("enabled"):
        return {"ok": False, "detail": "云存储未启用"}

    backend = scfg.get("backend", "s3")
    endpoint = scfg.get("endpoint", "")
    bucket = scfg.get("bucket", "")
    key = remote_key or f"vpp/{local.name}"

    if scfg.get("use_boto3", False):
        try:
            url = _boto3_upload(local, scfg, key)
            return {"ok": True, "url": url, "key": key, "backend": "boto3"}
        except ImportError:
            return {"ok": False, "detail": "boto3 未安装，pip install boto3"}
        except Exception as e:
            return {"ok": False, "detail": str(e)}

    if backend in ("s3", "oss", "cos"):
        url = _s3_upload(
            local,
            endpoint=endpoint,
            bucket=bucket,
            key=key,
            access_key=scfg.get("access_key", ""),
            secret_key=scfg.get("secret_key", ""),
        )
        return {"ok": True, "url": url, "key": key}
    return {"ok": False, "detail": f"不支持的后端: {backend}"}


def upload_job_output(job_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    """上传整个 job 输出目录中所有成品文件。"""
    scfg = (cfg.get("cloud_storage") or cfg.get("storage")) or {}
    if not scfg.get("enabled"):
        return {"ok": False, "detail": "未启用"}

    results: list[dict[str, Any]] = []
    for p in sorted(job_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in {".mp4", ".srt", ".png", ".json", ".md", ".ass", ".vtt"}:
            key = f"vpp/{job_dir.name}/{p.name}"
            r = upload_to_storage(p, cfg, remote_key=key)
            results.append(r)
    return {"ok": True, "files": len(results), "results": results}
