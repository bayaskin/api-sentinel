"""HTTP runner for explicitly configured security checks."""

from dataclasses import dataclass

import httpx

from api_sentinel.security import (
    SecurityFinding,
    detect_database_error_disclosure,
    detect_unescaped_html_reflection,
)


@dataclass(frozen=True)
class SecurityProbe:
    """A single security check against a configured endpoint."""

    name: str
    path: str
    check: str
    parameter: str = "marker"
    marker: str = "<api-sentinel-probe>"


@dataclass(frozen=True)
class SecurityResult:
    """Outcome of one security check."""

    name: str
    passed: bool
    status_code: int | None = None
    finding: SecurityFinding | None = None
    error: str | None = None


def run_security_checks(
    base_url: str,
    probes: list[SecurityProbe],
    client: httpx.Client | None = None,
) -> list[SecurityResult]:
    """Execute configured security checks and return their findings."""
    owns_client = client is None
    if client is None:
        client = httpx.Client(
            base_url=base_url,
            timeout=10.0,
            follow_redirects=True,
        )

    results: list[SecurityResult] = []

    try:
        for probe in probes:
            if probe.check not in {
                "sql_error_disclosure",
                "unescaped_html_reflection",
            }:
                results.append(
                    SecurityResult(
                        name=probe.name,
                        passed=False,
                        error=f"Unsupported security check: {probe.check}",
                    )
                )
                continue

            params = (
                {probe.parameter: probe.marker}
                if probe.check == "unescaped_html_reflection"
                else None
            )

            try:
                response = client.get(
                    f"{base_url.rstrip('/')}/{probe.path.lstrip('/')}",
                    params=params,
                )
                body = response.text
            except httpx.HTTPError as exc:
                results.append(
                    SecurityResult(
                        name=probe.name,
                        passed=False,
                        error=f"HTTP request failed: {exc}",
                    )
                )
                continue

            if probe.check == "sql_error_disclosure":
                finding = detect_database_error_disclosure(body)
            else:
                finding = detect_unescaped_html_reflection(body, probe.marker)

            results.append(
                SecurityResult(
                    name=probe.name,
                    passed=finding is None,
                    status_code=response.status_code,
                    finding=finding,
                )
            )
    finally:
        if owns_client:
            client.close()

    return results
