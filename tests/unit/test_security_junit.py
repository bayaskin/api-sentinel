from xml.etree import ElementTree as ET

from api_sentinel.junit import write_security_junit_xml
from api_sentinel.security import SecurityFinding
from api_sentinel.security_runner import SecurityResult


def test_writes_security_findings_errors_and_passes(tmp_path):
    report = tmp_path / "security.xml"

    finding = SecurityFinding(
        check="sql_error_disclosure",
        severity="medium",
        title="Potential database error disclosure",
        evidence="MySQL signature found",
        remediation="Return a generic error.",
    )

    results = [
        SecurityResult(
            name="Database error check",
            passed=False,
            status_code=500,
            finding=finding,
        ),
        SecurityResult(
            name="Escaped reflection check",
            passed=True,
            status_code=200,
        ),
        SecurityResult(
            name="Unreachable endpoint",
            passed=False,
            error="Connection refused",
        ),
    ]

    write_security_junit_xml(results, report)

    root = ET.parse(report).getroot()
    cases = root.findall("testcase")

    assert root.attrib["tests"] == "3"
    assert root.attrib["failures"] == "1"
    assert root.attrib["errors"] == "1"

    failure = cases[0].find("failure")
    assert failure is not None
    assert failure.attrib["type"] == "sql_error_disclosure"
    assert "MySQL signature found" in failure.text
    assert "Return a generic error." in failure.text

    assert cases[1].find("failure") is None
    assert cases[1].find("error") is None

    error = cases[2].find("error")
    assert error is not None
    assert error.attrib["message"] == "Connection refused"


def test_escapes_special_characters(tmp_path):
    report = tmp_path / "security.xml"
    finding = SecurityFinding(
        check="unescaped_html_reflection",
        severity="medium",
        title='Unexpected "<tag>" & reflection',
        evidence="Marker <test> & found",
        remediation="Encode < and >.",
    )

    write_security_junit_xml(
        [
            SecurityResult(
                name="Reflection <check> & validation",
                passed=False,
                finding=finding,
            )
        ],
        report,
    )

    root = ET.parse(report).getroot()
    case = root.find("testcase")
    assert case is not None
    assert case.attrib["name"] == "Reflection <check> & validation"

    failure = case.find("failure")
    assert failure is not None
    assert failure.attrib["message"] == finding.title
    assert "Marker <test> & found" in failure.text
