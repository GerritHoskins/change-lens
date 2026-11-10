"""The CI result gate cannot turn unavailable services or empty collection into green."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from check_integration_result import inspect, main


class IntegrationResultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.report = Path(self.temp.name) / "integration.xml"

    def check(self, xml: str):
        self.report.write_text(xml, encoding="utf-8")
        return inspect(self.report)

    def test_nonempty_passing_pytest_report_is_accepted(self):
        result, errors = self.check('<testsuites><testsuite tests="2" skipped="0" failures="0" errors="0">'
                                   '<testcase name="a"/><testcase name="b"/></testsuite></testsuites>')
        self.assertEqual(errors, [])
        self.assertEqual(result["tests"], 2)

    def test_unavailable_services_skipping_every_test_is_rejected(self):
        _, errors = self.check('<testsuites><testsuite tests="1" skipped="1">'
                               '<testcase name="tenant"><skipped message="Postgres unavailable"/>'
                               '</testcase></testsuite></testsuites>')
        self.assertTrue(any("skipped" in error for error in errors))

    def test_one_skipped_test_among_passes_is_rejected(self):
        _, errors = self.check('<testsuite tests="2" skipped="1"><testcase name="pass"/>'
                               '<testcase name="skip"><skipped/></testcase></testsuite>')
        self.assertTrue(errors)

    def test_failure_and_setup_error_are_rejected(self):
        for element in ("failure", "error"):
            with self.subTest(element=element):
                _, errors = self.check(f'<testsuite><testcase><{element}/></testcase></testsuite>')
                self.assertTrue(errors)

    def test_empty_or_summary_only_reports_are_rejected(self):
        for xml in ('<testsuites/>', '<testsuite tests="0"/>', '<testsuite tests="99"/>'):
            with self.subTest(xml=xml):
                _, errors = self.check(xml)
                self.assertTrue(any("no integration" in error for error in errors))

    def test_misleading_summary_counts_are_rejected(self):
        for attributes in ('tests="2"', 'skipped="1"', 'failures="1"', 'errors="1"', 'tests="no"'):
            with self.subTest(attributes=attributes):
                _, errors = self.check(f'<testsuite {attributes}><testcase/></testsuite>')
                self.assertTrue(any("inconsistent" in error for error in errors))

    def test_nested_suite_aggregates_do_not_double_count_cases(self):
        result, errors = self.check('<testsuites tests="2"><testsuite tests="1"><testcase/>'
                                   '</testsuite><testsuite tests="1"><testcase/></testsuite></testsuites>')
        self.assertEqual(errors, [])
        self.assertEqual(result["tests"], 2)

    def test_missing_malformed_or_wrong_format_reports_fail_closed(self):
        self.assertTrue(inspect(self.report)[1])
        for xml in ('not xml', '<testsuites>', '<report><testcase/></report>'):
            with self.subTest(xml=xml):
                self.assertTrue(self.check(xml)[1])

    def test_cli_exit_code_is_nonzero_for_missing_or_skipped_report(self):
        with redirect_stdout(StringIO()):
            self.assertEqual(main([str(self.report)]), 1)
            self.check('<testsuite><testcase><skipped/></testcase></testsuite>')
            self.assertEqual(main([str(self.report)]), 1)
            self.check('<testsuite><testcase/></testsuite>')
            self.assertEqual(main([str(self.report)]), 0)


if __name__ == "__main__":
    unittest.main()
