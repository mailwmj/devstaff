import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "site-builder" / "scripts" / "state.py"


class StateCliTests(unittest.TestCase):
    def run_cli(self, *args, expected=0):
        result = subprocess.run(
            ["python3", str(SCRIPT), *map(str, args)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_guided_cli_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialized = self.run_cli("init", root, "--mode", "guided")
            self.assertEqual(initialized["next_action"], "prepare_and_confirm_direction")

            self.run_cli(
                "decide",
                root,
                "--task",
                "登记库存",
                "--direction",
                "单工作台",
                "--quote",
                "就按这个方向做",
            )
            self.run_cli("start", root)
            delivered = self.run_cli(
                "verify",
                root,
                "--status",
                "verified",
                "--evidence",
                "新增库存后刷新仍可见",
            )
            self.assertEqual(delivered["next_action"], "report_delivery")

    def test_invalid_transition_returns_machine_readable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_cli("init", root)
            result = self.run_cli("start", root, expected=2)
            self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
