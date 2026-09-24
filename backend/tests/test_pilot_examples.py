"""File-backed pilot fixture checks without publishing synthetic content."""

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "content/curricula/a1-pilot"


class PilotExampleTests(unittest.TestCase):
    def setUp(self):
        self.examples = json.loads((PACK / "examples.synthetic.json").read_text(encoding="utf-8"))
        self.curriculum = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))
        self.sources = json.loads((ROOT / "content/sources/manifest.json").read_text(encoding="utf-8"))

    def check_fixture(self, examples=None, curriculum=None, sources=None, publish=False):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ("examples.json", "curriculum.json", "sources.json")]
            for path, data in zip(paths, (examples or self.examples, curriculum or self.curriculum,
                                          sources or self.sources)):
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return subprocess.run(
                ["python3", str(PACK / "validate_examples.py"),
                 "--examples", str(paths[0]), "--curriculum", str(paths[1]),
                 "--sources", str(paths[2]), *( ["--publish"] if publish else [])],
                capture_output=True, text=True, check=False,
            )

    def test_synthetic_fixture_validates_but_cannot_publish(self):
        self.assertEqual(self.check_fixture().returncode, 0)
        self.assertIn("synthetic", self.check_fixture(publish=True).stderr)

    def test_unknown_target_or_family_is_rejected(self):
        examples = copy.deepcopy(self.examples)
        examples["examples"][0]["target"]["id"] = "missing"
        self.assertIn("unknown target", self.check_fixture(examples=examples).stderr)
        examples = copy.deepcopy(self.examples)
        examples["examples"][0]["family_id"] = "missing"
        self.assertIn("unresolved family", self.check_fixture(examples=examples).stderr)

    def test_missing_source_item_is_rejected(self):
        examples = copy.deepcopy(self.examples)
        examples["examples"][0]["source"]["item_id"] = "missing"
        self.assertIn("unresolved source item", self.check_fixture(examples=examples).stderr)

    def test_nfc_and_target_span_reconstruction_are_required(self):
        examples = copy.deepcopy(self.examples)
        examples["examples"][0]["text_nfc"] = examples["examples"][0]["text_nfc"].replace("ž", "z\u030c")
        self.assertIn("NFC", self.check_fixture(examples=examples).stderr)
        examples = copy.deepcopy(self.examples)
        examples["examples"][0]["target"]["end"] += 1
        self.assertIn("target span", self.check_fixture(examples=examples).stderr)

    def test_transliteration_or_translation_reuse_cannot_cross_holdout(self):
        examples = copy.deepcopy(self.examples)
        holdout = next(item for item in examples["examples"] if item["id"] == "ex-personal-holdout")
        holdout["text_nfc"] = "Мила живи у Нишу."
        holdout["target"].update(start=5, end=16, surface="живи у Нишу")
        self.assertIn("holdout leakage", self.check_fixture(examples=examples).stderr)
        examples = copy.deepcopy(self.examples)
        practice = next(item for item in examples["examples"] if item["role"] == "practice")
        holdout = next(item for item in examples["examples"] if item["role"] == "assessment")
        holdout["translation_ru_nfc"] = practice["translation_ru_nfc"]
        self.assertIn("holdout leakage", self.check_fixture(examples=examples).stderr)

    def test_duplicate_ids_and_unreviewed_answer_policy_block_publication(self):
        examples = copy.deepcopy(self.examples)
        examples["examples"][1]["id"] = examples["examples"][0]["id"]
        self.assertIn("duplicate example id", self.check_fixture(examples=examples).stderr)
        self.assertIn("draft", self.check_fixture(publish=True).stderr)

    def test_missing_translation_or_source_permission_is_rejected(self):
        examples = copy.deepcopy(self.examples)
        examples["examples"][0]["translation_ru_nfc"] = ""
        self.assertIn("NFC text/translation required", self.check_fixture(examples=examples).stderr)

        examples = copy.deepcopy(self.examples)
        examples["examples"][0]["source"] = {"source_id": "test-author", "item_id": "test-item"}
        material = {
            "rights": {"analysis": "allowed", "redistribution": "unknown", "adaptation": "unknown"},
            "license": "test-only placeholder", "evidence_url": "https://example.test/test-only",
            "reviewer": "test-only", "reviewed_on": "2026-09-24",
            "attribution_required": False, "share_alike_required": False,
        }
        sources = {"schema_version": 1, "sources": [{
            "source_id": "test-author", "kind": "authored", "release_id": "test-only",
            "review": {"reviewer": "test-only", "reviewed_on": "2026-09-24",
                       "evidence_url": "https://example.test/test-only"},
            "items": [{"item_id": "test-item", "materials": {"text": material,
                       "translation": copy.deepcopy(material)}}],
        }]}
        self.assertIn("redistribution is unknown",
                      self.check_fixture(examples=examples, sources=sources, publish=True).stderr)
        del sources["sources"][0]["items"][0]["materials"]["translation"]
        self.assertIn("source translation rights missing",
                      self.check_fixture(examples=examples, sources=sources, publish=True).stderr)


if __name__ == "__main__":
    unittest.main()
