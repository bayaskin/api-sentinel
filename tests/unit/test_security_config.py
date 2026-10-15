import textwrap

import pytest

from api_sentinel.config import ConfigError
from api_sentinel.security_config import load_security_config


def write_config(tmp_path, content):
    path = tmp_path / "security.yaml"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def test_loads_valid_security_config(tmp_path):
    path = write_config(
        tmp_path,
        """
        base_url: http://127.0.0.1:8765
        probes:
          - name: SQL error check
            path: /security/sql-error
            check: sql_error_disclosure
          - name: HTML reflection check
            path: /security/reflect
            check: unescaped_html_reflection
            parameter: marker
            marker: "<b>TEST</b>"
        """,
    )

    config = load_security_config(path)

    assert config.base_url == "http://127.0.0.1:8765"
    assert len(config.probes) == 2
    assert config.probes[0].check == "sql_error_disclosure"
    assert config.probes[1].marker == "<b>TEST</b>"


@pytest.mark.parametrize("content", ["", "[]", "null"])
def test_rejects_non_mapping_config(tmp_path, content):
    path = write_config(tmp_path, content)

    with pytest.raises(ConfigError):
        load_security_config(path)


@pytest.mark.parametrize(
    "base_url",
    ["", "ftp://example.com", "http://", "http://user:pass@example.com",
     "http://example.com?token=abc", "http://example.com/#fragment"],
)
def test_rejects_invalid_base_url(tmp_path, base_url):
    path = write_config(
        tmp_path,
        f"""
        base_url: "{base_url}"
        probes:
          - name: SQL error check
            path: /security/sql-error
            check: sql_error_disclosure
        """,
    )

    with pytest.raises(ConfigError):
        load_security_config(path)


def test_rejects_missing_probes(tmp_path):
    path = write_config(tmp_path, "base_url: http://127.0.0.1:8765\n")

    with pytest.raises(ConfigError, match="probes"):
        load_security_config(path)


def test_rejects_unknown_check(tmp_path):
    path = write_config(
        tmp_path,
        """
        base_url: http://127.0.0.1:8765
        probes:
          - name: Unknown
            path: /
            check: arbitrary_check
        """,
    )

    with pytest.raises(ConfigError, match="check"):
        load_security_config(path)


@pytest.mark.parametrize("endpoint", ["https://example.com", "//evil.test", "/x?y=1", "/x#frag"])
def test_rejects_non_relative_endpoint(tmp_path, endpoint):
    path = write_config(
        tmp_path,
        f"""
        base_url: http://127.0.0.1:8765
        probes:
          - name: Invalid endpoint
            path: "{endpoint}"
            check: sql_error_disclosure
        """,
    )

    with pytest.raises(ConfigError, match="path"):
        load_security_config(path)


def test_rejects_empty_name(tmp_path):
    path = write_config(
        tmp_path,
        """
        base_url: http://127.0.0.1:8765
        probes:
          - name: ""
            path: /security/sql-error
            check: sql_error_disclosure
        """,
    )

    with pytest.raises(ConfigError, match="name"):
        load_security_config(path)


def test_rejects_empty_parameter(tmp_path):
    path = write_config(
        tmp_path,
        """
        base_url: http://127.0.0.1:8765
        probes:
          - name: Reflection
            path: /security/reflect
            check: unescaped_html_reflection
            parameter: ""
        """,
    )

    with pytest.raises(ConfigError, match="parameter"):
        load_security_config(path)


def test_rejects_empty_marker(tmp_path):
    path = write_config(
        tmp_path,
        """
        base_url: http://127.0.0.1:8765
        probes:
          - name: Reflection
            path: /security/reflect
            check: unescaped_html_reflection
            marker: ""
        """,
    )

    with pytest.raises(ConfigError, match="marker"):
        load_security_config(path)


def test_rejects_marker_options_for_sql_check(tmp_path):
    path = write_config(
        tmp_path,
        """
        base_url: http://127.0.0.1:8765
        probes:
          - name: SQL check
            path: /security/sql-error
            check: sql_error_disclosure
            marker: TEST
        """,
    )

    with pytest.raises(ConfigError, match="only valid"):
        load_security_config(path)


def test_rejects_non_mapping_probe(tmp_path):
    path = write_config(
        tmp_path,
        """
        base_url: http://127.0.0.1:8765
        probes:
          - just-a-string
        """,
    )

    with pytest.raises(ConfigError, match="mapping"):
        load_security_config(path)


def test_rejects_missing_file():
    with pytest.raises(ConfigError, match="Unable to load"):
        load_security_config("/nonexistent/security-config.yaml")


def test_rejects_invalid_yaml(tmp_path):
    path = write_config(tmp_path, "base_url: [unterminated")

    with pytest.raises(ConfigError, match="Unable to load"):
        load_security_config(path)
