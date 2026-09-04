"""Keep published action examples aligned with the registered API contract."""
import json
from pathlib import Path
import re
import unittest

import editor_engine as engine


class ActionDocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.catalog = json.loads(
            (root / "static" / "action-docs.json").read_text(encoding="utf-8")
        )
        cls.markdown = (root / "ACTIONS.md").read_text(encoding="utf-8")

    def test_catalog_covers_registered_actions_and_valid_categories(self):
        documented = self.catalog["actions"]
        self.assertEqual(len(engine.ACTIONS), 89)
        self.assertEqual(set(documented), set(engine.ACTIONS))

        category_ids = [category["id"] for category in self.catalog["categories"]]
        self.assertEqual(len(category_ids), len(set(category_ids)))
        assigned = {entry["category"] for entry in documented.values()}
        self.assertEqual(assigned, set(category_ids))

    def test_every_catalog_example_passes_the_strict_operation_contract(self):
        for name, entry in self.catalog["actions"].items():
            with self.subTest(action=name):
                operation = entry["example"]
                self.assertEqual(operation["action"], name)
                self.assertEqual(set(operation), {"action", "args"})
                validator = engine.StrictValidator(engine.ACTIONS[name]["schema"])
                validator.validate(operation["args"])
                engine.validate_operations([operation])

    def test_markdown_has_one_reference_entry_per_registered_action(self):
        entries = re.findall(r"^### `([^`]+)`\s*$", self.markdown, re.MULTILINE)
        self.assertEqual(len(entries), len(set(entries)))
        self.assertEqual(set(entries), set(engine.ACTIONS))


if __name__ == "__main__":
    unittest.main()
