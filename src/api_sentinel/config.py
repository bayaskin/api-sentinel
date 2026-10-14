
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml

SUPPORTED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


class ConfigError(Exception):
    """Raised when an API Sentinel configuration is invalid."""


@dataclass(frozen=True)
class RequestConfig:
    method: str
    path: str


@dataclass(frozen=True)
class ExpectConfig:
    status: int


@dataclass(frozen=True)
class ApiTestConfig:
    name: str
    request: RequestConfig
    expect: ExpectConfig


@dataclass(frozen=True)
class SentinelConfig:
    base_url: str
    tests: list[ApiTestConfig]


def _require_mapping(value: object, field: str) -> dict:
    if not isinstance(value, dict):
        raise ConfigError(f"{field} must be a mapping")
    return value


def load_config(path: str | Path) -> SentinelConfig:
    """Load and validate an API Sentinel YAML configuration."""
    config_path = Path(path)

    if not config_path.is_file():
        raise ConfigError(f"Configuration file not found: {config_path}")

    try:
        with config_path.open(encoding="utf-8") as file:
            raw = yaml.safe_load(file)
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ConfigError(f"Invalid YAML: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Unable to read configuration: {exc}") from exc

    data = _require_mapping(raw, "Configuration")

    base_url = data.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        raise ConfigError("base_url must be a non-empty URL")

    parsed_url = urlparse(base_url)
    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.netloc
        or parsed_url.hostname is None
    ):
        raise ConfigError("base_url must be a valid HTTP or HTTPS URL")

    raw_tests = data.get("tests")
    if not isinstance(raw_tests, list) or not raw_tests:
        raise ConfigError("tests must be a non-empty list")

    tests: list[ApiTestConfig] = []

    for index, raw_test in enumerate(raw_tests):
        prefix = f"tests[{index}]"
        test_data = _require_mapping(raw_test, prefix)

        name = test_data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"{prefix}.name must be a non-empty string")

        request_data = _require_mapping(
            test_data.get("request"), f"{prefix}.request"
        )

        method = request_data.get("method")
        if not isinstance(method, str) or method.upper() not in SUPPORTED_METHODS:
            raise ConfigError(
                f"{prefix}.request.method must be a supported HTTP method"
            )

        request_path = request_data.get("path")
        if (
            not isinstance(request_path, str)
            or not request_path.startswith("/")
            or request_path.startswith("//")
        ):
            raise ConfigError(
                f"{prefix}.request.path must start with a single slash"
            )

        expect_data = _require_mapping(
            test_data.get("expect"), f"{prefix}.expect"
        )

        status = expect_data.get("status")
        if (
            not isinstance(status, int)
            or isinstance(status, bool)
            or not 100 <= status <= 599
        ):
            raise ConfigError(
                f"{prefix}.expect.status must be an HTTP status code from 100 to 599"
            )

        tests.append(
            ApiTestConfig(
                name=name.strip(),
                request=RequestConfig(
                    method=method.upper(),
                    path=request_path,
                ),
                expect=ExpectConfig(status=status),
            )
        )

    return SentinelConfig(base_url=base_url.rstrip("/"), tests=tests)
