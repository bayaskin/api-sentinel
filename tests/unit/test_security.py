from api_sentinel.security import (
    detect_database_error_disclosure,
    detect_unescaped_html_reflection,
)


def test_detects_mysql_error_disclosure() -> None:
    finding = detect_database_error_disclosure(
        "You have an error in your SQL syntax; check the manual for MySQL"
    )

    assert finding is not None
    assert finding.check == "sql_error_disclosure"
    assert finding.severity == "medium"
    assert "MySQL error" in finding.evidence


def test_detects_sqlite_error_disclosure() -> None:
    finding = detect_database_error_disclosure(
        "sqlite3.OperationalError: near SELECT: syntax error"
    )

    assert finding is not None
    assert "SQLite error" in finding.evidence


def test_detects_oracle_error_disclosure() -> None:
    finding = detect_database_error_disclosure(
        "Database failure: ORA-00933"
    )

    assert finding is not None
    assert "Oracle error" in finding.evidence


def test_ignores_generic_error_message() -> None:
    finding = detect_database_error_disclosure(
        "The request could not be processed."
    )

    assert finding is None


def test_detects_unescaped_html_marker() -> None:
    marker = "<api-sentinel-marker>"
    finding = detect_unescaped_html_reflection(
        f"<html><body>Search: {marker}</body></html>",
        marker,
    )

    assert finding is not None
    assert finding.check == "unescaped_html_reflection"
    assert "Potential" in finding.title


def test_ignores_escaped_html_marker() -> None:
    marker = "<api-sentinel-marker>"
    finding = detect_unescaped_html_reflection(
        "&lt;api-sentinel-marker&gt;",
        marker,
    )

    assert finding is None


def test_ignores_empty_marker() -> None:
    finding = detect_unescaped_html_reflection(
        "<html><body>anything</body></html>",
        "",
    )

    assert finding is None


def test_finding_includes_remediation() -> None:
    finding = detect_database_error_disclosure("ORA-00933")

    assert finding is not None
    assert finding.remediation
