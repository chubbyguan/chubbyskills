"""Keep distributed skills compatible with the Agent Skills/Codex contract."""

from pathlib import Path
import re
import unittest

import yaml

from tools.install_skill import SUPPORTED_SKILLS


ROOT = Path(__file__).resolve().parents[1]
# The common subset supported by the Agent Skills specification and Codex's
# quick validator. Project-specific fields belong in metadata.
ALLOWED_FIELDS = {"name", "description", "license", "allowed-tools", "metadata"}


class SkillMetadataTest(unittest.TestCase):
    def test_every_distributed_skill_has_valid_frontmatter(self):
        for skill in sorted(SUPPORTED_SKILLS):
            with self.subTest(skill=skill):
                content = (ROOT / skill / "SKILL.md").read_text(encoding="utf-8")
                match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", content, re.DOTALL)
                self.assertIsNotNone(match, "SKILL.md must start with YAML frontmatter")
                fields = yaml.safe_load(match.group(1))
                self.assertIsInstance(fields, dict)
                self.assertLessEqual(set(fields), ALLOWED_FIELDS)

                name = fields.get("name")
                self.assertEqual(name, skill, "Skill name must match its install directory")
                self.assertRegex(name, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
                self.assertLessEqual(len(name), 64)

                description = fields.get("description")
                self.assertIsInstance(description, str)
                self.assertTrue(description.strip(), "Description must explain when to use the skill")
                self.assertLessEqual(len(description), 1024)
                self.assertNotRegex(description, r"[<>]")

                metadata = fields.get("metadata", {})
                self.assertIsInstance(metadata, dict)
                for key, value in metadata.items():
                    self.assertIsInstance(key, str)
                    self.assertIsInstance(value, str, f"metadata.{key} must be a string")


if __name__ == "__main__":
    unittest.main()
