from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "plugin/assets/workflow/analysis/Snakefile"
EXAMPLE = ROOT / "plugin/assets/workflow/analysis/example"


def branch(text: str, mode: str) -> str:
    start = text.index(f'if _MODE == "{mode}":')
    if mode == "present":
        end = text.index("\nelse:\n", start)
        return text[start:end]
    return text[text.index("\nelse:\n", start) + 1:]


def rule_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^    rule {name}:\n", text)
    if match is None:
        raise AssertionError(f"rule {name!r} is missing")
    next_rule = re.search(r"(?m)^    rule \w+:\n", text[match.end():])
    end = match.end() + (next_rule.start() if next_rule else len(text[match.end():]))
    return text[match.start():end]


class SnakemakeTemplateTests(unittest.TestCase):
    def test_presentation_branch_has_no_calculation_rule_ancestor(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        present = branch(text, "present")
        calculation = text[text.index("\nelse:\n") + 1:]
        self.assertIn("rule present:", present)
        self.assertNotIn("rule calculate:", present)
        self.assertIn("rule calculate:", calculation)

        # The active presentation graph contains only rules declared in its
        # branch; no calculation producer can therefore become an ancestor.
        present_rules = set(re.findall(r"(?m)^    rule (\w+):$", present))
        self.assertEqual({"present"}, present_rules)
        self.assertNotIn("calculate", present_rules)

    def test_rule_outputs_are_named_generated_files(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        calculation = text[text.index("\nelse:\n") + 1:]
        for rule_text, name in ((branch(text, "present"), "present"), (calculation, "calculate")):
            outputs = rule_block(rule_text, name).split("        output:", 1)[1]
            outputs = outputs.split("        shell:", 1)[0]
            self.assertNotRegex(outputs, r"['\"]inputs/")
            self.assertNotIn("notebook.qmd", outputs)

    def test_example_scripts_referenced_by_snakefile_exist(self):
        text = (EXAMPLE / "Snakefile").read_text(encoding="utf-8")
        scripts = set(re.findall(r"['\"](scripts/[^'\"]+\.py)['\"]", text))
        self.assertTrue(scripts)
        for relative in scripts:
            self.assertTrue((EXAMPLE / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
