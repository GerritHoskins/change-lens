"""The Logto Management client for account deletion (I-8 S5), over `httpx.MockTransport`."""
import httpx
import pytest

from changelens.auth.logto_management import DevIdp, IdpDeletionFailed, LogtoManagement, idp_for
from changelens.config import Settings

ENDPOINT = "https://auth.example.test"
APP_CRED = "m2m-secret-0123456789"


class Logto:
    def __init__(self, delete_status=204, token_status=200, expires_in=3600):
        self.delete_status, self.token_status, self.expires_in = delete_status, token_status, expires_in
        self.requests = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/oidc/token":
            assert request.method == "POST" and request.headers["authorization"].startswith("Basic ")
            body = dict(x.split("=", 1) for x in request.content.decode().split("&"))
            assert body["grant_type"] == "client_credentials" and body["scope"] == "all"
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={"error": "nope " + APP_CRED})
            return httpx.Response(200, json={"access_token": "mgmt-token", "expires_in": self.expires_in})
        assert request.method == "DELETE" and request.headers["authorization"] == "Bearer mgmt-token"
        return httpx.Response(self.delete_status, text="body with user-123")


def client(fake, now=None):
    clock = (lambda: now[0]) if now else None
    kwargs = {"clock": clock} if clock else {}
    return LogtoManagement(ENDPOINT, "m2m-app", APP_CRED, client=httpx.Client(transport=httpx.MockTransport(fake.handler)),
                           **kwargs)


@pytest.mark.parametrize("status", [200, 204, 404])
def test_delete_succeeds_and_a_missing_user_counts_as_done(status):
    fake = Logto(delete_status=status)
    client(fake).delete_user("user-123")
    assert [r.url.path for r in fake.requests] == ["/oidc/token", "/api/users/user-123"]


def test_the_management_token_is_reused_until_shortly_before_expiry():
    fake, now = Logto(expires_in=120), [0.0]
    c = client(fake, now)
    c.delete_user("a"), c.delete_user("b")
    now[0] = 100.0  # within 30 s of expiry
    c.delete_user("c")
    assert [r.url.path for r in fake.requests].count("/oidc/token") == 2


@pytest.mark.parametrize("fake,code", [
    (Logto(delete_status=500), "delete_status_500"),
    (Logto(delete_status=403), "delete_status_403"),
    (Logto(token_status=401), "token_status_401"),
])
def test_failures_raise_an_event_code_without_secrets_or_bodies(fake, code):
    with pytest.raises(IdpDeletionFailed) as error:
        client(fake).delete_user("user-123")
    assert str(error.value) == code
    assert APP_CRED not in repr(error.value) and "user-123" not in str(error.value)


def test_network_errors_and_odd_subjects_never_reach_logto():
    def down(request):
        raise httpx.ConnectError("refused")
    c = LogtoManagement(ENDPOINT, "m2m-app", APP_CRED, client=httpx.Client(transport=httpx.MockTransport(down)))
    with pytest.raises(IdpDeletionFailed, match="token_unreachable:ConnectError"):
        c.delete_user("user-123")
    fake = Logto()
    for subject in ("", "../admin", "a/b", "x" * 201, None):
        with pytest.raises(IdpDeletionFailed, match="invalid_subject"):
            client(fake).delete_user(subject)
    assert fake.requests == []
    assert APP_CRED not in repr(c)


def test_settings_choose_the_idp_and_validate_the_management_endpoint():
    base = dict(database_url="x", s3_endpoint="x", s3_access_key="x", s3_secret_key="x", s3_bucket="x")
    assert isinstance(idp_for(Settings(**base)), DevIdp)
    logto = dict(base, auth_mode="logto", logto_issuer="https://i", logto_audience="a",
                 logto_jwks_url="https://i/jwks")
    assert idp_for(Settings(**logto)) is None  # not configured: the IdP step stays pending
    configured = Settings(**logto, logto_management_endpoint=ENDPOINT, logto_m2m_app_id="m2m-app",
                          logto_m2m_app_secret=APP_CRED)
    assert isinstance(idp_for(configured), LogtoManagement) and APP_CRED not in repr(configured)
    for bad in ({"logto_management_endpoint": "http://auth"}, {"logto_management_endpoint": ENDPOINT}):
        with pytest.raises(ValueError):
            Settings(**logto, **bad)
