
import httpx
import pytest

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


def run_response_expectation(
    expect: ExpectConfig,
    response: httpx.Response,
) -> object:
    config = SentinelConfig(
        base_url="https://api.example.com",
        tests=[
            ApiTestConfig(
                name="Response expectation",
                request=RequestConfig(method="GET", path="/health"),
                expect=expect,
            )
        ],
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: response)
    )

    try:
        return run_tests(config, client=client)[0]
    finally:
        client.close()


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


def test_passes_when_response_matches_schema() -> None:
    result = run_response_expectation(
        ExpectConfig(
            status=200,
            schema={
                "type": "object",
                "required": ["id", "name"],
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                },
            },
        ),
        httpx.Response(200, json={"id": 7, "name": "Ada"}),
    )

    assert result.passed is True
    assert result.error is None


@pytest.mark.parametrize(
    ("schema", "body"),
    [
        (
            {"type": "object", "required": ["id"]},
            {"name": "Ada"},
        ),
        (
            {"type": "object", "properties": {"id": {"type": "integer"}}},
            {"id": "7"},
        ),
    ],
    ids=["missing-required-field", "incorrect-field-type"],
)
def test_fails_when_response_does_not_match_schema(
    schema: dict,
    body: dict,
) -> None:
    result = run_response_expectation(
        ExpectConfig(status=200, schema=schema),
        httpx.Response(200, json=body),
    )

    assert result.passed is False
    assert result.error


def test_checks_nested_objects_and_array_items_in_schema() -> None:
    result = run_response_expectation(
        ExpectConfig(
            status=200,
            schema={
                "type": "object",
                "properties": {
                    "user": {
                        "type": "object",
                        "required": ["emails"],
                        "properties": {
                            "emails": {
                                "type": "array",
                                "items": {"type": "string", "format": "email"},
                            }
                        },
                    }
                },
            },
        ),
        httpx.Response(
            200,
            json={"user": {"emails": ["ada@example.com", "grace@example.org"]}},
        ),
    )

    assert result.passed is True
    assert result.error is None


def test_rejects_invalid_email_when_format_checking_is_enabled() -> None:
    result = run_response_expectation(
        ExpectConfig(
            status=200,
            schema={"type": "string", "format": "email"},
        ),
        httpx.Response(200, json="not-an-email"),
    )

    assert result.passed is False
    assert result.error


def test_fails_when_schema_response_is_not_valid_json() -> None:
    result = run_response_expectation(
        ExpectConfig(status=200, schema={"type": "object"}),
        httpx.Response(200, content=b"not json"),
    )

    assert result.passed is False
    assert result.error


def test_applies_schema_and_exact_json_assertion_together() -> None:
    result = run_response_expectation(
        ExpectConfig(
            status=200,
            json={"user.name": "Ada"},
            schema={
                "type": "object",
                "required": ["user"],
                "properties": {
                    "user": {
                        "type": "object",
                        "required": ["name", "active"],
                        "properties": {
                            "name": {"type": "string"},
                            "active": {"type": "boolean"},
                        },
                    }
                },
            },
        ),
        httpx.Response(200, json={"user": {"name": "Ada", "active": True}}),
    )

    assert result.passed is True
    assert result.error is None


def test_schema_does_not_change_status_mismatch_behavior() -> None:
    result = run_response_expectation(
        ExpectConfig(
            status=200,
            schema={"type": "object", "required": ["present"]},
        ),
        httpx.Response(500, json={}),
    )

    assert result.passed is False
    assert result.actual_status == 500
    assert result.error == "expected 200, got 500"


@pytest.mark.parametrize("expected_status", [400, 404])
def test_passes_when_expected_error_status_matches(expected_status: int) -> None:
    result = run_response_expectation(
        ExpectConfig(status=expected_status),
        httpx.Response(expected_status, json={"error": "invalid request"}),
    )

    assert result.passed is True
    assert result.expected_status == expected_status
    assert result.actual_status == expected_status
    assert result.error is None


def test_fails_when_error_response_status_is_unexpected() -> None:
    result = run_response_expectation(
        ExpectConfig(status=400),
        httpx.Response(404, json={"error": "not found"}),
    )

    assert result.passed is False
    assert result.error == "expected 400, got 404"


def test_validates_expected_error_response_with_json_and_schema() -> None:
    result = run_response_expectation(
        ExpectConfig(
            status=400,
            json={"error.code": "invalid_input"},
            schema={
                "type": "object",
                "required": ["error"],
                "properties": {
                    "error": {
                        "type": "object",
                        "required": ["code", "message"],
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                        },
                    }
                },
            },
        ),
        httpx.Response(
            400,
            json={
                "error": {
                    "code": "invalid_input",
                    "message": "The name field is required.",
                }
            },
        ),
    )

    assert result.passed is True
    assert result.error is None


def test_transport_error_fails_when_expected_status_is_400() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    config = SentinelConfig(
        base_url="https://api.example.com",
        tests=[
            ApiTestConfig(
                name="Expected bad request",
                request=RequestConfig(method="GET", path="/health"),
                expect=ExpectConfig(status=400),
            )
        ],
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))

    try:
        result = run_tests(config, client=client)[0]
    finally:
        client.close()

    assert result.passed is False
    assert result.expected_status == 400
    assert result.actual_status is None
    assert "connection refused" in result.error


def test_reports_one_schema_violation_with_path_and_constraint() -> None:
    result = run_response_expectation(
        ExpectConfig(
            status=200,
            schema={
                "type": "object",
                "properties": {
                    "profile": {
                        "type": "object",
                        "properties": {"email": {"type": "integer"}},
                    }
                },
            },
        ),
        httpx.Response(200, json={"profile": {"email": "private-value"}}),
    )

    assert result.passed is False
    assert result.error.count("response schema") == 1
    assert "$['profile']['email']" in result.error
    assert "'type' constraint" in result.error
    assert "private-value" not in result.error


def test_reports_multiple_schema_violations_below_limit() -> None:
    result = run_response_expectation(
        ExpectConfig(
            status=200,
            schema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "active": {"type": "boolean"},
                    "name": {"type": "string"},
                },
            },
        ),
        httpx.Response(200, json={"id": "bad", "active": 1, "name": False}),
    )

    assert result.passed is False
    assert result.error.count("response schema") == 3
    assert "$['id']" in result.error
    assert "$['active']" in result.error
    assert "$['name']" in result.error


def test_limits_reported_schema_violations_and_indicates_omissions() -> None:
    result = run_response_expectation(
        ExpectConfig(
            status=200,
            schema={"type": "array", "items": {"type": "string"}},
        ),
        httpx.Response(200, json=list(range(12))),
    )

    assert result.passed is False
    assert result.error.count("response schema") == 10
    assert "$[0]" in result.error
    assert "$[9]" in result.error
    assert "$[10]" not in result.error
    assert "additional schema violations omitted after 10" in result.error


