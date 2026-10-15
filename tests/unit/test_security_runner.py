import httpx

from api_sentinel.security_runner import SecurityProbe, run_security_checks


def make_client(handler):
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://testserver",
    )


def test_detects_database_error_in_http_response():
    def handler(request):
        return httpx.Response(
            500,
            text="You have an error in your SQL syntax; MySQL server version",
        )

    client = make_client(handler)
    try:
        results = run_security_checks(
            "http://testserver",
            [
                SecurityProbe(
                    name="SQL error disclosure",
                    path="/security/sql-error",
                    check="sql_error_disclosure",
                )
            ],
            client=client,
        )
    finally:
        client.close()

    assert len(results) == 1
    assert not results[0].passed
    assert results[0].status_code == 500
    assert results[0].finding is not None
    assert results[0].finding.check == "sql_error_disclosure"


def test_detects_unescaped_reflection_in_http_response():
    def handler(request):
        marker = request.url.params["marker"]
        return httpx.Response(200, text=f"<html>{marker}</html>")

    client = make_client(handler)
    try:
        results = run_security_checks(
            "http://testserver",
            [
                SecurityProbe(
                    name="HTML reflection",
                    path="/security/reflect",
                    check="unescaped_html_reflection",
                    marker="<b>SAFE</b>",
                )
            ],
            client=client,
        )
    finally:
        client.close()

    assert not results[0].passed
    assert results[0].finding is not None
    assert results[0].finding.check == "unescaped_html_reflection"


def test_passes_when_marker_is_html_escaped():
    def handler(request):
        return httpx.Response(
            200,
            text="<html>&lt;b&gt;SAFE&lt;/b&gt;</html>",
        )

    client = make_client(handler)
    try:
        results = run_security_checks(
            "http://testserver",
            [
                SecurityProbe(
                    name="Escaped HTML reflection",
                    path="/security/reflect-escaped",
                    check="unescaped_html_reflection",
                    marker="<b>SAFE</b>",
                )
            ],
            client=client,
        )
    finally:
        client.close()

    assert results[0].passed
    assert results[0].finding is None


def test_reports_unsupported_check():
    results = run_security_checks(
        "http://testserver",
        [
            SecurityProbe(
                name="Unknown check",
                path="/",
                check="unknown_check",
            )
        ],
    )

    assert not results[0].passed
    assert "Unsupported security check" in results[0].error
