"""Object-store adapter (03 §9.1 `storage`). Keys are tenant-prefixed; nothing touches local disk."""
from __future__ import annotations

import uuid
from typing import Protocol

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


def original_key(tenant_id: uuid.UUID, project_id: uuid.UUID) -> str:
    """`{tenant}/{project}/{random}`: no filename or label, so keys carry no document content."""
    return "%s/%s/%s" % (tenant_id, project_id, uuid.uuid4())


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
        doomed = [k for k in self.objects if k.startswith(prefix)]
        for k in doomed:
            del self.objects[k]
        return len(doomed)


class S3ObjectStore:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str):
        self.bucket = bucket
        self.client = boto3.client(
            "s3", endpoint_url=endpoint, aws_access_key_id=access_key, aws_secret_access_key=secret_key,
            region_name="eu-central-1",
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                          retries={"max_attempts": 3}, connect_timeout=5, read_timeout=30),
        )

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete_prefix(self, prefix: str) -> int:
        n = 0
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            keys = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if keys:
                self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": keys})
                n += len(keys)
        return n
