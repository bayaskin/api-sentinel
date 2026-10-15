import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def mock_api():
    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]

    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["API_SENTINEL_MOCK_PORT"] = str(port)
    process = subprocess.Popen(
        [sys.executable, "examples/mock_api.py"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )

    try:
        for _ in range(40):
            if process.poll() is not None:
                pytest.fail("Mock API exited before becoming ready")

            try:
                with urllib.request.urlopen(
                    f"{base_url}/status/200",
                    timeout=1,
                ):
                    break
            except (OSError, urllib.error.URLError):
                time.sleep(0.25)
        else:
            pytest.fail("Mock API did not become ready")

        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _redirect_config(config: Path, tmp_path: Path, base_url: str) -> Path:
    redirected = tmp_path / f"{config.stem}-local.yaml"
    redirected.write_text(
        config.read_text(encoding="utf-8").replace(
            "http://127.0.0.1:8765", base_url
        ),
        encoding="utf-8",
    )
    return redirected


@pytest.mark.skipif(
    os.environ.get("API_SENTINEL_SKIP_INTEGRATION") == "1",
    reason="Integration tests disabled",
)
def test_security_cli_reports_findings_and_junit(mock_api, tmp_path):
    report = tmp_path / "security-results.xml"
    config = _redirect_config(
        PROJECT_ROOT / "examples/security-tests.yaml", tmp_path, mock_api
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "api_sentinel.cli",
            "security",
            str(config),
            "--junit-xml",
            str(report),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "FINDING" in result.stdout
    assert "2 finding(s)" in result.stdout
    assert report.is_file()

    from xml.etree import ElementTree as ET

    root = ET.parse(report).getroot()
    assert root.attrib["tests"] == "3"
    assert root.attrib["failures"] == "2"
    assert root.attrib["errors"] == "0"


@pytest.mark.skipif(
    os.environ.get("API_SENTINEL_SKIP_INTEGRATION") == "1",
    reason="Integration tests disabled",
)
def test_security_cli_detects_escaped_reflection(mock_api, tmp_path):
    config = tmp_path / "escaped-only.yaml"
    report = tmp_path / "escaped-results.xml"

    config.write_text(
        """
base_url: http://127.0.0.1:8765
probes:
  - name: Escaped reflection
    path: /security/reflect-escaped
    check: unescaped_html_reflection
    parameter: marker
    marker: "<b>API-SENTINEL-TEST</b>"
""",
        encoding="utf-8",
    )

    config = _redirect_config(config, tmp_path, mock_api)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "api_sentinel.cli",
            "security",
            str(config),
            "--junit-xml",
            str(report),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed, 0 finding(s), 0 error(s)" in result.stdout


def _run_api_cli(config: Path):
    return subprocess.run(
        [sys.executable, "-m", "api_sentinel.cli", "run", str(config)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


@pytest.mark.skipif(
    os.environ.get("API_SENTINEL_SKIP_INTEGRATION") == "1",
    reason="Integration tests disabled",
)
def test_api_cli_runs_schema_and_expected_error_example(mock_api, tmp_path):
    config = _redirect_config(
        PROJECT_ROOT / "examples/schema-tests.yaml", tmp_path, mock_api
    )
    result = _run_api_cli(config)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Validate nested user data and email format" in result.stdout
    assert "Validate an expected not-found response" in result.stdout
    assert "2 passed, 0 failed" in result.stdout


@pytest.mark.skipif(
    os.environ.get("API_SENTINEL_SKIP_INTEGRATION") == "1",
    reason="Integration tests disabled",
)
def test_api_cli_reports_schema_violation_path(mock_api, tmp_path):
    config = tmp_path / "wrong-type.yaml"
    config.write_text(
        """
base_url: http://127.0.0.1:8765
tests:
  - name: Wrong nested type
    request: {method: GET, path: /users}
    expect:
      status: 200
      schema:
        type: object
        properties:
          users:
            type: array
            items:
              type: object
              properties:
                id: {type: string}
""",
        encoding="utf-8",
    )

    result = _run_api_cli(_redirect_config(config, tmp_path, mock_api))

    assert result.returncode == 1, result.stdout + result.stderr
    assert "$['users'][0]['id']" in result.stdout
    assert "'type' constraint" in result.stdout


@pytest.mark.skipif(
    os.environ.get("API_SENTINEL_SKIP_INTEGRATION") == "1",
    reason="Integration tests disabled",
)
def test_api_cli_checks_email_format(mock_api, tmp_path):
    config = tmp_path / "invalid-email.yaml"
    config.write_text(
        """
base_url: http://127.0.0.1:8765
tests:
  - name: Invalid email format
    request: {method: GET, path: /users/invalid-email}
    expect:
      status: 200
      schema:
        type: object
        properties:
          users:
            type: array
            items:
              type: object
              properties:
                email: {type: string, format: email}
""",
        encoding="utf-8",
    )

    result = _run_api_cli(_redirect_config(config, tmp_path, mock_api))

    assert result.returncode == 1, result.stdout + result.stderr
    assert "format" in result.stdout
    assert "$['users'][0]['email']" in result.stdout


@pytest.mark.skipif(
    os.environ.get("API_SENTINEL_SKIP_INTEGRATION") == "1",
    reason="Integration tests disabled",
)
def test_api_cli_fails_on_unexpected_status(mock_api, tmp_path):
    config = tmp_path / "unexpected-status.yaml"
    config.write_text(
        """
base_url: http://127.0.0.1:8765
tests:
  - name: Unexpected service unavailable response
    request: {method: GET, path: /status/503}
    expect: {status: 200}
""",
        encoding="utf-8",
    )

    result = _run_api_cli(_redirect_config(config, tmp_path, mock_api))

    assert result.returncode == 1
    assert "expected 200, got 503" in result.stdout


@pytest.mark.skipif(
    os.environ.get("API_SENTINEL_SKIP_INTEGRATION") == "1",
    reason="Integration tests disabled",
)
def test_api_cli_returns_configuration_error_for_invalid_schema(mock_api, tmp_path):
    config = tmp_path / "invalid-schema.yaml"
    config.write_text(
        """
base_url: http://127.0.0.1:8765
tests:
  - name: Invalid schema
    request: {method: GET, path: /users}
    expect:
      status: 200
      schema: {type: not-a-schema-type}
""",
        encoding="utf-8",
    )

    result = _run_api_cli(_redirect_config(config, tmp_path, mock_api))

    assert result.returncode == 2
    assert "Configuration error:" in result.stderr
    assert "expect.schema is invalid" in result.stderr


@pytest.mark.skipif(
    os.environ.get("API_SENTINEL_SKIP_INTEGRATION") == "1",
    reason="Integration tests disabled",
)
def test_api_cli_preserves_existing_non_schema_configuration(mock_api, tmp_path):
    config = _redirect_config(
        PROJECT_ROOT / "examples/local-tests.yaml", tmp_path, mock_api
    )
    result = _run_api_cli(config)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "3 passed, 0 failed" in result.stdout


