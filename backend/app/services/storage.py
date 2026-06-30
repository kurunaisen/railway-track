"""Абстракция хранилища: локальный диск или MinIO/S3."""

from __future__ import annotations

import logging
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    @abstractmethod
    def save(self, content: bytes, key: str) -> str:
        """Сохраняет файл, возвращает URI (local path или s3://bucket/key)."""

    @abstractmethod
    def resolve_local_path(self, uri: str) -> Path:
        """Возвращает локальный путь для обработки (скачивает из S3 при необходимости)."""

    @abstractmethod
    def delete(self, uri: str) -> None:
        pass


class LocalStorage(StorageBackend):
    def save(self, content: bytes, key: str) -> str:
        dest = settings.upload_dir / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return str(dest)

    def resolve_local_path(self, uri: str) -> Path:
        return Path(uri)

    def delete(self, uri: str) -> None:
        p = Path(uri)
        if p.exists():
            p.unlink()


class S3Storage(StorageBackend):
    def __init__(self) -> None:
        import boto3
        from botocore.config import Config

        self._bucket = settings.s3_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint or None,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4"),
            use_ssl=settings.s3_use_ssl,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception:
            try:
                self._client.create_bucket(Bucket=self._bucket)
                logger.info("Created S3 bucket %s", self._bucket)
            except Exception as exc:
                logger.warning("Could not create bucket: %s", exc)

    def save(self, content: bytes, key: str) -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=content)
        return f"s3://{self._bucket}/{key}"

    def resolve_local_path(self, uri: str) -> Path:
        if not uri.startswith("s3://"):
            return Path(uri)
        _, rest = uri.split("s3://", 1)
        bucket, key = rest.split("/", 1)
        suffix = Path(key).suffix or ".bin"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.close()
        self._client.download_file(bucket, key, tmp.name)
        return Path(tmp.name)

    def delete(self, uri: str) -> None:
        if not uri.startswith("s3://"):
            Path(uri).unlink(missing_ok=True)
            return
        _, rest = uri.split("s3://", 1)
        bucket, key = rest.split("/", 1)
        self._client.delete_object(Bucket=bucket, Key=key)


class SupabaseStorage(StorageBackend):
    """Supabase Storage через REST API (service role), без тяжёлого SDK."""

    def __init__(self) -> None:
        import httpx

        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY обязательны для STORAGE_BACKEND=supabase")

        self._bucket = settings.supabase_storage_bucket
        self._base = settings.supabase_url.rstrip("/") + "/storage/v1"
        self._headers = {
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
        }
        self._client = httpx.Client(timeout=120.0)
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        resp = self._client.get(f"{self._base}/bucket/{self._bucket}", headers=self._headers)
        if resp.status_code == 200:
            return
        try:
            create = self._client.post(
                f"{self._base}/bucket",
                headers={**self._headers, "Content-Type": "application/json"},
                json={"id": self._bucket, "name": self._bucket, "public": False},
            )
            if create.status_code in (200, 201):
                logger.info("Created Supabase bucket %s", self._bucket)
            else:
                logger.warning("Could not create Supabase bucket: %s %s", create.status_code, create.text[:200])
        except Exception as exc:
            logger.warning("Could not create Supabase bucket: %s", exc)

    def save(self, content: bytes, key: str) -> str:
        resp = self._client.post(
            f"{self._base}/object/{self._bucket}/{key}",
            headers={
                **self._headers,
                "Content-Type": "application/octet-stream",
                "x-upsert": "true",
            },
            content=content,
        )
        resp.raise_for_status()
        return f"supabase://{self._bucket}/{key}"

    def resolve_local_path(self, uri: str) -> Path:
        if uri.startswith("supabase://"):
            _, rest = uri.split("supabase://", 1)
            bucket, key = rest.split("/", 1)
            resp = self._client.get(
                f"{self._base}/object/{bucket}/{key}",
                headers=self._headers,
            )
            resp.raise_for_status()
            suffix = Path(key).suffix or ".bin"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(resp.content)
            tmp.close()
            return Path(tmp.name)
        return Path(uri)

    def delete(self, uri: str) -> None:
        if not uri.startswith("supabase://"):
            Path(uri).unlink(missing_ok=True)
            return
        _, rest = uri.split("supabase://", 1)
        bucket, key = rest.split("/", 1)
        resp = self._client.request(
            "DELETE",
            f"{self._base}/object/{bucket}",
            headers={**self._headers, "Content-Type": "application/json"},
            json={"prefixes": [key]},
        )
        if resp.status_code not in (200, 204, 404):
            resp.raise_for_status()


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        if settings.storage_backend == "supabase":
            _storage = SupabaseStorage()
        elif settings.storage_backend == "s3":
            _storage = S3Storage()
        else:
            _storage = LocalStorage()
    return _storage
