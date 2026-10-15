"""Security response checks for API Sentinel."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityFinding:
    """A potential security issue identified in an HTTP response."""

    check: str
    severity: str
    title: str
    evidence: str
    remediation: str


_DATABASE_ERROR_PATTERNS = (
    ("MySQL error", re.compile(r"SQL syntax.*MySQL|MySQL server version", re.IGNORECASE)),
    ("SQLite error", re.compile(r"sqlite3\.(?:OperationalError|DatabaseError)", re.IGNORECASE)),
    ("PostgreSQL error", re.compile(r"PostgreSQL.*ERROR|ERROR:\s+syntax error", re.IGNORECASE)),
    ("Oracle error", re.compile(r"\bORA-\d{5}\b", re.IGNORECASE)),
    (
        "SQL Server error",
        re.compile(
            r"Unclosed quotation mark after the character string"
            r"|Microsoft OLE DB Provider for SQL Server",
            re.IGNORECASE,
        ),
    ),
    ("SQLSTATE error", re.compile(r"\bSQLSTATE\[[0-9A-Z]+\]", re.IGNORECASE)),
)


def detect_database_error_disclosure(body: str) -> SecurityFinding | None:
    """Identify common database error messages exposed in a response body."""
    for label, pattern in _DATABASE_ERROR_PATTERNS:
        match = pattern.search(body)
        if match:
            return SecurityFinding(
                check="sql_error_disclosure",
                severity="medium",
                title="Potential database error disclosure",
                evidence=f"{label} signature found in response body",
                remediation=(
                    "Return a generic client-facing error and keep database "
                    "diagnostics in protected server-side logs."
                ),
            )

    return None


def detect_unescaped_html_reflection(
    body: str,
    marker: str,
) -> SecurityFinding | None:
    """Flag a supplied HTML-like marker reflected without escaping.

    This identifies potential unsafe reflection, not confirmed executable XSS.
    Callers should use a unique, inert marker and test only authorized targets.
    """
    if not marker:
        return None

    if marker in body:
        return SecurityFinding(
            check="unescaped_html_reflection",
            severity="medium",
            title="Potential unescaped HTML reflection",
            evidence="The supplied HTML-like marker appears verbatim in the response",
            remediation=(
                "Apply context-appropriate output encoding and validate input. "
                "Use browser-based testing to determine whether execution is possible."
            ),
        )

    return None
