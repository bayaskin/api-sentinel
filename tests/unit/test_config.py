
from pathlib import Path

import pytest

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
