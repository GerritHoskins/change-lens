"""Exercise botocore's real retry handler with its HTTP send boundary replaced in memory."""
import pytest
from botocore.awsrequest import AWSResponse
from botocore.exceptions import ClientError, ReadTimeoutError

from changelens.storage import S3ObjectStore, StorageWriteAttemptError


@pytest.mark.parametrize("failure", ["http_500", "timeout"])
def test_put_has_one_sdk_attempt_while_reads_and_deletes_keep_retries(monkeypatch, failure):
    store = S3ObjectStore("http://127.0.0.1:1", "test-key", "test-secret", "synthetic-bucket")
    assert store.write_client.meta.config.retries["total_max_attempts"] == 1
    assert store.client.meta.config.retries["total_max_attempts"] == 4
    sent = []

    class RawResponse:
        def stream(self, *args, **kwargs):
            yield b"<Error><Code>InternalError</Code><Message>Synthetic failure</Message></Error>"

    def send(request):
        sent.append(request.method)
        if failure == "timeout":
            raise ReadTimeoutError(endpoint_url="http://127.0.0.1:1")
        return AWSResponse(request.url, 500, {"Content-Type": "application/xml"}, RawResponse())

    def forbidden(*args, **kwargs):
        raise AssertionError("PUT must never use the retrying read/delete client")

    monkeypatch.setattr(store.write_client._endpoint.http_session, "send", send)
    monkeypatch.setattr(store.client._endpoint.http_session, "send", forbidden)
    error_type = ReadTimeoutError if failure == "timeout" else ClientError
    with pytest.raises(error_type):
        store.put("synthetic-key", b"Synthetic content")
    assert sent == ["PUT"]


class Raw:
    def __init__(self, body=b""):
        self.body = body

    def stream(self, *args, **kwargs):
        yield self.body


def test_region_redirect_cannot_bypass_single_put_attempt_and_next_call_still_works(monkeypatch):
    store = S3ObjectStore("http://127.0.0.1:1", "test-key", "test-secret", "synthetic-bucket")
    sent = []

    def send(request):
        sent.append(request.method)
        if len(sent) == 1:
            # botocore's S3RegionRedirector otherwise resends despite total_max_attempts=1.
            return AWSResponse(request.url, 301,
                {"Content-Type": "application/xml", "x-amz-bucket-region": "eu-west-1"},
                Raw(b"<Error><Code>PermanentRedirect</Code><Message>Synthetic redirect</Message></Error>"))
        return AWSResponse(request.url, 200, {}, Raw())

    monkeypatch.setattr(store.write_client._endpoint.http_session, "send", send)
    with pytest.raises(StorageWriteAttemptError, match="^object_write_retry_blocked$"):
        store.put("synthetic-key", b"Synthetic content")
    assert sent == ["PUT"]
    store.put("second-synthetic-key", b"Synthetic content")
    assert sent == ["PUT", "PUT"]


def test_concurrent_put_calls_have_independent_attempt_guards(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    store = S3ObjectStore("http://127.0.0.1:1", "test-key", "test-secret", "synthetic-bucket")
    together, sent = Barrier(2), []

    def send(request):
        sent.append(request.method)
        together.wait(timeout=5)
        return AWSResponse(request.url, 200, {}, Raw())

    monkeypatch.setattr(store.write_client._endpoint.http_session, "send", send)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(store.put, f"synthetic-{i}", b"Synthetic content") for i in range(2)]
        for result in results:
            assert result.result(timeout=10) is None
    assert sent == ["PUT", "PUT"]
