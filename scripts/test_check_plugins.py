import importlib.util
from pathlib import Path
import tempfile
import unittest

import yaml


spec = importlib.util.spec_from_file_location(
    'check_plugins', Path(__file__).with_name('check-plugins.py'),
)
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


class WithoutSyncedSkillsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.synced = self.root / 'agents/.agents/skills/synced'

    def add_skill(self, path, name):
        skill = self.synced / path / 'SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text(f'---\nname: {name}\ndescription: Local skill.\n---\n')
        return skill

    def test_absent_synced_directory_preserves_inventory(self):
        actual = {'xlm:owned', 'xlm:unexpected'}
        self.assertEqual(checks.without_synced_skills(self.root, actual, {'xlm:owned'}), actual)

    def test_empty_synced_directory_preserves_inventory(self):
        self.synced.mkdir(parents=True)
        self.assertEqual(checks.without_synced_skills(self.root, set(), set()), set())

    def test_nested_synced_skill_uses_frontmatter_name(self):
        self.add_skill('source/folder-name', 'synced-name')
        actual = {'xlm:owned', 'xlm:synced-name', 'xlm:unexpected'}
        self.assertEqual(
            checks.without_synced_skills(self.root, actual, {'xlm:owned'}),
            {'xlm:owned', 'xlm:unexpected'},
        )

    def test_synced_collision_preserves_expected_name(self):
        self.add_skill('collision', 'owned')
        self.assertEqual(
            checks.without_synced_skills(self.root, {'xlm:owned'}, {'xlm:owned'}),
            {'xlm:owned'},
        )

    def test_synced_skill_cannot_fill_missing_expected_name(self):
        self.add_skill('other', 'other')
        self.assertEqual(
            checks.without_synced_skills(self.root, {'xlm:other'}, {'xlm:owned'}),
            set(),
        )

    def test_malformed_synced_metadata_fails_closed(self):
        skill = self.add_skill('invalid', 'invalid')
        skill.write_text('---\nname: [\n---\n')
        with self.assertRaises(yaml.YAMLError):
            checks.without_synced_skills(self.root, {'xlm:invalid'}, set())


if __name__ == '__main__':
    unittest.main()
