"""Contract checks for the provisional, file-backed written pilot."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "content/curricula/a1-pilot/validate.py"
MANIFEST = ROOT / "content/curricula/a1-pilot/manifest.json"


class PilotManifestTests(unittest.TestCase):
    def run_validator(self, manifest):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            return subprocess.run(
                ["python3", str(VALIDATOR), str(path)],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_checked_in_manifest_has_four_complete_written_outcomes(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        result = self.run_validator(manifest)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            {outcome["id"] for outcome in manifest["outcomes"]},
            {"A1.PERSONAL_DETAILS", "A1.SIMPLE_REQUEST", "A1.PRICE_INFO", "A1.LOCATION_INFO"},
        )
        self.assertEqual({edge["kind"] for edge in manifest["edges"]}, {"soft"})

    def test_duplicate_id_is_rejected(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["targets"].append(dict(manifest["targets"][0]))
        self.assertIn("duplicate target id", self.run_validator(manifest).stderr)

    def test_unresolved_target_reference_is_rejected(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["outcomes"][0]["target_ids"] = ["missing.target"]
        self.assertIn("unknown target", self.run_validator(manifest).stderr)

    def test_unresolved_edge_reference_is_rejected(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["edges"][0]["to"] = "A1.NOT_IN_PILOT"
        self.assertIn("unresolved edge", self.run_validator(manifest).stderr)

    def test_missing_rubric_dimension_is_rejected(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["outcomes"][0]["rubric"]["communicative_success"] = ""
        self.assertIn("rubric communicative_success missing", self.run_validator(manifest).stderr)

    def test_hard_edge_cycle_is_rejected(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["edges"] = [
            {"id": "e1", "from": "A1.PERSONAL_DETAILS", "to": "A1.PRICE_INFO", "kind": "hard"},
            {"id": "e2", "from": "A1.PRICE_INFO", "to": "A1.PERSONAL_DETAILS", "kind": "hard"},
        ]
        self.assertIn("hard edge cycle", self.run_validator(manifest).stderr)

    def test_practice_holdout_family_overlap_is_rejected(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["outcomes"][0]["families"]["assessment"] = manifest["outcomes"][0]["families"]["practice"]
        self.assertIn("practice/assessment family overlap", self.run_validator(manifest).stderr)


if __name__ == "__main__":
    unittest.main()
