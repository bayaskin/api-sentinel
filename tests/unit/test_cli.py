
from api_sentinel.cli import main
from api_sentinel.runner import ApiTestResult


def test_returns_zero_when_all_tests_pass(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "api_sentinel.cli.load_config",
        lambda path: object(),
    )
    monkeypatch.setattr(
        "api_sentinel.cli.run_tests",
        lambda config: [
            ApiTestResult(
                name="Health endpoint",
                passed=True,
                expected_status=200,
                actual_status=200,
            )
        ],
    )

    exit_code = main(["run", "tests.yaml"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "PASS" in output
    assert "1 passed, 0 failed" in output


def test_returns_one_when_a_test_fails(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "api_sentinel.cli.load_config",
        lambda path: object(),
    )
    monkeypatch.setattr(
        "api_sentinel.cli.run_tests",
        lambda config: [
            ApiTestResult(
                name="Health endpoint",
                passed=False,
                expected_status=200,
                actual_status=503,
                error="expected 200, got 503",
            )
        ],
    )

    exit_code = main(["run", "tests.yaml"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "FAIL" in output
    assert "1 passed, 0 failed" not in output
    assert "0 passed, 1 failed" in output


def test_returns_two_for_invalid_configuration(monkeypatch, capsys) -> None:
    from api_sentinel.config import ConfigError

    def raise_config_error(path):
        raise ConfigError("invalid configuration")

    monkeypatch.setattr(
        "api_sentinel.cli.load_config",
        raise_config_error,
    )

    exit_code = main(["run", "tests.yaml"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Configuration error: invalid configuration" in captured.err
