
import json
from pathlib import Path

import pytest
import yaml

from api_sentinel.config import ConfigError, load_config


def test_loads_valid_configuration(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        """
base_url: https://api.example.com
tests:
  - name: Health endpoint
    request:
      method: GET
      path: /health
    expect:
      status: 200
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.base_url == "https://api.example.com"
    assert len(config.tests) == 1
    assert config.tests[0].name == "Health endpoint"
    assert config.tests[0].request.method == "GET"
    assert config.tests[0].request.path == "/health"
    assert config.tests[0].expect.status == 200


def test_rejects_missing_tests(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        "base_url: https://api.example.com\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="tests"):
        load_config(config_file)


def test_rejects_unsupported_http_method(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        """
base_url: https://api.example.com
tests:
  - name: Invalid request
    request:
      method: TRACE
      path: /health
    expect:
      status: 200
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="method"):
        load_config(config_file)


def test_rejects_invalid_status_code(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        """
base_url: https://api.example.com
tests:
  - name: Invalid expectation
    request:
      method: GET
      path: /health
    expect:
      status: 99
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="status"):
        load_config(config_file)


def test_rejects_non_mapping_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text("- just\n- a\n- list\n", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(config_file)


def test_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.yaml")



@pytest.mark.parametrize(
    "base_url",
    [
        "ftp://api.example.com",
        "not-a-url",
        "https://",
        "",
    ],
)
def test_rejects_invalid_base_url(tmp_path: Path, base_url: str) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        f"""
base_url: "{base_url}"
tests:
  - name: Health endpoint
    request:
      method: GET
      path: /health
    expect:
      status: 200
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="base_url"):
        load_config(config_file)


def test_rejects_malformed_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        "base_url: [unterminated\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_config(config_file)


def test_rejects_missing_request_method(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        """
base_url: https://api.example.com
tests:
  - name: Health endpoint
    request:
      path: /health
    expect:
      status: 200
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="method"):
        load_config(config_file)


def test_rejects_network_path_reference(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        """
base_url: https://api.example.com
tests:
  - name: Invalid path
    request:
      method: GET
      path: //other.example.com/health
    expect:
      status: 200
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="path"):
        load_config(config_file)


def test_rejects_empty_tests_list(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        """
base_url: https://api.example.com
tests: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="tests"):
        load_config(config_file)



def test_loads_request_options(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        """
base_url: https://api.example.com
tests:
  - name: Create resource
    request:
      method: POST
      path: /resources
      headers:
        Accept: application/json
        X-Test: enabled
      params:
        page: "2"
      json:
        name: example
        enabled: true
    expect:
      status: 201
""",
        encoding="utf-8",
    )

    config = load_config(config_file)
    request = config.tests[0].request

    assert request.headers == {
        "Accept": "application/json",
        "X-Test": "enabled",
    }
    assert request.params == {"page": "2"}
    assert request.json == {"name": "example", "enabled": True}


def test_optional_request_options_default_to_empty() -> None:
    from api_sentinel.config import RequestConfig

    request = RequestConfig(method="GET", path="/health")

    assert request.headers == {}
    assert request.params == {}
    assert request.json is None


def test_rejects_non_string_header_values(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        """
base_url: https://api.example.com
tests:
  - name: Invalid headers
    request:
      method: GET
      path: /health
      headers:
        X-Retry: 3
    expect:
      status: 200
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="headers"):
        load_config(config_file)


def test_rejects_invalid_json_body(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        """
base_url: https://api.example.com
tests:
  - name: Invalid body
    request:
      method: POST
      path: /resources
      json: "not an object"
    expect:
      status: 201
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="request.json"):
        load_config(config_file)


def test_rejects_invalid_json_assertion_path(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        """
base_url: https://api.example.com
tests:
  - name: Invalid assertion
    request:
      method: GET
      path: /health
    expect:
      status: 200
      json:
        "user..name": example
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="invalid JSON path"):
        load_config(config_file)


def test_rejects_whitespace_only_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text("   \n\n\t  \n", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(config_file)


def test_loads_schema_and_existing_json_assertions_together(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        """
base_url: https://api.example.com
tests:
  - name: Schema and exact assertion
    request:
      method: GET
      path: /users/1
    expect:
      status: 200
      schema:
        type: object
        required: [id, email]
        properties:
          id:
            type: integer
          email:
            type: string
      json:
        id: 7
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.tests[0].expect.schema == {
        "type": "object",
        "required": ["id", "email"],
        "properties": {
            "id": {"type": "integer"},
            "email": {"type": "string"},
        },
    }
    assert config.tests[0].expect.json == {"id": 7}


@pytest.mark.parametrize("schema", ['"a string"', "42", "true", "[]", "null"])
def test_rejects_non_mapping_schema(tmp_path: Path, schema: str) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        f"""
base_url: https://api.example.com
tests:
  - name: Invalid schema shape
    request:
      method: GET
      path: /users/1
    expect:
      status: 200
      schema: {schema}
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match=r"schema.*mapping|mapping.*schema"):
        load_config(config_file)


def test_rejects_invalid_schema_definition(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        """
base_url: https://api.example.com
tests:
  - name: Invalid schema definition
    request:
      method: GET
      path: /users/1
    expect:
      status: 200
      schema:
        type: not-a-json-schema-type
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match=r"schema.*invalid|invalid.*schema"):
        load_config(config_file)


def test_configuration_without_schema_remains_valid(tmp_path: Path) -> None:
    config_file = tmp_path / "tests.yaml"
    config_file.write_text(
        """
base_url: https://api.example.com
tests:
  - name: Existing status and JSON assertion
    request:
      method: GET
      path: /health
    expect:
      status: 200
      json:
        status: ok
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.tests[0].expect.status == 200
    assert config.tests[0].expect.json == {"status": "ok"}


def _load_schema_config(tmp_path: Path, schema_yaml: str):
    config_file = tmp_path / "schema.yaml"
    config_file.write_text(
        f"""
base_url: https://api.example.com
tests:
  - name: Schema dialect
    request:
      method: GET
      path: /health
    expect:
      status: 200
      schema:
{schema_yaml}
""",
        encoding="utf-8",
    )
    return load_config(config_file)


def test_schema_without_dialect_uses_draft_2020_12(tmp_path: Path) -> None:
    config = _load_schema_config(tmp_path, "        type: object\n")

    assert config.tests[0].expect.schema == {"type": "object"}


def test_accepts_official_draft_2020_12_schema_uri(tmp_path: Path) -> None:
    config = _load_schema_config(
        tmp_path,
        "        $schema: https://json-schema.org/draft/2020-12/schema\n"
        "        type: object\n",
    )

    assert config.tests[0].expect.schema["$schema"] == (
        "https://json-schema.org/draft/2020-12/schema"
    )


def test_rejects_draft_7_schema_uri_as_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="unsupported \\$schema dialect"):
        _load_schema_config(
            tmp_path,
            "        $schema: http://json-schema.org/draft-07/schema#\n"
            "        type: object\n",
        )


@pytest.mark.parametrize("dialect", ['""', "not-a-uri", "123", "[]", "null"])
def test_rejects_unsupported_or_malformed_schema_dialect(
    tmp_path: Path,
    dialect: str,
) -> None:
    with pytest.raises(ConfigError, match="unsupported \\$schema dialect"):
        _load_schema_config(
            tmp_path,
            f"        $schema: {dialect}\n        type: object\n",
        )


_NO_BODY = object()


def _load_case_config(
    tmp_path: Path,
    cases: object,
    *,
    request_json: object = _NO_BODY,
    request_fields: dict[str, object] | None = None,
):
    request = {
        "method": "POST",
        "path": "/items",
        **(request_fields or {}),
    }
    if request_json is not _NO_BODY:
        request["json"] = request_json
    raw = {
        "base_url": "https://api.example.com",
        "tests": [{
            "name": "Create item",
            "request": request,
            "cases": cases,
        }],
    }
    config_file = tmp_path / "cases.yaml"
    config_file.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_config(config_file)


def _case(name: str, variables: dict[str, object], **extra: object) -> dict:
    return {
        "name": name,
        "variables": variables,
        "expect": {"status": 201},
        **extra,
    }


def test_existing_non_case_configuration_still_loads_unchanged(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "existing.yaml"
    config_file.write_text(
        """
base_url: https://api.example.com
tests:
  - name: Existing JSON check
    request:
      method: GET
      path: /users/7
      params: {view: full}
      json: {enabled: true}
    expect:
      status: 200
      json: {user.active: true}
      schema:
        type: object
        required: [user]
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert len(config.tests) == 1
    test = config.tests[0]
    assert test.name == "Existing JSON check"
    assert test.request.method == "GET"
    assert test.request.path == "/users/7"
    assert test.request.params == {"view": "full"}
    assert test.request.json == {"enabled": True}
    assert test.expect.status == 200
    assert test.expect.json == {"user.active": True}
    assert test.expect.schema == {"type": "object", "required": ["user"]}


def test_expands_cases_in_order_with_qualified_names(tmp_path: Path) -> None:
    config = _load_case_config(
        tmp_path,
        [_case("first", {"value": "one"}), _case("second", {"value": "two"})],
        request_json={"value": "${value}"},
    )

    assert [test.name for test in config.tests] == [
        "Create item / first",
        "Create item / second",
    ]
    assert [test.request.json for test in config.tests] == [
        {"value": "one"},
        {"value": "two"},
    ]


@pytest.mark.parametrize(
    "case",
    [
        {"name": "no expectation", "variables": {}},
        {"name": "missing status", "variables": {}, "expect": {}},
    ],
    ids=["missing-expect", "incomplete-expect"],
)
def test_requires_complete_expectation_for_each_case(
    tmp_path: Path,
    case: dict,
) -> None:
    with pytest.raises(ConfigError, match="case.*expect|case.*status"):
        _load_case_config(tmp_path, [case])


@pytest.mark.parametrize(
    "cases",
    [None, "not-a-list", {"name": "case"}, ["not-a-case-mapping"], []],
    ids=["null", "string", "mapping", "wrong-item", "empty"],
)
def test_rejects_malformed_or_empty_cases(tmp_path: Path, cases: object) -> None:
    with pytest.raises(ConfigError, match="cases"):
        _load_case_config(tmp_path, cases)


@pytest.mark.parametrize(
    "case_name",
    [None, 7, "", "   "],
    ids=["null", "number", "empty", "whitespace"],
)
def test_rejects_missing_or_invalid_case_names(
    tmp_path: Path,
    case_name: object,
) -> None:
    case = _case("placeholder", {})
    case["name"] = case_name
    with pytest.raises(ConfigError, match="name"):
        _load_case_config(tmp_path, [case])


def test_rejects_case_without_name_or_variables(tmp_path: Path) -> None:
    case = {"expect": {"status": 201}}
    with pytest.raises(ConfigError, match="name"):
        _load_case_config(tmp_path, [case])

    case["name"] = "missing variables"
    with pytest.raises(ConfigError, match="variables"):
        _load_case_config(tmp_path, [case])


@pytest.mark.parametrize("variables", [None, "values", ["x"], 3])
def test_rejects_non_mapping_case_variables(
    tmp_path: Path,
    variables: object,
) -> None:
    case = _case("invalid variables", {})
    case["variables"] = variables
    with pytest.raises(ConfigError, match="variables"):
        _load_case_config(tmp_path, [case])


def test_rejects_undefined_case_variable(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="undefined|variable"):
        _load_case_config(
            tmp_path,
            [_case("missing variable", {})],
            request_json={"name": "${name}"},
        )


def test_case_variables_do_not_leak_between_cases(tmp_path: Path) -> None:
    cases = [
        _case("defines value", {"name": "Ada"}),
        _case("cannot reuse value", {}),
    ]

    with pytest.raises(ConfigError, match="undefined variable.*name"):
        _load_case_config(
            tmp_path,
            cases,
            request_json={"name": "${name}"},
        )


def test_accepts_explicit_null_and_unused_variable(tmp_path: Path) -> None:
    config = _load_case_config(
        tmp_path,
        [_case("null is present", {"value": None, "unused": "allowed"})],
        request_json={"value": "${value}"},
    )

    assert config.tests[0].request.json == {"value": None}


@pytest.mark.parametrize(
    "expected",
    ["text", 12, 1.25, True, None, [1, "two"], {"nested": False}],
    ids=["string", "integer", "finite-number", "boolean", "null", "array", "object"],
)
def test_whole_value_placeholder_preserves_json_type(
    tmp_path: Path,
    expected: object,
) -> None:
    config = _load_case_config(
        tmp_path,
        [_case("typed value", {"value": expected})],
        request_json={"value": "${value}"},
    )

    value = config.tests[0].request.json["value"]
    assert type(value) is type(expected)
    assert value == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [("Ada", "hello Ada"), (12, "hello 12"), (True, "hello true"), (None, "hello null")],
    ids=["string", "number", "boolean", "null"],
)
def test_embedded_placeholder_uses_json_scalar_text(
    tmp_path: Path,
    value: object,
    expected: str,
) -> None:
    config = _load_case_config(
        tmp_path,
        [_case("embedded value", {"value": value})],
        request_json={"message": "hello ${value}"},
    )

    assert config.tests[0].request.json == {"message": expected}


@pytest.mark.parametrize("value", [1.25, 1.25e-10], ids=["decimal", "exponent"])
def test_embedded_number_placeholder_uses_valid_json_number_text(
    tmp_path: Path,
    value: float,
) -> None:
    config = _load_case_config(
        tmp_path,
        [_case("embedded number", {"value": value})],
        request_json={"message": "value=${value}"},
    )

    rendered = config.tests[0].request.json["message"]
    number_text = rendered.removeprefix("value=")
    assert json.loads(number_text) == value


def test_parent_expectation_is_not_inherited_by_cases(tmp_path: Path) -> None:
    raw = {
        "base_url": "https://api.example.com",
        "tests": [{
            "name": "Create item",
            "request": {"method": "POST", "path": "/items"},
            "expect": {"status": 201},
            "cases": [{"name": "missing own expectation", "variables": {}}],
        }],
    }
    config_file = tmp_path / "parent-expectation.yaml"
    config_file.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(ConfigError, match="expect cannot be combined with cases"):
        load_config(config_file)


@pytest.mark.parametrize(
    ("case_request", "message"),
    [
        ("not-a-mapping", r"cases\[0\]\.request must be a mapping"),
        ({"json": "not-a-json-object"}, r"request\.json must be a mapping or list"),
    ],
    ids=["non-mapping-request", "invalid-json-override"],
)
def test_rejects_malformed_case_request_overrides(
    tmp_path: Path,
    case_request: object,
    message: str,
) -> None:
    case = _case("invalid override", {})
    case["request"] = case_request

    with pytest.raises(ConfigError, match=message):
        _load_case_config(tmp_path, [case])


@pytest.mark.parametrize("value", [[1, 2], {"key": "value"}], ids=["array", "object"])
def test_rejects_embedded_array_or_object_variable(
    tmp_path: Path,
    value: object,
) -> None:
    with pytest.raises(ConfigError, match="scalar|embedded|variable"):
        _load_case_config(
            tmp_path,
            [_case("not scalar", {"value": value})],
            request_json={"message": "value=${value}"},
        )


@pytest.mark.parametrize(
    "template",
    ["${bad-name}", "${unterminated"],
    ids=["invalid-identifier", "unterminated"],
)
def test_rejects_malformed_placeholder_syntax(
    tmp_path: Path,
    template: str,
) -> None:
    with pytest.raises(ConfigError, match="placeholder|template"):
        _load_case_config(
            tmp_path,
            [_case("malformed", {"bad-name": "value"})],
            request_json={"value": template},
        )


def test_escape_preserves_placeholder_as_literal_text(tmp_path: Path) -> None:
    config = _load_case_config(
        tmp_path,
        [_case("escaped", {})],
        request_json={"value": "$${name}"},
    )

    assert config.tests[0].request.json == {"value": "${name}"}


@pytest.mark.parametrize(
    "value_yaml",
    [".nan", "!!timestamp 2024-01-02"],
    ids=["non-finite-number", "non-json-timestamp"],
)
def test_rejects_non_json_or_non_finite_variable_values(
    tmp_path: Path,
    value_yaml: str,
) -> None:
    config_file = tmp_path / "invalid-variable.yaml"
    config_file.write_text(
        f"""base_url: https://api.example.com
tests:
  - name: Invalid variable
    request: {{method: POST, path: /items, json: {{value: '${{value}}'}}}}
    cases:
      - name: invalid
        variables:
          value: {value_yaml}
        expect: {{status: 201}}
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="variables|JSON|finite"):
        load_config(config_file)


def test_case_json_override_replaces_shared_body_and_can_omit_field(
    tmp_path: Path,
) -> None:
    config = _load_case_config(
        tmp_path,
        [_case(
            "missing name",
            {"role": "member"},
            request={"json": {"role": "${role}"}},
        )],
        request_json={"name": "${name}", "role": "${role}"},
    )

    assert config.tests[0].request.json == {"role": "member"}


def test_substitutes_only_request_json_values(tmp_path: Path) -> None:
    config = _load_case_config(
        tmp_path,
        [_case("restricted substitution", {"value": "resolved"})],
        request_json={"${value}": "${value}"},
        request_fields={
            "path": "/items/${value}",
            "headers": {"X-Value": "${value}"},
            "params": {"value": "${value}"},
        },
    )

    request = config.tests[0].request
    assert request.path == "/items/${value}"
    assert request.headers == {"X-Value": "${value}"}
    assert request.params == {"value": "${value}"}
    assert request.json == {"${value}": "resolved"}


def test_expanding_one_case_does_not_mutate_later_case_templates(
    tmp_path: Path,
) -> None:
    config = _load_case_config(
        tmp_path,
        [_case("first", {"value": "one"}), _case("second", {"value": "two"})],
        request_json={"nested": {"value": "${value}"}},
    )

    assert [test.request.json for test in config.tests] == [
        {"nested": {"value": "one"}},
        {"nested": {"value": "two"}},
    ]


def test_cases_reuse_existing_exact_json_and_schema_expectations(
    tmp_path: Path,
) -> None:
    config = _load_case_config(
        tmp_path,
        [{
            "name": "schema and exact value",
            "variables": {},
            "expect": {
                "status": 201,
                "json": {"result.id": 7},
                "schema": {
                    "type": "object",
                    "required": ["result"],
                    "properties": {"label": {"const": "${value}"}},
                },
            },
        }],
    )

    assert config.tests[0].expect.status == 201
    assert config.tests[0].expect.json == {"result.id": 7}
    assert config.tests[0].expect.schema == {
        "type": "object",
        "required": ["result"],
        "properties": {"label": {"const": "${value}"}},
    }
