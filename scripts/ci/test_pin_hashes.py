"""Offline tests for the pin tool: wheel selection and the rewrite, with PyPI replaced by a table."""
import unittest

import pin_hashes


def digest(seed: str) -> str:
    return (seed * 64)[:64]


WHEELS = {
    ("pure", "1.0"): ["pure-1.0-py3-none-any.whl"],
    ("native", "2.0"): ["native-2.0-cp314-cp314-win_amd64.whl",
                        "native-2.0-cp314-cp314-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
                        "native-2.0-cp314-cp314-musllinux_1_2_x86_64.whl",
                        "native-2.0-cp313-cp313-win_amd64.whl",
                        "native-2.0-cp314-cp314t-win_amd64.whl"],
    ("stable", "3.0"): ["stable-3.0-cp311-abi3-win_amd64.whl", "stable-3.0-cp311-abi3-manylinux_2_28_x86_64.whl",
                        "stable-3.0-cp311-abi3-win32.whl"],
    ("winonly", "4.0"): ["winonly-4.0-cp314-cp314-win_amd64.whl"],
}


def wheels(name, version):
    return [{"filename": f, "digests": {"sha256": digest(format(n, "x"))}}
            for n, f in enumerate(WHEELS[(name, version)], start=1)]


class InstallableTests(unittest.TestCase):
    def test_only_wheels_the_target_interpreter_can_install_on_a_supported_platform(self):
        cases = {
            "pure-1.0-py3-none-any.whl": True,
            "native-2.0-cp314-cp314-win_amd64.whl": True,
            "native-2.0-cp314-cp314-manylinux_2_17_x86_64.manylinux2014_x86_64.whl": True,
            "native-2.0-cp314-cp314-macosx_11_0_arm64.whl": True,
            "native-2.0-cp314-cp314-musllinux_1_2_x86_64.whl": False,   # the image is glibc
            "native-2.0-cp314-cp314-win32.whl": False,
            "native-2.0-cp313-cp313-win_amd64.whl": False,              # another interpreter
            "native-2.0-cp314-cp314t-win_amd64.whl": False,             # free-threaded build
            "stable-3.0-cp311-abi3-win_amd64.whl": True,                # stable ABI from 3.11 on
            "stable-3.0-cp315-abi3-win_amd64.whl": False,               # needs a newer interpreter
            "source-1.0.tar.gz": False,
        }
        for filename, expected in cases.items():
            with self.subTest(filename=filename):
                self.assertEqual(pin_hashes.installable(filename, 14), expected)


class RewriteTests(unittest.TestCase):
    def test_hashes_are_replaced_and_everything_else_is_kept(self):
        before = ("# header\n--only-binary=:all:\n\npure==1.0 \\\n    --hash=sha256:" + digest("f") + "\n"
                  "# a note\nnative[extra]==2.0 \\\n    --hash=sha256:" + digest("e") + " \\\n"
                  "    --hash=sha256:" + digest("d") + "\n")
        after = pin_hashes.rewrite(before, 14, False, wheels)
        self.assertEqual(after, "# header\n--only-binary=:all:\n\npure==1.0 \\\n    --hash=sha256:" + digest("1") + "\n"
                                "# a note\nnative[extra]==2.0 \\\n    --hash=sha256:" + digest("1") + " \\\n"
                                "    --hash=sha256:" + digest("2") + "\n")

    def test_a_pin_whose_hashes_are_already_right_keeps_its_lines_and_order(self):
        before = ("native==2.0 \\\n    --hash=sha256:" + digest("2") + " \\\n    --hash=sha256:" + digest("1") + "\n")
        self.assertEqual(pin_hashes.rewrite(before, 14, False, wheels), before)

    def test_all_wheels_keeps_every_published_wheel(self):
        after = pin_hashes.rewrite("native==2.0 \\\n    --hash=sha256:" + digest("9") + "\n", 14, True, wheels)
        self.assertEqual(after.count("--hash=sha256:"), 5)

    def test_a_pin_without_a_linux_or_windows_wheel_is_an_error(self):
        with self.assertRaises(SystemExit) as raised:
            pin_hashes.rewrite("winonly==4.0 \\\n    --hash=sha256:" + digest("9") + "\n", 14, False, wheels)
        self.assertIn("Linux x64", str(raised.exception))
        with self.assertRaises(SystemExit):
            pin_hashes.rewrite("native==2.0 \\\n    --hash=sha256:" + digest("9") + "\n", 12, False, wheels)

    def test_hash_sets_ignore_line_order(self):
        one = "a==1 \\\n    --hash=sha256:" + digest("1") + " \\\n    --hash=sha256:" + digest("2") + "\n"
        two = "a==1 \\\n    --hash=sha256:" + digest("2") + " \\\n    --hash=sha256:" + digest("1") + "\n"
        self.assertEqual(pin_hashes.hash_sets(one), pin_hashes.hash_sets(two))


if __name__ == "__main__":
    unittest.main()
