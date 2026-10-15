import argparse
import sys
from collections.abc import Sequence

from api_sentinel.config import ConfigError, load_config
from api_sentinel.junit import write_junit_xml, write_security_junit_xml
from api_sentinel.runner import run_tests
from api_sentinel.security_config import load_security_config
from api_sentinel.security_runner import run_security_checks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="api-sentinel",
        description="Run configuration-driven API checks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Execute API smoke tests from a YAML configuration file.",
    )
    run_parser.add_argument("config", help="Path to the YAML configuration file.")
    run_parser.add_argument(
        "--junit-xml",
        metavar="PATH",
        help="Write test results to a JUnit XML report.",
    )

    security_parser = subparsers.add_parser(
        "security",
        help="Execute configured security response checks.",
    )
    security_parser.add_argument(
        "config",
        help="Path to the security YAML configuration file.",
    )
    security_parser.add_argument(
        "--junit-xml",
        metavar="PATH",
        help="Write security results to a JUnit XML report.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        try:
            config = load_config(args.config)
        except ConfigError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            return 2

        results = run_tests(config)

        if args.junit_xml:
            try:
                write_junit_xml(results, args.junit_xml)
            except OSError as exc:
                print(f"Error writing JUnit report: {exc}", file=sys.stderr)
                return 2

            print(f"JUnit report written to {args.junit_xml}")

        for result in results:
            label = "PASS" if result.passed else "FAIL"
            print(
                f"  {label}  {result.name} "
                f"(expected {result.expected_status}, got {result.actual_status})"
            )
            if result.error:
                print(f"        {result.error}")

        passed = sum(result.passed for result in results)
        failed = len(results) - passed
        print(f"\nResults: {passed} passed, {failed} failed")
        return 1 if failed else 0

    if args.command == "security":
        try:
            config = load_security_config(args.config)
        except ConfigError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            return 2

        results = run_security_checks(config.base_url, config.probes)

        if args.junit_xml:
            try:
                write_security_junit_xml(results, args.junit_xml)
            except OSError as exc:
                print(f"Error writing JUnit report: {exc}", file=sys.stderr)
                return 2

            print(f"JUnit report written to {args.junit_xml}")

        for result in results:
            label = "PASS" if result.passed else "FINDING"
            suffix = (
                f" (HTTP {result.status_code})"
                if result.status_code is not None
                else ""
            )
            print(f"  {label}  {result.name}{suffix}")

            if result.finding:
                print(
                    f"        [{result.finding.severity}] "
                    f"{result.finding.title}"
                )
                print(f"        Evidence: {result.finding.evidence}")
                print(f"        Remediation: {result.finding.remediation}")

            if result.error:
                print(f"        {result.error}")

        findings = sum(result.finding is not None for result in results)
        errors = sum(result.error is not None for result in results)
        passed = sum(result.passed for result in results)

        print(
            f"\nSecurity results: {passed} passed, "
            f"{findings} finding(s), {errors} error(s)"
        )
        return 1 if findings or errors else 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
