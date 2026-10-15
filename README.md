# API Sentinel

**A lightweight, configuration-driven API smoke-testing CLI built with Python.**

API Sentinel runs HTTP checks defined in a YAML configuration file, validates response status codes, and returns meaningful exit codes for local development and CI/CD pipelines.

## Features

- **Configuration-driven tests** — define API checks in YAML without writing Python test code.
- **HTTP methods** — supports GET, POST, PUT, PATCH, DELETE, HEAD, and OPTIONS.
- **Response validation** — verify expected HTTP status codes.
- **Failure reporting** — reports unexpected status codes and HTTP request errors while continuing through the remaining checks.
- **CI/CD integration** — exits with code `0` when all checks pass, `1` when one or more checks fail, and `2` for configuration errors.
- **Docker support** — run checks in a container without installing Python dependencies on the host.
- **Automated tests** — pytest, Ruff, and a GitHub Actions workflow.
- **Coverage enforcement** — CI requires at least 90% test coverage.
- **JSON response assertions** — validate expected values in nested JSON fields using dot-separated paths.

## Requirements

- Python 3.12 or newer
- pip

Alternatively, use Docker to run the packaged CLI.

## Installation

Clone the repository:

```bash
git clone https://github.com/bayaskin/api-sentinel.git
cd api-sentinel
```

Install the project and development dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Quick start

Run the included example:

```bash
api-sentinel run examples/tests.yaml
```
```bash
api-sentinel run examples/tests.yaml --junit-xml report.xml
```

Example output:

```text
PASS  GET request succeeds (expected 200, got 200)
PASS  JSON response succeeds (expected 200, got 200)

Results: 2 passed, 0 failed
```

The example uses [httpbin](https://httpbin.org/), a public HTTP testing service, so it requires network access.

How to rub local demo:

# Terminal 1
```bash
python examples/mock_api.py
```
# Terminal 2
```bash
api-sentinel run examples/local-tests.yaml --junit-xml report.xml
```

## Configuration

Create a YAML file describing the API and its checks:

```yaml
base_url: https://httpbin.org

tests:
  - name: Get a successful response
    request:
      method: GET
      path: /status/200
    expect:
      status: 200

  - name: Get JSON data
    request:
      method: GET
      path: /json
    expect:
      status: 200
      json:
        slideshow.author: "Yours Truly"
        slideshow.slides: 2
```

### Configuration fields

| Field | Description |
|---|---|
| `base_url` | Base HTTP or HTTPS URL of the target API |
| `tests` | Non-empty list of checks to execute |
| `tests[].name` | Human-readable check name |
| `tests[].request.method` | Supported HTTP method |
| `tests[].request.path` | Absolute path beginning with `/` |
| `tests[].expect.status` | Expected HTTP status code, from 100 to 599 |

Each check sends an HTTP request and compares the actual status code with the expected status. A mismatch marks that check as failed.

## Docker

Build the image from the repository root:

```bash
docker build -t api-sentinel:0.1.0 .
```

Run the included example by mounting its directory read-only:

```bash
docker run --rm \
  -v "$PWD/examples:/work:ro" \
  api-sentinel:0.1.0 \
  run tests.yaml
```

Run a custom configuration by mounting its containing directory into `/work`, then pass its filename to the CLI.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All checks passed |
| `1` | One or more checks failed |
| `2` | Invalid or unreadable configuration |

These exit codes allow API Sentinel to be used as a pipeline gate in automated workflows.

## Development

Run linting:

```bash
ruff check src tests
```

Run the test suite:

```bash
pytest
```

Run tests with coverage reporting and the CI threshold:

```bash
pytest --cov=api_sentinel --cov-report=term-missing --cov-fail-under=90
```

GitHub Actions runs linting and tests on pushes and pull requests.

## Current limitations

API Sentinel is an early-stage smoke-testing tool, not a full API testing framework.

- Assertions currently cover expected HTTP status codes.
- Request bodies, custom headers, authentication, environment variables, and response-body assertions are not yet configurable.
- Tests execute sequentially.
- The example requires access to a public endpoint.

## Roadmap

Potential future improvements:

- Request headers, query parameters, and JSON bodies.
- Environment-variable substitution for configuration and secrets.
- Response-body assertions.
- Configurable timeouts and richer failure diagnostics.
- JUnit-compatible reports for CI systems.

## License

No license has been added yet. Until a license is included, others should not assume they have permission to redistribute or modify this project.