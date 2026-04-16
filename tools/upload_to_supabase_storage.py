"""
Generic Supabase Storage uploader.

Uploads local files to a public Supabase Storage bucket and prints the
resulting public URLs (one per line, in the same order as the input files).

Creates the target bucket if it does not already exist. Overwrites existing
objects at the same key (idempotent).

Usage:
    python tools/upload_to_supabase_storage.py \\
        --bucket avm-public \\
        --prefix carousels/ai-misconceptions-2026-04-14 \\
        path/to/slide1.png path/to/slide2.png path/to/slide3.png

Environment variables required (loaded from .env):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

from __future__ import annotations

import argparse
import mimetypes
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import httpx
from dotenv import load_dotenv


@dataclass(frozen=True)
class SupabaseStorageConfig:
    base_url: str
    service_role_key: str

    @classmethod
    def from_env(cls) -> "SupabaseStorageConfig":
        load_dotenv(Path(__file__).parent.parent / ".env")
        base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not base_url:
            raise RuntimeError("SUPABASE_URL is not set in .env")
        if not key:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not set in .env")
        return cls(base_url=base_url, service_role_key=key)

    @property
    def storage_api(self) -> str:
        return f"{self.base_url}/storage/v1"

    def auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.service_role_key}",
            "apikey": self.service_role_key,
        }


def ensure_bucket(cfg: SupabaseStorageConfig, bucket: str, *, public: bool = True) -> None:
    """Create the bucket if it does not already exist. No-op if it exists."""
    with httpx.Client(timeout=30) as client:
        list_resp = client.get(
            f"{cfg.storage_api}/bucket",
            headers=cfg.auth_headers(),
        )
        list_resp.raise_for_status()
        existing = {b.get("id") for b in list_resp.json() if isinstance(b, dict)}
        if bucket in existing:
            return

        create_resp = client.post(
            f"{cfg.storage_api}/bucket",
            headers={**cfg.auth_headers(), "Content-Type": "application/json"},
            json={"id": bucket, "name": bucket, "public": public},
        )
        if create_resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to create bucket '{bucket}': "
                f"{create_resp.status_code} {create_resp.text}"
            )


def upload_file(
    cfg: SupabaseStorageConfig,
    bucket: str,
    key: str,
    file_path: Path,
) -> str:
    """Upload a single file, overwriting any existing object at that key.

    Returns the public URL (only valid if the bucket is public).
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    content_type, _ = mimetypes.guess_type(str(file_path))
    content_type = content_type or "application/octet-stream"

    headers = {
        **cfg.auth_headers(),
        "Content-Type": content_type,
        "x-upsert": "true",
    }

    with httpx.Client(timeout=120) as client:
        with file_path.open("rb") as fh:
            resp = client.post(
                f"{cfg.storage_api}/object/{bucket}/{key}",
                headers=headers,
                content=fh.read(),
            )

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Upload failed for {file_path.name} -> {bucket}/{key}: "
            f"{resp.status_code} {resp.text}"
        )

    return f"{cfg.base_url}/storage/v1/object/public/{bucket}/{key}"


def upload_many(
    *,
    bucket: str,
    prefix: str,
    files: Sequence[Path],
    ensure: bool = True,
) -> list[str]:
    cfg = SupabaseStorageConfig.from_env()
    if ensure:
        ensure_bucket(cfg, bucket, public=True)

    urls: list[str] = []
    for file_path in files:
        key = f"{prefix.strip('/')}/{file_path.name}" if prefix else file_path.name
        public_url = upload_file(cfg, bucket, key, file_path)
        urls.append(public_url)
    return urls


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload files to a public Supabase Storage bucket and print public URLs."
    )
    parser.add_argument(
        "--bucket",
        required=True,
        help="Target Supabase Storage bucket (created if missing).",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="Optional key prefix inside the bucket (e.g. carousels/ai-misconceptions-2026-04-14).",
    )
    parser.add_argument(
        "--no-ensure-bucket",
        action="store_true",
        help="Skip bucket creation check (assumes bucket exists).",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="One or more local file paths to upload.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    files = [Path(p) for p in args.files]
    missing = [p for p in files if not p.exists()]
    if missing:
        for p in missing:
            print(f"ERROR: file not found: {p}", file=sys.stderr)
        return 2

    try:
        urls = upload_many(
            bucket=args.bucket,
            prefix=args.prefix,
            files=files,
            ensure=not args.no_ensure_bucket,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for url in urls:
        print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
