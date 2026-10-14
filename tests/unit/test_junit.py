from xml.etree import ElementTree as ET

from api_sentinel.junit import write_junit_xml
from api_sentinel.runner import ApiTestResult


def test_writes_passing_and_failing_results(tmp_path) -> None:
    report = tmp_path / "junit.xml"
    results = [
        ApiTestResult(
            name="Health endpoint",
            passed=True,
            expected_status=200,
            actual_status=200,
        ),
        ApiTestResult(
            name="Unavailable endpoint",
            passed=False,
            expected_status=200,
            actual_status=503,
            error="expected 200, got 503",
        ),
    ]

    write_junit_xml(results, report)

    root = ET.parse(report).getroot()
    cases = root.findall("testcase")

    assert root.tag == "testsuite"
    assert root.attrib["tests"] == "2"
    assert root.attrib["failures"] == "1"
    assert cases[0].attrib["name"] == "Health endpoint"
    assert cases[0].find("failure") is None
    assert cases[1].attrib["name"] == "Unavailable endpoint"
    assert cases[1].find("failure").attrib["message"] == "expected 200, got 503"


def test_writes_failure_when_no_http_status_is_available(tmp_path) -> None:
    report = tmp_path / "junit.xml"
    results = [
        ApiTestResult(
            name="Unreachable endpoint",
            passed=False,
            expected_status=200,
            actual_status=None,
            error="Connection refused",
        )
    ]

    write_junit_xml(results, report)

    root = ET.parse(report).getroot()
    failure = root.find("./testcase/failure")

    assert root.attrib["failures"] == "1"
    assert failure is not None
    assert failure.attrib["message"] == "Connection refused"