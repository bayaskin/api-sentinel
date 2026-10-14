
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
