# API Sentinel

**A lightweight, configuration-driven API smoke-testing CLI built with Python.**

API Sentinel runs HTTP checks defined in a YAML configuration file, validates expected HTTP status codes and JSON responses, and returns meaningful exit codes for local development and CI/CD pipelines.

## Features

- **Configuration-driven tests** — define API checks in YAML without writing Python test code.
- **HTTP methods** — supports GET, POST, PUT, PATCH, DELETE, HEAD, and OPTIONS.
- **Request configuration** — configure request headers, query parameters, and JSON bodies.
- **Response validation** — verify expected HTTP status codes, exact JSON values, and JSON Schema constraints.
- **Failure reporting** — reports unexpected status codes and HTTP request errors while continuing through the remaining checks.
- **JUnit XML reports** — export API smoke-test and security-check results for CI systems.
- **CI/CD integration** — exits with code `0` when all checks pass, `1` when one or more checks fail, and `2` for configuration or report-writing errors.
- **Docker support** — run the CLI in a container using an unprivileged runtime user.
- **Security checks (experimental)** — detect common database error disclosure and unescaped HTML reflection indicators using an explicit YAML configuration.
- **Automated quality checks** — pytest, Ruff, coverage enforcement, package builds, API smoke tests, security-check integration tests, and clean-install verification in GitHub Actions.
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

Run the schema and expected-error example against the same local mock API:

```bash
api-sentinel run examples/schema-tests.yaml
```

The local examples check HTTP status codes, exact JSON values, JSON Schema constraints, and an expected 404 response. They require the mock API to be running on port 8765.

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
| `tests[].expect.schema` | Optional JSON Schema object for the response body |

`expect.json` checks exact values at dot-separated object paths. For example, `slideshow.author` checks the `author` field inside the `slideshow` object. It can also compare an entire JSON value, including a list or object, at a path.

### JSON Schema and expected error responses

`expect.schema` validates response structure and constraints. API Sentinel supports **JSON Schema Draft 2020-12** and checks configured formats such as `email`. Schemas must be YAML mappings (JSON objects) and are validated when the configuration is loaded. A schema may omit `$schema`, in which case Draft 2020-12 is used, or declare `https://json-schema.org/draft/2020-12/schema`; any other `$schema` value is rejected as a configuration error. At most 10 schema violations are reported for each response, with a notice when more are omitted.

For example, `examples/schema-tests.yaml` checks required fields, types, nested objects, array items, and email format. Schema assertions complement `expect.json`: schemas validate the shape and allowed values of a response, while `expect.json` checks specific exact values. Both can be configured together and both are enforced.

```yaml
base_url: http://127.0.0.1:8765
tests:
  - name: Validate users
    request:
      method: GET
      path: /users
    expect:
      status: 200
      schema:
        type: object
        required: [users]
        properties:
          users:
            type: array
            items:
              type: object
              required: [id, email, profile]
              properties:
                id: {type: integer}
                email: {type: string, format: email}
                profile:
                  type: object
                  required: [display_name]
                  properties:
                    display_name: {type: string}
      json:
        users:
          - id: 7
            email: ada@example.com
            profile:
              display_name: Ada

  - name: Check a not-found response
    request:
      method: GET
      path: /does-not-exist
    expect:
      status: 404
      json:
        error: Not found
```

An expected error response uses the same `expect.status` field as a successful response. Add `expect.json` and/or `expect.schema` to validate its body. A matching 404 with the expected error body passes; a different status or body fails. There is no separate negative-test status setting.

Run the example locally after starting `python examples/mock_api.py`:

```bash
api-sentinel run examples/schema-tests.yaml
```

These checks verify documented API behavior. JSON Schema and expected-error assertions are not a substitute for a full security scanner.

### Data-driven cases

Add an optional `cases` list to a test to run one request definition with multiple inputs. Each case expands into an independent test named `Parent test / case name`. Cases run in YAML order, and a failed case does not stop later cases. Every case needs its own complete `expect` block; a parent-level `expect` cannot be combined with `cases`.

A case can replace the parent JSON request body with `request.json`. This is a complete replacement, not a merge. If the case omits `request.json`, it uses the parent body. Existing configurations without `cases` continue to work as before.

Each case declares its own `variables` mapping. In JSON request-body values, `${identifier}` references a case variable; identifiers start with a letter or underscore and contain only letters, digits, and underscores. An undefined variable is a configuration error, while a variable explicitly set to `null` is defined. Unused variables are allowed.

A placeholder that occupies a whole value preserves the variable's JSON type, including strings, numbers, Booleans, null, arrays, and objects. Embedded placeholders accept scalar values: strings are inserted as text, while numbers use JSON number text and Booleans and null become `true`, `false`, and `null`. Use `$${name}` to write the literal `${name}` without substitution.

Substitution applies only to JSON request-body values. It does not apply to object keys, paths, headers, query parameters, expectations, or schemas. Malformed placeholders, undefined references, non-JSON values, non-finite numbers, and embedded arrays or objects are configuration errors.

The [data-driven example](examples/data-driven-tests.yaml) demonstrates valid input, a complete body override that omits the required `name`, an empty required value, and a typed Boolean value. Its case definitions include their own expectations:

```yaml
  - name: Create a user
    request:
      method: POST
      path: /users
      json:
        name: "${name}"
        role: "${role}"
        nickname: "${nickname}"
    cases:
      - name: valid user
        variables: {name: Ada Lovelace, role: member, nickname: Ada}
        expect:
          status: 201
          json: {user.id: 1, user.name: Ada Lovelace}
      - name: missing required name
        variables: {role: member, nickname: Ada}
        request:
          json: {role: "${role}", nickname: "${nickname}"}
        expect:
          status: 400
          json: {error.code: invalid_name, error.field: name}
```

To run the complete example, start the repository's mock API in one terminal. It uses port `8765` by default. If that port is occupied, start it on an OS-selected free port with `API_SENTINEL_MOCK_PORT=0`; the server prints the port it actually bound to. For example:

```bash
API_SENTINEL_MOCK_PORT=0 python examples/mock_api.py
```

Keep that server running. In a second terminal, set `MOCK_PORT` to the port printed by the server, make a temporary copy of the example with its base URL updated, and run the CLI from the repository root:

```bash
MOCK_PORT=<port-printed-by-server>
sed "s|http://127.0.0.1:8765|http://127.0.0.1:${MOCK_PORT}|" \
  examples/data-driven-tests.yaml > /tmp/data-driven-tests.yaml
api-sentinel run /tmp/data-driven-tests.yaml
```

If port `8765` is available, the simpler default procedure is `python examples/mock_api.py` followed by `api-sentinel run examples/data-driven-tests.yaml`. Data-driven cases exercise configured API behavior; they do not provide response extraction, chained workflows, automatic fuzzing, or performance testing. API Sentinel remains a smoke-testing CLI, not a production server or a full contract-testing platform.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All checks passed |
| `1` | One or more API checks failed |
| `2` | Configuration error or JUnit report-writing error |

For `api-sentinel run`, exit code `0` means every check passed, `1` means one or more response checks failed, and `2` means configuration loading or JUnit report writing failed. These exit codes allow API Sentinel to act as a pipeline gate.

## JUnit reports

Generate a report for CI systems:

```bash
api-sentinel run examples/local-tests.yaml --junit-xml report.xml
```

The report contains a test case for each executed check and failure details for unsuccessful checks. The report path must be writable.


## Security checks (experimental)

API Sentinel includes an initial set of configuration-driven security response checks. These are intended for systems you own or are explicitly authorized to test.

Start the local mock API in one terminal:

```bash
python examples/mock_api.py
```

Run the security checks in another terminal:

```bash
api-sentinel security examples/security-tests.yaml
```

Write a JUnit XML report for CI systems:

```bash
mkdir -p reports
api-sentinel security examples/security-tests.yaml \
  --junit-xml reports/security-results.xml
```

The example configuration targets `http://127.0.0.1:8765`, the local mock API. Do not use the example configuration against other systems without reviewing and explicitly changing the target.

### Security configuration

```yaml
base_url: http://127.0.0.1:8765

probes:
  - name: Detect database error disclosure
    path: /security/sql-error
    check: sql_error_disclosure

  - name: Detect unescaped HTML reflection
    path: /security/reflect
    check: unescaped_html_reflection
    parameter: marker
    marker: "<b>API-SENTINEL-TEST</b>"
```

Supported initial checks:

- `sql_error_disclosure` — looks for common database error signatures in the response body.
- `unescaped_html_reflection` — checks whether a configured marker is reflected verbatim in the response.

Each probe has a human-readable `name`, a relative endpoint `path`, and a supported `check`. Reflection checks can also set the query-string `parameter` and the inert `marker` value.

### Interpreting security results

- Exit code `0`: no findings or execution errors were reported.
- Exit code `1`: one or more findings or execution errors were reported.
- Exit code `2`: configuration validation or JUnit report-writing failed.

When `--junit-xml` is used, a detected finding is represented as a JUnit failure; an execution error is represented as a JUnit error. Passing checks are represented as successful test cases.

**Important limitations:** these checks are initial indicators, not a full vulnerability scanner. A database error signature indicates possible database error disclosure; it does not prove SQL injection. Unescaped HTML reflection does not prove that a browser will execute script or that exploitable XSS exists. Use browser-based validation and a broader authorized security-testing process before treating a result as a confirmed vulnerability. The current security checks use configured GET requests and should only be run against approved targets.

## Docker

Build the image from the repository root:

```bash
docker build -t api-sentinel:0.4.0 .
```

Run the public-service example:

```bash
docker run --rm \
  -v "$PWD/examples:/work:ro" \
  api-sentinel:0.4.0 \
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

- Dot-separated JSON assertions currently traverse nested JSON objects; use `expect.schema` for array constraints.
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
