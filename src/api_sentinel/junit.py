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