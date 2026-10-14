
from dataclasses import dataclass

import httpx

from api_sentinel.config import SentinelConfig


@dataclass(frozen=True)
class ApiTestResult:
    name: str
    passed: bool
    expected_status: int
    actual_status: int | None
    error: str | None = None


def _get_json_path(data: object, path: str) -> tuple[bool, object]:
    current = data

    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]

    return True, current


def run_tests(
    config: SentinelConfig,
    *,
    client: httpx.Client | None = None,
) -> list[ApiTestResult]:
    """Execute configured HTTP tests and return one result per test."""
    owns_client = client is None
    if client is None:
        client = httpx.Client(timeout=10.0, follow_redirects=True)

    results: list[ApiTestResult] = []

    try:
        for test in config.tests:
            url = f"{config.base_url.rstrip('/')}{test.request.path}"

            try:
                response = client.request(
                    test.request.method,
                    url,
                    headers=test.request.headers,
                    params=test.request.params,
                    json=test.request.json,
                    )
                actual_status = response.status_code

                if actual_status != test.expect.status:
                    error = f"expected {test.expect.status}, got {actual_status}"
                else:
                    error = None

                    if test.expect.json:
                        try:
                            response_json = response.json()
                        except ValueError:
                            error = "response body is not valid JSON"
                        else:
                            for path, expected in test.expect.json.items():
                                found, actual = _get_json_path(response_json, path)

                                if not found:
                                    error = f"JSON field {path!r} was not found"
                                    break

                                if type(actual) is not type(expected) or actual != expected:
                                    error = (
                                        f"JSON field {path!r}: expected {expected!r}, "
                                        f"got {actual!r}"
                                    )
                                    break

                results.append(
                    ApiTestResult(
                        name=test.name,
                        passed=error is None,
                        expected_status=test.expect.status,
                        actual_status=actual_status,
                        error=error,
                    )
                )
            except httpx.HTTPError as exc:
                results.append(
                    ApiTestResult(
                        name=test.name,
                        passed=False,
                        expected_status=test.expect.status,
                        actual_status=None,
                        error=str(exc),
                    )
                )
    finally:
        if owns_client:
            client.close()

    return results
