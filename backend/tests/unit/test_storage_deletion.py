"""Version-aware S3 erasure with botocore Stubber only; no network or credentials."""
import uuid

from botocore.exceptions import ClientError
from botocore.stub import Stubber
import pytest

from changelens.storage import MemoryObjectStore, S3ObjectStore, StorageDeletionError


TENANT = str(uuid.UUID(int=1))
PROJECT = str(uuid.UUID(int=2))
LEAF = str(uuid.UUID(int=3))
PREFIX = f"{TENANT}/{PROJECT}/"
KEY = PREFIX + LEAF
BUCKET = "test-only"


@pytest.fixture
def storage():
    store = S3ObjectStore("https://storage.invalid", "test-key", "test-secret", BUCKET)
    with Stubber(store.client) as stub:
        yield store, stub
        stub.assert_no_pending_responses()


def listed(stub, operation, response=None, prefix=PREFIX, **params):
    stub.add_response(operation, response or {"IsTruncated": False},
                      {"Bucket": BUCKET, "Prefix": prefix, **params})


def deleted(stub, objects, response=None):
    stub.add_response("delete_objects", response or {},
                      {"Bucket": BUCKET, "Delete": {"Objects": objects, "Quiet": True}})


def verified_empty(stub, prefix=PREFIX):
    listed(stub, "list_object_versions", prefix=prefix)
    listed(stub, "list_objects_v2", prefix=prefix)


def test_purges_all_versions_and_delete_markers_across_pages(storage):
    store, stub = storage
    old, latest, marker = ({"Key": KEY, "VersionId": version} for version in ("old", "latest", "marker"))
    listed(stub, "list_object_versions", {"Versions": [latest, old], "IsTruncated": True,
                                          "NextKeyMarker": KEY, "NextVersionIdMarker": "old"})
    deleted(stub, [latest, old])
    listed(stub, "list_object_versions", {"DeleteMarkers": [marker], "IsTruncated": False},
           KeyMarker=KEY, VersionIdMarker="old")
    deleted(stub, [marker])
    listed(stub, "list_objects_v2")
    verified_empty(stub)
    assert store.delete_prefix(PREFIX.removesuffix("/")) == 3


def test_unversioned_null_version_is_explicitly_deleted(storage):
    store, stub = storage
    item = {"Key": KEY, "VersionId": "null"}
    listed(stub, "list_object_versions", {"Versions": [item], "IsTruncated": False})
    deleted(stub, [item])
    listed(stub, "list_objects_v2")
    verified_empty(stub)
    assert store.delete_prefix(PREFIX) == 1


def test_unversioned_current_keys_are_deleted_when_version_listing_is_empty(storage):
    store, stub = storage
    listed(stub, "list_object_versions")
    listed(stub, "list_objects_v2", {"Contents": [{"Key": KEY}], "IsTruncated": False})
    deleted(stub, [{"Key": KEY}])
    verified_empty(stub)
    assert store.delete_prefix(PREFIX) == 1


def test_batches_are_limited_to_one_thousand_entries(storage):
    store, stub = storage
    versions = [{"Key": KEY, "VersionId": str(i)} for i in range(1001)]
    listed(stub, "list_object_versions", {"Versions": versions, "IsTruncated": False})
    deleted(stub, versions[:1000])
    deleted(stub, versions[1000:])
    listed(stub, "list_objects_v2")
    verified_empty(stub)
    assert store.delete_prefix(PREFIX) == 1001


def test_exact_leaf_cleanup_does_not_delete_prefix_neighbors(storage):
    store, stub = storage
    item = {"Key": KEY, "VersionId": "v1"}
    neighbor = {"Key": KEY + "-neighbor", "VersionId": "v2"}
    listed(stub, "list_object_versions", {"Versions": [item, neighbor]}, prefix=KEY)
    deleted(stub, [item])
    listed(stub, "list_objects_v2", {"Contents": [{"Key": neighbor["Key"]}]}, prefix=KEY)
    listed(stub, "list_object_versions", {"Versions": [neighbor]}, prefix=KEY)
    listed(stub, "list_objects_v2", {"Contents": [{"Key": neighbor["Key"]}]}, prefix=KEY)
    assert store.delete_prefix(KEY) == 1


@pytest.mark.parametrize("scope", ["", "/", TENANT[:12], "../" + TENANT, TENANT + "//",
                                   f"{TENANT}/not-a-project", KEY + "/", KEY + "/extra"])
def test_invalid_scopes_are_refused_before_any_request(storage, scope):
    store, _ = storage
    with pytest.raises(ValueError, match="invalid_deletion_scope"):
        store.delete_prefix(scope)


def test_partial_batch_error_is_not_reported_as_success_or_leaked(storage):
    store, stub = storage
    item = {"Key": KEY, "VersionId": "v1"}
    listed(stub, "list_object_versions", {"Versions": [item]})
    deleted(stub, [item], {"Errors": [{**item, "Code": "AccessDenied", "Message": "PRIVATE-MARKER"}]})
    with pytest.raises(StorageDeletionError, match="object_deletion_failed") as error:
        store.delete_prefix(PREFIX)
    assert "PRIVATE-MARKER" not in str(error.value) and KEY not in str(error.value)


def test_version_listing_permission_error_never_falls_back_to_current_keys(storage):
    store, stub = storage
    stub.add_client_error("list_object_versions", service_error_code="AccessDenied",
                          expected_params={"Bucket": BUCKET, "Prefix": PREFIX})
    with pytest.raises(ClientError):
        store.delete_prefix(PREFIX)


def test_provider_reported_success_with_leftover_version_is_failure(storage):
    store, stub = storage
    item = {"Key": KEY, "VersionId": "old"}
    listed(stub, "list_object_versions", {"Versions": [item]})
    deleted(stub, [item])
    listed(stub, "list_objects_v2")
    listed(stub, "list_object_versions", {"Versions": [item]})
    with pytest.raises(StorageDeletionError, match="object_deletion_incomplete"):
        store.delete_prefix(PREFIX)


def test_leftover_current_object_fails_final_verification(storage):
    store, stub = storage
    listed(stub, "list_object_versions")
    listed(stub, "list_objects_v2")
    listed(stub, "list_object_versions")
    listed(stub, "list_objects_v2", {"Contents": [{"Key": KEY}]})
    with pytest.raises(StorageDeletionError, match="object_deletion_incomplete"):
        store.delete_prefix(PREFIX)


def test_out_of_scope_listing_never_reaches_delete(storage):
    store, stub = storage
    listed(stub, "list_object_versions", {"Versions": [{"Key": "other-tenant/private", "VersionId": "v1"}]})
    with pytest.raises(StorageDeletionError, match="invalid_object_listing"):
        store.delete_prefix(PREFIX)


def test_version_id_is_required_even_for_unversioned_objects(storage):
    store, stub = storage
    listed(stub, "list_object_versions", {"Versions": [{"Key": KEY}]})
    with pytest.raises(StorageDeletionError, match="invalid_version_listing"):
        store.delete_prefix(PREFIX)


def test_truncated_listing_without_continuation_marker_fails(storage):
    store, stub = storage
    listed(stub, "list_object_versions", {"IsTruncated": True})
    with pytest.raises(StorageDeletionError, match="incomplete_object_listing"):
        store.delete_prefix(PREFIX)


def test_memory_store_uses_identical_scope_boundaries():
    store = MemoryObjectStore()
    neighbor = KEY + "-neighbor"
    sibling_project = f"{TENANT}/{uuid.UUID(int=4)}/{LEAF}"
    sibling_tenant = f"{uuid.UUID(int=5)}/{PROJECT}/{LEAF}"
    for key in (KEY, neighbor, sibling_project, sibling_tenant):
        store.put(key, b"synthetic")
    assert store.delete_prefix(KEY) == 1 and neighbor in store.objects
    assert store.delete_prefix(PREFIX) == 1 and sibling_project in store.objects
    assert store.delete_prefix(TENANT) == 1 and set(store.objects) == {sibling_tenant}
    with pytest.raises(ValueError):
        store.delete_prefix("")
