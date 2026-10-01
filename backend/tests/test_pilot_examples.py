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

    def reviewed_source_backed_pack(self):
        examples = copy.deepcopy(self.examples)
        examples["status"] = "reviewed"
        for item in list(examples["examples"]):
            if item["role"] == "practice":
                input_item = copy.deepcopy(item)
                input_item["id"] += "-input"
                input_item["role"] = "input"
                outcome = next(
                    outcome for outcome in self.curriculum["outcomes"]
                    if outcome["id"] == item["outcome_id"]
                )
                input_item["family_id"] = outcome["families"]["input"][0]
                input_item["text_nfc"] += " Primer."
                input_item["translation_ru_nfc"] += " Пример."
                input_item["answer_policy"]["id"] += "-input"
                examples["examples"].append(input_item)

        material = {
            "rights": {"analysis": "allowed", "redistribution": "allowed", "adaptation": "allowed"},
            "license": "test fixture", "evidence_url": "https://example.test/fixture",
            "reviewer": "test fixture", "reviewed_on": "2026-09-25",
            "attribution_required": False, "share_alike_required": False,
        }
        source = {
            "source_id": "test-reviewed-pack", "kind": "authored", "release_id": "test-fixture",
            "review": {"reviewer": "test fixture", "reviewed_on": "2026-09-25",
                       "evidence_url": "https://example.test/fixture"},
            "items": [],
        }
        for item in examples["examples"]:
            item_id = item["id"]
            item["source"] = {"source_id": source["source_id"], "item_id": item_id}
            item["review_status"] = "approved"
            item["answer_policy"]["review_status"] = "approved"
            source["items"].append({
                "item_id": item_id,
                "materials": {"text": copy.deepcopy(material), "translation": copy.deepcopy(material)},
            })
        return examples, {"schema_version": 1, "sources": [source]}

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

    def test_example_validation_rejects_overlapping_curriculum_families(self):
        curriculum = copy.deepcopy(self.curriculum)
        outcome = curriculum["outcomes"][0]
        outcome["families"]["assessment"].append(outcome["families"]["practice"][0])
        result = self.check_fixture(curriculum=curriculum)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("practice/assessment family overlap", result.stderr)

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

    def test_reviewed_empty_pack_cannot_publish_without_outcome_role_coverage(self):
        examples = {"schema_version": 1, "status": "reviewed", "examples": []}
        result = self.check_fixture(examples=examples, publish=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing publish coverage", result.stderr)
        self.assertIn("A1.PERSONAL_DETAILS/input", result.stderr)

    def test_reviewed_pack_requires_each_outcome_role(self):
        examples = copy.deepcopy(self.examples)
        examples["status"] = "reviewed"
        for item in examples["examples"]:
            item["review_status"] = "approved"
            item["answer_policy"]["review_status"] = "approved"
        examples["examples"] = [
            item for item in examples["examples"]
            if item["id"] != "ex-location-holdout"
        ]
        result = self.check_fixture(examples=examples, publish=True)
        self.assertIn("A1.LOCATION_INFO/assessment", result.stderr)
        self.assertIn("A1.LOCATION_INFO/input", result.stderr)

    def test_practice_answer_variant_cannot_reveal_assessment_answer(self):
        examples = copy.deepcopy(self.examples)
        examples["status"] = "reviewed"
        for item in examples["examples"]:
            item["review_status"] = "approved"
            item["answer_policy"]["review_status"] = "approved"
        practice = next(item for item in examples["examples"] if item["id"] == "ex-request-practice")
        assessment = next(item for item in examples["examples"] if item["id"] == "ex-request-holdout")
        practice["answer_policy"]["accepted_variants"].append(
            assessment["answer_policy"]["accepted_variants"][0]
        )
        result = self.check_fixture(examples=examples, publish=True)
        self.assertIn("holdout leakage", result.stderr)

    def test_publish_rejects_assessment_answer_inside_visible_practice_text(self):
        examples, sources = self.reviewed_source_backed_pack()
        baseline = self.check_fixture(examples=examples, sources=sources, publish=True)
        self.assertEqual(baseline.returncode, 0, baseline.stderr)

        practice = next(item for item in examples["examples"] if item["id"] == "ex-price-practice")
        practice["text_nfc"] = "Čaj — 90 dinara."
        practice["target"].update(surface="Čaj — 90 dinara", end=len("Čaj — 90 dinara"))
        result = self.check_fixture(examples=examples, sources=sources, publish=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("holdout leakage", result.stderr)

    def test_publish_rejects_assessment_answer_inside_visible_input_text(self):
        examples, sources = self.reviewed_source_backed_pack()
        input_item = next(item for item in examples["examples"] if item["id"] == "ex-price-practice-input")
        input_item["text_nfc"] = "Čaj — 90 dinara. Primer."
        input_item["target"].update(surface="Čaj — 90 dinara", end=len("Čaj — 90 dinara"))
        result = self.check_fixture(examples=examples, sources=sources, publish=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("holdout leakage", result.stderr)

    def test_publish_rejects_assessment_answer_inside_visible_translation(self):
        examples, sources = self.reviewed_source_backed_pack()
        practice = next(item for item in examples["examples"] if item["id"] == "ex-price-practice")
        practice["translation_ru_nfc"] = "Чай стоит 90 dinara."
        result = self.check_fixture(examples=examples, sources=sources, publish=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("holdout leakage", result.stderr)

    def test_publish_rejects_assessment_answer_inside_visible_answer_variant(self):
        for example_id in ("ex-price-practice", "ex-price-practice-input"):
            with self.subTest(example_id=example_id):
                examples, sources = self.reviewed_source_backed_pack()
                baseline = self.check_fixture(examples=examples, sources=sources, publish=True)
                self.assertEqual(baseline.returncode, 0, baseline.stderr)

                visible = next(item for item in examples["examples"] if item["id"] == example_id)
                visible["answer_policy"]["accepted_variants"].append("Cena je 90 dinara")
                result = self.check_fixture(examples=examples, sources=sources, publish=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("holdout leakage", result.stderr)

    def test_publish_ignores_larger_tokens_in_practice_answer_variant(self):
        for variant in ("Cena je 190 dinara", "Cena je 90 dinaraza"):
            with self.subTest(variant=variant):
                examples, sources = self.reviewed_source_backed_pack()
                practice = next(item for item in examples["examples"] if item["id"] == "ex-price-practice")
                practice["answer_policy"]["accepted_variants"].append(variant)
                result = self.check_fixture(examples=examples, sources=sources, publish=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_publish_ignores_assessment_answer_inside_larger_tokens(self):
        for field, visible_text in (
            ("text_nfc", "Čaj — 190 dinara."),
            ("text_nfc", "Čaj — 90 dinaraza."),
            ("translation_ru_nfc", "Чай стоит 190 dinara."),
            ("translation_ru_nfc", "Чай стоит 90 dinaraza."),
        ):
            with self.subTest(field=field, visible_text=visible_text):
                examples, sources = self.reviewed_source_backed_pack()
                practice = next(item for item in examples["examples"] if item["id"] == "ex-price-practice")
                practice[field] = visible_text
                if field == "text_nfc":
                    practice["target"].update(surface=visible_text[:-1], end=len(visible_text) - 1)
                result = self.check_fixture(examples=examples, sources=sources, publish=True)
                self.assertEqual(result.returncode, 0, result.stderr)

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
