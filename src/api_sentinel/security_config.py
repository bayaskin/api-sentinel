"""Configuration loading for API Sentinel security checks."""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from api_sentinel.config import ConfigError

SUPPORTED_CHECKS = {
    "sql_error_disclosure",
    "unescaped_html_reflection",
}


@dataclass(frozen=True)
class SecurityConfig:
    base_url: str
    probes: list


def load_security_config(path: str | Path) -> SecurityConfig:
    """Load and validate a security-check YAML file."""
    try:
        with Path(path).open(encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Unable to load security configuration: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError("Security configuration must be a YAML mapping.")

    base_url = data.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        raise ConfigError("'base_url' must be a non-empty URL.")

    parsed_url = urlsplit(base_url)
    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.netloc
        or parsed_url.username is not None
        or parsed_url.password is not None
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ConfigError(
            "'base_url' must be an HTTP(S) URL without credentials, "
            "query parameters, or fragments."
        )

    raw_probes = data.get("probes")
    if not isinstance(raw_probes, list) or not raw_probes:
        raise ConfigError("'probes' must be a non-empty list.")

    from api_sentinel.security_runner import SecurityProbe

    probes = []
    for index, item in enumerate(raw_probes):
        prefix = f"probes[{index}]"

        if not isinstance(item, dict):
            raise ConfigError(f"{prefix} must be a YAML mapping.")

        name = item.get("name")
        endpoint = item.get("path")
        check = item.get("check")

        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"{prefix}.name must be a non-empty string.")

        if (
            not isinstance(endpoint, str)
            or not endpoint.startswith("/")
            or endpoint.startswith("//")
            or "://" in endpoint
            or "?" in endpoint
            or "#" in endpoint
        ):
            raise ConfigError(
                f"{prefix}.path must be a relative endpoint path starting with '/'."
            )

        if check not in SUPPORTED_CHECKS:
            raise ConfigError(
                f"{prefix}.check must be one of: "
                f"{', '.join(sorted(SUPPORTED_CHECKS))}."
            )

        parameter = item.get("parameter", "marker")
        marker = item.get("marker", "<api-sentinel-probe>")

        if not isinstance(parameter, str) or not parameter.strip():
            raise ConfigError(f"{prefix}.parameter must be a non-empty string.")

        if not isinstance(marker, str) or not marker:
            raise ConfigError(f"{prefix}.marker must be a non-empty string.")

        if check == "sql_error_disclosure" and (
            "parameter" in item or "marker" in item
        ):
            raise ConfigError(
                f"{prefix}: parameter and marker are only valid for "
                "unescaped_html_reflection checks."
            )

        probes.append(
            SecurityProbe(
                name=name.strip(),
                path=endpoint,
                check=check,
                parameter=parameter,
                marker=marker,
            )
        )

    return SecurityConfig(base_url=base_url.rstrip("/"), probes=probes)
