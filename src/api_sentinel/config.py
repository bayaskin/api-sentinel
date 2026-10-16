
import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

SUPPORTED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


class ConfigError(Exception):
    """Raised when an API Sentinel configuration is invalid."""


DRAFT_2020_12_SCHEMA_URI = Draft202012Validator.META_SCHEMA["$id"]
VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
PLACEHOLDER = re.compile(
    r"\$\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$\{([A-Za-z_][A-Za-z0-9_]*)\}"
)
WHOLE_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}\Z")
NO_REQUEST_BODY_OVERRIDE = object()


@dataclass(frozen=True)
class RequestConfig:
    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    json: dict | list | None = None


@dataclass(frozen=True)
class ExpectConfig:
    status: int
    json: dict[str, object] = field(default_factory=dict)
    schema: dict[str, object] | None = None


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


def _string_mapping(value: object, field: str) -> dict[str, str]:
    mapping = _require_mapping(value, field)

    for key, item in mapping.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ConfigError(f"{field} must contain only string keys and values")

    return mapping


def _json_assertions(value: object, field_name: str) -> dict[str, object]:
    assertions = _require_mapping(value, field_name)

    for path, expected in assertions.items():
        if not isinstance(path, str) or not path.strip():
            raise ConfigError(
                f"{field_name} must contain non-empty string paths"
            )

        if any(not part for part in path.split(".")):
            raise ConfigError(
                f"{field_name} contains an invalid JSON path: {path!r}"
            )

        try:
            json.dumps(expected, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ConfigError(
                f"{field_name}.{path} must contain a valid JSON value"
            ) from exc

    return assertions


def _json_schema(value: object, field_name: str) -> dict[str, object]:
    schema = _require_mapping(value, field_name)

    if (
        "$schema" in schema
        and schema["$schema"] != DRAFT_2020_12_SCHEMA_URI
    ):
        raise ConfigError(
            f"{field_name} declares an unsupported $schema dialect "
            f"{schema['$schema']!r}; only {DRAFT_2020_12_SCHEMA_URI!r} is supported"
        )

    try:
        json.dumps(schema, allow_nan=False)
        Draft202012Validator.check_schema(schema)
    except (TypeError, ValueError, SchemaError) as exc:
        detail = exc.message if isinstance(exc, SchemaError) else str(exc)
        raise ConfigError(f"{field_name} is invalid: {detail}") from exc

    return schema


def _expectation(value: object, field_name: str) -> ExpectConfig:
    expect_data = _require_mapping(value, field_name)

    status = expect_data.get("status")
    if (
        not isinstance(status, int)
        or isinstance(status, bool)
        or not 100 <= status <= 599
    ):
        raise ConfigError(
            f"{field_name}.status must be an HTTP status code from 100 to 599"
        )

    json_assertions = _json_assertions(
        expect_data.get("json", {}), f"{field_name}.json"
    )
    response_schema = None
    if "schema" in expect_data:
        response_schema = _json_schema(
            expect_data["schema"], f"{field_name}.schema"
        )

    return ExpectConfig(
        status=status,
        json=json_assertions,
        schema=response_schema,
    )


def _validate_variable_value(value: object, field_name: str) -> None:
    def is_json_value(item: object) -> bool:
        if item is None or type(item) in (str, int, bool, float):
            return True
        if isinstance(item, list):
            return all(is_json_value(child) for child in item)
        if isinstance(item, dict):
            return all(
                isinstance(key, str) and is_json_value(child)
                for key, child in item.items()
            )
        return False

    try:
        if not is_json_value(value):
            raise ValueError("value is not a JSON value")
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            f"{field_name} must contain a valid finite JSON value"
        ) from exc


def _case_variables(value: object, field_name: str) -> dict[str, object]:
    variables = _require_mapping(value, field_name)
    for name, variable_value in variables.items():
        if not isinstance(name, str):
            raise ConfigError(f"{field_name} keys must be strings")
        _validate_variable_value(variable_value, f"{field_name}.{name}")
    return variables


def _lookup_case_variable(
    name: str,
    variables: dict[str, object],
    field_name: str,
) -> object:
    if name not in variables:
        raise ConfigError(f"{field_name} references undefined variable {name!r}")
    return variables[name]


def _render_template_string(
    value: str,
    variables: dict[str, object],
    field_name: str,
) -> object:
    whole_match = WHOLE_PLACEHOLDER.fullmatch(value)
    if whole_match:
        return deepcopy(
            _lookup_case_variable(whole_match.group(1), variables, field_name)
        )

    rendered: list[str] = []
    cursor = 0
    for match in PLACEHOLDER.finditer(value):
        between = value[cursor : match.start()]
        if "${" in between:
            raise ConfigError(f"{field_name} contains malformed placeholder syntax")
        rendered.append(between)

        escaped_name, name = match.groups()
        if escaped_name is not None:
            rendered.append("${" + escaped_name + "}")
        else:
            variable_value = _lookup_case_variable(name, variables, field_name)
            if isinstance(variable_value, (dict, list)):
                raise ConfigError(
                    f"{field_name} cannot embed array or object variable {name!r}"
                )
            if isinstance(variable_value, str):
                rendered.append(variable_value)
            else:
                rendered.append(json.dumps(variable_value, allow_nan=False))
        cursor = match.end()

    remainder = value[cursor:]
    if "${" in remainder:
        raise ConfigError(f"{field_name} contains malformed placeholder syntax")
    rendered.append(remainder)
    return "".join(rendered)


def _substitute_json_values(
    value: object,
    variables: dict[str, object],
    field_name: str,
) -> object:
    if isinstance(value, dict):
        return {
            key: _substitute_json_values(child, variables, field_name)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [
            _substitute_json_values(child, variables, field_name)
            for child in value
        ]
    if isinstance(value, str):
        return _render_template_string(value, variables, field_name)
    return deepcopy(value)


def _request_config(
    prefix: str,
    method: str,
    path: str,
    headers: dict[str, str],
    params: dict[str, str],
    body: object,
) -> RequestConfig:
    if body is not None:
        if not isinstance(body, (dict, list)):
            raise ConfigError(f"{prefix}.request.json must be a mapping or list")
        try:
            json.dumps(body, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ConfigError(
                f"{prefix}.request.json must contain valid JSON values"
            ) from exc
    return RequestConfig(
        method=method.upper(),
        path=path,
        headers=deepcopy(headers),
        params=deepcopy(params),
        json=body,
    )


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

        headers = _string_mapping(
            request_data.get("headers", {}), f"{prefix}.request.headers"
        )
        params = _string_mapping(
            request_data.get("params", {}), f"{prefix}.request.params"
        )

        json_body = request_data.get("json")
        if json_body is not None:
            if not isinstance(json_body, (dict, list)):
                raise ConfigError(
                    f"{prefix}.request.json must be a mapping or list"
                )
            try:
                json.dumps(json_body, allow_nan=False)
            except (TypeError, ValueError) as exc:
                raise ConfigError(
                    f"{prefix}.request.json must contain valid JSON values"
                ) from exc

        if "cases" not in test_data:
            tests.append(
                ApiTestConfig(
                    name=name.strip(),
                    request=_request_config(
                        prefix, method, request_path, headers, params, json_body
                    ),
                    expect=_expectation(
                        test_data.get("expect"), f"{prefix}.expect"
                    ),
                )
            )
            continue

        if "expect" in test_data:
            raise ConfigError(
                f"{prefix}.expect cannot be combined with cases; define an "
                "expectation for every case"
            )

        raw_cases = test_data["cases"]
        if not isinstance(raw_cases, list) or not raw_cases:
            raise ConfigError(f"{prefix}.cases must be a non-empty list")

        for case_index, raw_case in enumerate(raw_cases):
            case_prefix = f"{prefix}.cases[{case_index}]"
            case_data = _require_mapping(raw_case, case_prefix)

            case_name = case_data.get("name")
            if not isinstance(case_name, str) or not case_name.strip():
                raise ConfigError(f"{case_prefix}.name must be a non-empty string")

            variables = _case_variables(
                case_data.get("variables"), f"{case_prefix}.variables"
            )

            case_request_data: dict = {}
            if "request" in case_data:
                case_request_data = _require_mapping(
                    case_data["request"], f"{case_prefix}.request"
                )
                unsupported_request_fields = set(case_request_data) - {"json"}
                if unsupported_request_fields:
                    field = min(unsupported_request_fields, key=str)
                    raise ConfigError(
                        f"{case_prefix}.request.{field} is not supported; "
                        "only JSON body replacement is allowed"
                    )

            override = case_request_data.get("json", NO_REQUEST_BODY_OVERRIDE)
            case_body = json_body if override is NO_REQUEST_BODY_OVERRIDE else override
            if case_body is not None:
                case_body = _substitute_json_values(
                    case_body, variables, f"{case_prefix}.request.json"
                )
            for variable_name in variables:
                if not VARIABLE_NAME.fullmatch(variable_name):
                    raise ConfigError(
                        f"{case_prefix}.variables keys must be valid "
                        "variable identifiers"
                    )

            tests.append(
                ApiTestConfig(
                    name=f"{name.strip()} / {case_name.strip()}",
                    request=_request_config(
                        prefix, method, request_path, headers, params, case_body
                    ),
                    expect=_expectation(
                        case_data.get("expect"), f"{case_prefix}.expect"
                    ),
                )
            )

    return SentinelConfig(base_url=base_url.rstrip("/"), tests=tests)
