"""Object-store adapter (03 §9.1 `storage`). Keys are tenant-prefixed; nothing touches local disk."""
from __future__ import annotations

from contextvars import ContextVar
import uuid
from typing import Protocol

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


def original_key(tenant_id: uuid.UUID, project_id: uuid.UUID) -> str:
    """`{tenant}/{project}/{random}`: no filename or label, so keys carry no document content."""
    return "%s/%s/%s" % (tenant_id, project_id, uuid.uuid4())


class StorageDeletionError(RuntimeError):
    """A content-free purge failure. A partial failure is safe to retry."""


class StorageWriteAttemptError(RuntimeError):
    """An SDK resend was blocked; callers retain the unknown-write cleanup obligation."""


def _deletion_scope(prefix: str) -> tuple[str, bool]:
    """Only canonical tenant/project scopes or an exact generated object key are deletable."""
    if not isinstance(prefix, str):
        raise ValueError("invalid_deletion_scope")
    parts = prefix.removesuffix("/").split("/")
    try:
        valid = 1 <= len(parts) <= 3 and all(str(uuid.UUID(part)) == part for part in parts)
    except (ValueError, AttributeError):
        valid = False
    if not valid:
        raise ValueError("invalid_deletion_scope")
    exact = len(parts) == 3
    if exact and prefix.endswith("/"):
        raise ValueError("invalid_deletion_scope")
    return "/".join(parts) + ("" if exact else "/"), exact


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete_prefix(self, prefix: str) -> int: ...


class MemoryObjectStore:
    """In-process store for unit tests."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        if key in self.objects:
            raise ValueError("originals are immutable")
        self.objects[key] = bytes(data)

    def get(self, key: str) -> bytes:
        return self.objects[key]

    def delete_prefix(self, prefix: str) -> int:
        prefix, exact = _deletion_scope(prefix)
        doomed = [k for k in self.objects if (k == prefix if exact else k.startswith(prefix))]
        for k in doomed:
            del self.objects[k]
        return len(doomed)


class S3ObjectStore:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str):
        self.bucket = bucket
        options = dict(endpoint_url=endpoint, aws_access_key_id=access_key, aws_secret_access_key=secret_key,
                       region_name="eu-central-1")
        def config(attempts):
            return Config(signature_version="s3v4", s3={"addressing_style": "path"},
                          retries={"total_max_attempts": attempts}, connect_timeout=5, read_timeout=30)
        self.client = boto3.client("s3", **options, config=config(4))
        # A successful automatic PUT retry does not fence a timed-out earlier PUT. Give
        # every write exactly one attempt so unknown outcomes keep their durable tombstone,
        # while an acknowledged write can safely resolve after rollback cleanup.
        self.write_client = boto3.client("s3", **options, config=config(1))
        self._put_attempts: ContextVar[int | None] = ContextVar("storage_put_attempts", default=None)
        # S3 region redirects can retry independently of total_max_attempts. Enforce the
        # invariant at before-send as well, scoped to this put() call rather than the
        # shared client, so concurrent uploads each retain their own single attempt.
        self.write_client.meta.events.register("before-send.s3.PutObject", self._guard_put_attempt)

    def _guard_put_attempt(self, **kwargs) -> None:
        if self._put_attempts.get() != 0:
            raise StorageWriteAttemptError("object_write_retry_blocked")
        self._put_attempts.set(1)

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)

    def put(self, key: str, data: bytes) -> None:
        token = self._put_attempts.set(0)
        try:
            self.write_client.put_object(Bucket=self.bucket, Key=key, Body=data)
        finally:
            self._put_attempts.reset(token)

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete_prefix(self, prefix: str) -> int:
        """Purge versions, delete markers and current objects, then verify no selected keys remain.

        One/two UUIDs select a tenant/project directory; three select an exact object for
        upload rollback. Callers must quiesce writes before a lifecycle purge. Any incomplete
        listing/deletion raises instead of reporting successful erasure. Requires version-list
        permissions even when versioning is disabled; permission failures never fall back.
        """
        prefix, exact = _deletion_scope(prefix)
        n = 0
        for operation in ("list_object_versions", "list_objects_v2"):
            for keys in self._deletion_pages(operation, prefix, exact):
                for start in range(0, len(keys), 1000):
                    batch = keys[start:start + 1000]
                    response = self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": batch, "Quiet": True})
                    if response.get("Errors"):
                        raise StorageDeletionError("object_deletion_failed")
                    n += len(batch)
        # Also catches a provider that reports successful deletion but leaves data behind,
        # pagination affected by the deletes, or a concurrent writer seen before this check.
        for operation in ("list_object_versions", "list_objects_v2"):
            for keys in self._deletion_pages(operation, prefix, exact):
                if keys:
                    raise StorageDeletionError("object_deletion_incomplete")
        return n

    def _deletion_pages(self, operation: str, prefix: str, exact: bool):
        versioned = operation == "list_object_versions"
        fields = ("Versions", "DeleteMarkers") if versioned else ("Contents",)
        for page in self.client.get_paginator(operation).paginate(Bucket=self.bucket, Prefix=prefix):
            if page.get("IsTruncated") and not page.get("NextKeyMarker" if versioned else "NextContinuationToken"):
                raise StorageDeletionError("incomplete_object_listing")
            keys = []
            for field in fields:
                entries = page.get(field, [])
                if not isinstance(entries, list):
                    raise StorageDeletionError("invalid_object_listing")
                for entry in entries:
                    if not isinstance(entry, dict):
                        raise StorageDeletionError("invalid_object_listing")
                    key = entry.get("Key")
                    if not isinstance(key, str) or not key.startswith(prefix):
                        raise StorageDeletionError("invalid_object_listing")
                    if exact and key != prefix:
                        continue  # S3 Prefix can also return neighbors of an exact leaf
                    item = {"Key": key}
                    if versioned:
                        version = entry.get("VersionId")
                        if not isinstance(version, str) or not version:
                            raise StorageDeletionError("invalid_version_listing")
                        item["VersionId"] = version  # includes S3's unversioned "null" ID
                    keys.append(item)
            yield keys
