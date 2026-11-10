"""Verify all-version deletion against local MinIO, including exact-key neighbors."""
import uuid

from changelens.storage import S3ObjectStore, original_key
from conftest import S3


def test_versioned_purge_removes_history_and_markers_without_crossing_scope(env):
    bucket = "changelens-versioned-" + uuid.uuid4().hex[:16]
    store = S3ObjectStore(S3, "changelens", "changelens-dev-only", bucket)
    tenant, other, project = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    key, sentinel = original_key(tenant, project), original_key(other, uuid.uuid4())
    neighbor = key + "-neighbor"
    store.ensure_bucket()
    try:
        store.client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
        for data in (b"first synthetic version", b"second synthetic version", b"third synthetic version"):
            store.put(key, data)
        store.client.delete_object(Bucket=bucket, Key=key)
        store.put(neighbor, b"similar prefix must survive an exact-key purge")
        store.put(sentinel, b"another tenant")
        before = store.client.list_object_versions(Bucket=bucket, Prefix=key)
        assert len(before["Versions"]) == 4 and len(before["DeleteMarkers"]) == 1
        assert store.delete_prefix(key) == 4
        remaining = store.client.list_object_versions(Bucket=bucket, Prefix=key)
        assert [entry["Key"] for entry in remaining.get("Versions", [])] == [neighbor]
        assert not remaining.get("DeleteMarkers")
        assert store.get(neighbor).startswith(b"similar prefix")
        store.delete_prefix(f"{tenant}/{project}")
        assert store.get(sentinel) == b"another tenant"
        emptied = store.client.list_object_versions(Bucket=bucket, Prefix=f"{tenant}/{project}/")
        assert not emptied.get("Versions") and not emptied.get("DeleteMarkers")
    finally:
        store.delete_prefix(str(tenant))
        store.delete_prefix(str(other))
        store.client.delete_bucket(Bucket=bucket)
