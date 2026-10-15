
from dataclasses import dataclass
from itertools import islice

import httpx
from jsonschema import Draft202012Validator, FormatChecker

from api_sentinel.config import SentinelConfig

MAX_SCHEMA_ERRORS = 10


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


def _instance_path(path: list[str | int]) -> str:
    formatted = "$"
    for part in path:
        if isinstance(part, int):
            formatted += f"[{part}]"
        else:
            formatted += f"[{part!r}]"
    return formatted


def _schema_errors(schema: dict[str, object], response_json: object) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(islice(validator.iter_errors(response_json), MAX_SCHEMA_ERRORS + 1))
    has_more_errors = len(errors) > MAX_SCHEMA_ERRORS
    messages = [
        f"response schema {error.validator!r} constraint failed at "
        f"{_instance_path(list(error.path))}: expected {error.validator_value!r}"
        for error in errors[:MAX_SCHEMA_ERRORS]
    ]
    if has_more_errors:
        messages.append(
            f"additional schema violations omitted after {MAX_SCHEMA_ERRORS}"
        )
    return messages


def _json_assertion_errors(
    assertions: dict[str, object], response_json: object
) -> list[str]:
    errors = []
    for path, expected in assertions.items():
        found, actual = _get_json_path(response_json, path)

        if not found:
            errors.append(f"JSON field {path!r} was not found")
        elif type(actual) is not type(expected) or actual != expected:
            errors.append(
                f"JSON field {path!r}: expected {expected!r}, got {actual!r}"
            )
    return errors


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

                    if test.expect.json or test.expect.schema is not None:
                        try:
                            response_json = response.json()
                        except ValueError:
                            error = "response body is not valid JSON"
                        else:
                            if test.expect.schema is None:
                                assertion_errors = _json_assertion_errors(
                                    test.expect.json, response_json
                                )
                                if assertion_errors:
                                    error = assertion_errors[0]
                            else:
                                errors = _schema_errors(
                                    test.expect.schema, response_json
                                )
                                errors.extend(
                                    _json_assertion_errors(
                                        test.expect.json, response_json
                                    )
                                )
                                if errors:
                                    error = "; ".join(errors)

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
