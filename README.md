# API Sentinel

**A lightweight, configuration-driven API smoke-testing CLI built with Python.**

API Sentinel runs HTTP checks defined in a YAML configuration file, validates expected HTTP status codes and JSON response fields, and returns meaningful exit codes for local development and CI/CD pipelines.

## Features

- **Configuration-driven tests** — define API checks in YAML without writing Python test code.
- **HTTP methods** — supports GET, POST, PUT, PATCH, DELETE, HEAD, and OPTIONS.
- **Request configuration** — configure request headers, query parameters, and JSON bodies.
- **Response validation** — verify expected HTTP status codes and nested JSON fields using dot-separated paths.
- **Failure reporting** — reports unexpected status codes and HTTP request errors while continuing through the remaining checks.
- **JUnit XML reports** — export results for CI systems.
- **CI/CD integration** — exits with code `0` when all checks pass, `1` when one or more checks fail, and `2` for configuration or report-writing errors.
- **Docker support** — run the CLI in a container using an unprivileged runtime user.
- **Automated quality checks** — pytest, Ruff, coverage enforcement, package builds, and clean-install smoke tests in GitHub Actions.
- **Python distributions** — build a wheel and source distribution.

## Requirements

- Python 3.12 or newer
- pip

Docker is optional.

## Installation

Clone the repository:

```bash
git clone https://github.com/bayaskin/api-sentinel.git
cd api-sentinel
```

Create a virtual environment and install the project with development dependencies:

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

For a deterministic local demo, open two terminals.

**Terminal 1 — start the mock API:**

```bash
python examples/mock_api.py
```

**Terminal 2 — run the checks:**

```bash
api-sentinel run examples/local-tests.yaml
```

Generate a JUnit XML report:

```bash
api-sentinel run examples/local-tests.yaml --junit-xml report.xml
```

The local example checks HTTP status codes and JSON response fields. It requires the mock API to be running on port 8765.

You can also run the public-service example:

```bash
api-sentinel run examples/tests.yaml
```

That example uses [httpbin](https://httpbin.org/) and requires network access. Its availability is outside API Sentinel's control.

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

  - name: Validate JSON response fields
    request:
      method: GET
      path: /json
    expect:
      status: 200
      json:
        slideshow.author: "Yours Truly"
        slideshow.slides: 2
```

Run the configuration:

```bash
api-sentinel run examples/tests.yaml
```

### Configuration fields

| Field | Description |
|---|---|
| `base_url` | Base HTTP or HTTPS URL of the target API |
| `tests` | Non-empty list of checks to execute |
| `tests[].name` | Human-readable check name |
| `tests[].request.method` | Supported HTTP method |
| `tests[].request.path` | Request path beginning with `/` |
| `tests[].request.headers` | Optional HTTP request headers |
| `tests[].request.params` | Optional query parameters |
| `tests[].request.json` | Optional JSON request body |
| `tests[].expect.status` | Expected HTTP status code, from 100 to 599 |
| `tests[].expect.json` | Optional mapping of JSON paths to expected values |

JSON assertions use dot-separated paths to access nested object fields. For example, `slideshow.author` checks the `author` field inside the `slideshow` object.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All checks passed |
| `1` | One or more API checks failed |
| `2` | Configuration error or report-writing error |

These exit codes allow API Sentinel to act as a pipeline gate.

## JUnit reports

Generate a report for CI systems:

```bash
api-sentinel run examples/local-tests.yaml --junit-xml report.xml
```

The report contains a test case for each executed check and failure details for unsuccessful checks. The report path must be writable.

## Docker

Build the image from the repository root:

```bash
docker build -t api-sentinel:0.1.0 .
```

Run the public-service example:

```bash
docker run --rm \
  -v "$PWD/examples:/work:ro" \
  api-sentinel:0.1.0 \
  run tests.yaml
```

The container uses an unprivileged user. For a custom configuration, mount the directory containing the YAML file into `/work` and pass its filename to the CLI.

To run the local mock API from a container, additional networking setup is required because `127.0.0.1` inside a container refers to that container itself.

## Development

Run linting:

```bash
ruff check src tests
```

Run the test suite:

```bash
python -m pytest
```

Run tests with coverage enforcement:

```bash
python -m pytest \
  --cov=api_sentinel \
  --cov-report=term-missing \
  --cov-fail-under=90
```

Build the Python distributions:

```bash
python -m build
```

GitHub Actions runs automated checks, exercises the local mock API, verifies clean installation of the built wheel, and uploads test reports and distribution artifacts.

## Current limitations

API Sentinel is an early-stage smoke-testing tool, not a full API testing framework.

- JSON assertions currently target nested JSON object fields.
- Configuration values are static; environment-variable substitution and dedicated secret handling are not implemented.
- Checks execute sequentially.
- Request timeouts use the runner's current fixed timeout.
- The public-service example depends on an external endpoint.

## Roadmap

Potential future improvements include:

- Environment-variable substitution and secret management
- Configurable timeouts and retry policies
- More expressive response assertions
- Parallel test execution
- Richer reporting and diagnostics

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
