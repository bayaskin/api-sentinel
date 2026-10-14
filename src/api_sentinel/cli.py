
import argparse
import sys
from collections.abc import Sequence

from api_sentinel.config import ConfigError, load_config
from api_sentinel.runner import run_tests


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="api-sentinel",
        description="Run configuration-driven API smoke tests.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Execute tests from a YAML configuration file.",
    )
    run_parser.add_argument(
        "config",
        help="Path to the YAML configuration file.",
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

        for result in results:
            label = "PASS" if result.passed else "FAIL"
            message = (
                f"  {label}  {result.name} "
                f"(expected {result.expected_status}, "
                f"got {result.actual_status})"
            )
            print(message)

            if result.error:
                print(f"        {result.error}")

        passed = sum(result.passed for result in results)
        failed = len(results) - passed

        print(f"\nResults: {passed} passed, {failed} failed")

        return 1 if failed else 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
