
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
                response = client.request(test.request.method, url)
                actual_status = response.status_code

                if actual_status == test.expect.status:
                    results.append(
                        ApiTestResult(
                            name=test.name,
                            passed=True,
                            expected_status=test.expect.status,
                            actual_status=actual_status,
                        )
                    )
                else:
                    results.append(
                        ApiTestResult(
                            name=test.name,
                            passed=False,
                            expected_status=test.expect.status,
                            actual_status=actual_status,
                            error=(
                                f"expected {test.expect.status}, "
                                f"got {actual_status}"
                            ),
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
