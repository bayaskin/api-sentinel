from pathlib import Path
from xml.etree import ElementTree as ET

from api_sentinel.runner import ApiTestResult


def write_junit_xml(
    results: list[ApiTestResult],
    output_path: str | Path,
) -> None:
    """Write API test results in JUnit XML format."""
    failed = sum(not result.passed for result in results)

    suite = ET.Element(
        "testsuite",
        {
            "name": "API Sentinel",
            "tests": str(len(results)),
            "failures": str(failed),
            "errors": "0",
            "skipped": "0",
        },
    )

    for result in results:
        testcase = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": "api_sentinel",
                "name": result.name,
                "time": "0",
            },
        )

        if not result.passed:
            failure = ET.SubElement(
                testcase,
                "failure",
                {
                    "message": result.error or "API test failed",
                    "type": "AssertionError",
                },
            )
            failure.text = result.error or "API test failed"

    tree = ET.ElementTree(suite)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)

def write_security_junit_xml(
    results: list,
    output_path: str | Path,
) -> None:
    """Write security check results in JUnit XML format."""
    failures = sum(result.finding is not None for result in results)
    errors = sum(result.error is not None for result in results)

    suite = ET.Element(
        "testsuite",
        {
            "name": "API Sentinel Security",
            "tests": str(len(results)),
            "failures": str(failures),
            "errors": str(errors),
            "skipped": "0",
        },
    )

    for result in results:
        testcase = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": "api_sentinel.security",
                "name": result.name,
                "time": "0",
            },
        )

        if result.finding is not None:
            finding = result.finding
            failure = ET.SubElement(
                testcase,
                "failure",
                {
                    "message": finding.title,
                    "type": finding.check,
                },
            )
            failure.text = (
                f"Severity: {finding.severity}\n"
                f"Evidence: {finding.evidence}\n"
                f"Remediation: {finding.remediation}"
            )
        elif result.error is not None:
            error = ET.SubElement(
                testcase,
                "error",
                {
                    "message": result.error,
                    "type": "SecurityCheckError",
                },
            )
            error.text = result.error

    tree = ET.ElementTree(suite)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
