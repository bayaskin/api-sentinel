from api_sentinel.cli import main


def test_security_command_reports_findings(tmp_path, capsys, monkeypatch):
    from api_sentinel import cli
    from api_sentinel.security import SecurityFinding
    from api_sentinel.security_runner import SecurityResult

    config_path = tmp_path / "security.yaml"
    config_path.write_text(
        """
base_url: http://127.0.0.1:8765
probes:
  - name: SQL check
    path: /security/sql-error
    check: sql_error_disclosure
""",
        encoding="utf-8",
    )

    finding = SecurityFinding(
        check="sql_error_disclosure",
        severity="medium",
        title="Potential database error disclosure",
        evidence="MySQL signature found",
        remediation="Return a generic error.",
    )

    monkeypatch.setattr(
        cli,
        "run_security_checks",
        lambda *_: [
            SecurityResult(
                name="SQL check",
                passed=False,
                status_code=500,
                finding=finding,
            )
        ],
    )

    assert main(["security", str(config_path)]) == 1
    output = capsys.readouterr().out
    assert "FINDING" in output
    assert "Potential database error disclosure" in output


def test_security_command_returns_two_for_invalid_config(tmp_path, capsys):
    path = tmp_path / "invalid.yaml"
    path.write_text("not: [valid", encoding="utf-8")

    assert main(["security", str(path)]) == 2
    assert "Configuration error" in capsys.readouterr().err


def test_security_command_passes_when_no_findings(tmp_path, monkeypatch):
    from api_sentinel import cli
    from api_sentinel.security_runner import SecurityResult

    config_path = tmp_path / "security.yaml"
    config_path.write_text(
        """
base_url: http://127.0.0.1:8765
probes:
  - name: SQL check
    path: /security/sql-error
    check: sql_error_disclosure
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli,
        "run_security_checks",
        lambda *_: [SecurityResult(name="SQL check", passed=True, status_code=200)],
    )

    assert main(["security", str(config_path)]) == 0
