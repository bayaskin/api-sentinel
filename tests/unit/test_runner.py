
import httpx

from api_sentinel.config import (
    ApiTestConfig,
    ExpectConfig,
    RequestConfig,
    SentinelConfig,
)
from api_sentinel.runner import _get_json_path, run_tests


def make_config(path: str = "/health", status: int = 200) -> SentinelConfig:
    return SentinelConfig(
        base_url="https://api.example.com",
        tests=[
            ApiTestConfig(
                name="Health endpoint",
                request=RequestConfig(method="GET", path=path),
                expect=ExpectConfig(status=status),
            )
        ],
    )


def test_passes_when_status_matches() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == "https://api.example.com/health"
        return httpx.Response(200, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    try:
        results = run_tests(make_config(), client=client)
    finally:
        client.close()

    assert len(results) == 1
    assert results[0].name == "Health endpoint"
    assert results[0].passed is True
    assert results[0].expected_status == 200
    assert results[0].actual_status == 200
    assert results[0].error is None


def test_fails_when_status_does_not_match() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    try:
        results = run_tests(make_config(status=200), client=client)
    finally:
        client.close()

    assert len(results) == 1
    assert results[0].passed is False
    assert results[0].expected_status == 200
    assert results[0].actual_status == 503
    assert "expected 200" in results[0].error


def test_continues_after_a_failed_test() -> None:
    config = SentinelConfig(
        base_url="https://api.example.com",
        tests=[
            ApiTestConfig(
                name="First endpoint",
                request=RequestConfig(method="GET", path="/first"),
                expect=ExpectConfig(status=200),
            ),
            ApiTestConfig(
                name="Second endpoint",
                request=RequestConfig(method="GET", path="/second"),
                expect=ExpectConfig(status=200),
            ),
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        status = 500 if request.url.path == "/first" else 200
        return httpx.Response(status, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    try:
        results = run_tests(config, client=client)
    finally:
        client.close()

    assert len(results) == 2
    assert results[0].passed is False
    assert results[1].passed is True


def test_records_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    try:
        results = run_tests(make_config(), client=client)
    finally:
        client.close()

    assert results[0].passed is False
    assert results[0].actual_status is None
    assert "connection refused" in results[0].error



def test_sends_headers_query_params_and_json_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == (
            "https://api.example.com/resources?page=2"
        )
        assert request.headers["accept"] == "application/json"
        assert request.headers["x-test"] == "enabled"
        assert request.headers["content-type"] == "application/json"
        assert request.read() == b'{"name":"example","enabled":true}'

        return httpx.Response(201, request=request)

    config = SentinelConfig(
        base_url="https://api.example.com",
        tests=[
            ApiTestConfig(
                name="Create resource",
                request=RequestConfig(
                    method="POST",
                    path="/resources",
                    headers={
                        "Accept": "application/json",
                        "X-Test": "enabled",
                    },
                    params={"page": "2"},
                    json={"name": "example", "enabled": True},
                ),
                expect=ExpectConfig(status=201),
            )
        ],
    )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    try:
        results = run_tests(config, client=client)
    finally:
        client.close()

    assert results[0].passed is True
    assert results[0].actual_status == 201


def test_get_json_path_returns_nested_value() -> None:
    data = {"user": {"profile": {"name": "Alex"}}}

    found, value = _get_json_path(data, "user.profile.name")

    assert found is True
    assert value == "Alex"


def test_get_json_path_returns_false_for_missing_path() -> None:
    data = {"user": {"profile": {}}}

    found, value = _get_json_path(data, "user.profile.name")

    assert found is False
    assert value is None

def test_get_json_path_returns_false_when_intermediate_value_is_not_mapping() -> None:
    data = {"user": "not-a-mapping"}

    found, value = _get_json_path(data, "user.profile.name")

    assert found is False
    assert value is None


def test_fails_when_status_mismatches_even_with_json_assertions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={"status": "error"},
            request=request,
        )

    config = SentinelConfig(
        base_url="https://api.example.com",
        tests=[
            ApiTestConfig(
                name="Status takes precedence",
                request=RequestConfig(method="GET", path="/health"),
                expect=ExpectConfig(
                    status=200,
                    json={"status": "ok"},
                ),
            )
        ],
    )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        results = run_tests(config, client=client)
    finally:
        client.close()

    assert results[0].passed is False
    assert results[0].error == "expected 200, got 500"


def test_json_assertion_distinguishes_boolean_from_integer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"enabled": True}, request=request)

    config = SentinelConfig(
        base_url="https://api.example.com",
        tests=[
            ApiTestConfig(
                name="Strict JSON types",
                request=RequestConfig(method="GET", path="/health"),
                expect=ExpectConfig(status=200, json={"enabled": 1}),
            )
        ],
    )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        results = run_tests(config, client=client)
    finally:
        client.close()

    assert results[0].passed is False
    assert "expected 1, got True" in results[0].error


def test_closes_client_created_by_runner(monkeypatch) -> None:
    created_clients = []

    class FakeClient:
        closed = False

        def __init__(self, **kwargs) -> None:
            self.closed = False
            created_clients.append(self)

        def request(self, *args, **kwargs) -> httpx.Response:
            request = httpx.Request("GET", "https://api.example.com/health")
            return httpx.Response(200, request=request)

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr("api_sentinel.runner.httpx.Client", FakeClient)

    results = run_tests(make_config())

    assert results[0].passed is True
    assert len(created_clients) == 1
    assert created_clients[0].closed is True



def test_timeout_fails_one_test_and_runner_continues() -> None:
    config = SentinelConfig(
        base_url="https://api.example.com",
        tests=[
            ApiTestConfig(
                name="Slow endpoint",
                request=RequestConfig(method="GET", path="/slow"),
                expect=ExpectConfig(status=200),
            ),
            ApiTestConfig(
                name="Healthy endpoint",
                request=RequestConfig(method="GET", path="/health"),
                expect=ExpectConfig(status=200),
            ),
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/slow":
            raise httpx.ReadTimeout("request timed out", request=request)
        return httpx.Response(200, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    try:
        results = run_tests(config, client=client)
    finally:
        client.close()

    assert len(results) == 2

    assert results[0].name == "Slow endpoint"
    assert results[0].passed is False
    assert results[0].actual_status is None
    assert "request timed out" in results[0].error

    assert results[1].name == "Healthy endpoint"
    assert results[1].passed is True
    assert results[1].actual_status == 200


