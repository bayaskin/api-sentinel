import os
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
    process = subprocess.Popen(
        [sys.executable, "examples/mock_api.py"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        for _ in range(40):
            if process.poll() is not None:
                pytest.fail("Mock API exited before becoming ready")

            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:8765/status/200",
                    timeout=1,
                ):
                    break
            except (OSError, urllib.error.URLError):
                time.sleep(0.25)
        else:
            pytest.fail("Mock API did not become ready")

        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.mark.skipif(
    os.environ.get("API_SENTINEL_SKIP_INTEGRATION") == "1",
    reason="Integration tests disabled",
)
def test_security_cli_reports_findings_and_junit(mock_api, tmp_path):
    report = tmp_path / "security-results.xml"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "api_sentinel.cli",
            "security",
            "examples/security-tests.yaml",
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


