import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

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


class CopilotSkillNamesTests(unittest.TestCase):
    def test_plugin_names_preserve_punctuation_and_digits(self):
        self.assertEqual(
            checks.copilot_skill_names(
                'Plugin skills:\n  nextjs16 - Description.\n  code-review - More - detail.\n'
            ),
            {'nextjs16', 'code-review'},
        )

    def test_other_sections_and_description_mentions_are_ignored(self):
        output = ('Personal skills:\n  personal - Plugin skills:\n\n'
                  'Plugin skills:\n  owned - Description.\n\n'
                  'Builtin skills:\n  builtin - Description.\n')
        self.assertEqual(checks.copilot_skill_names(output), {'owned'})

    def test_empty_or_missing_section(self):
        for output in ('', 'Plugin skills:\n\n', 'Builtin skills:\n  other - Other.\n'):
            with self.subTest(output=output):
                self.assertEqual(checks.copilot_skill_names(output), set())

    def test_heading_must_match_exactly(self):
        cases = {
            'wrong capitalization': 'plugin skills:',
            'missing colon': 'Plugin skills',
            'indented heading': '  Plugin skills:',
        }
        for case, heading in cases.items():
            with self.subTest(case=case, heading=heading):
                self.assertEqual(
                    checks.copilot_skill_names(heading + '\n  other - Other.\n'), set(),
                )

    def test_malformed_entry_is_rejected(self):
        cases = {
            'missing separator': 'missing-separator',
            'missing description': 'name - ',
            'missing name': ' - Description.',
            'missing spaces around separator': 'name-Description.',
        }
        for case, entry in cases.items():
            with self.subTest(case=case, entry=entry), self.assertRaises(ValueError):
                checks.copilot_skill_names('Plugin skills:\n  ' + entry + '\n')


class PromptSkillNamesTests(unittest.TestCase):
    def test_names_keep_digits_and_hyphens(self):
        prompt = '- xlm:code-review: Review.\n- xlm:nextjs16 (file: x)\n'
        self.assertEqual(
            checks.prompt_skill_names(prompt), {'xlm:code-review', 'xlm:nextjs16'},
        )

    def test_other_namespaces_are_ignored(self):
        self.assertEqual(checks.prompt_skill_names('other:skill xlmx:no'), set())


class CodexHookListTests(unittest.TestCase):
    def listed(self, *hooks, errors=()):
        reply = {'id': 2, 'result': {'data': [{'hooks': list(hooks), 'errors': list(errors)}]}}
        with mock.patch.object(checks, 'read_hook_reply', return_value=reply):
            return checks.list_codex_hooks(mock.Mock(), Path('/work'))

    def hook(self, path='/cache/xlm/.codex-plugin/hooks.json', **overrides):
        return {'pluginId': 'xlm@dotagents', 'eventName': 'sessionStart', 'source': 'plugin',
                'enabled': True, 'sourcePath': path, **overrides}

    def test_one_hook_from_codex_file(self):
        self.assertEqual(self.listed(self.hook()), [self.hook()])

    def test_other_hooks_are_ignored(self):
        others = [self.hook(pluginId='other@market'), self.hook(eventName='stop'),
                  self.hook(source='user'), self.hook(enabled=False)]
        self.assertEqual(self.listed(self.hook(), *others), [self.hook()])

    def test_rejected_hook_sets(self):
        cases = {
            'no hook': [],
            'two hooks': [self.hook(), self.hook(path='/cache/xlm/hooks/hooks.json')],
            'shared Claude file': [self.hook(path='/cache/xlm/hooks/hooks.json')],
            'file name without folder': [self.hook(path='/cache/xlm/my.codex-plugin/hooks.json')],
        }
        for case, hooks in cases.items():
            with self.subTest(case=case), self.assertRaises(SystemExit):
                self.listed(*hooks)

    def test_hook_errors_fail(self):
        with self.assertRaises(SystemExit):
            self.listed(self.hook(), errors=['bad hook'])


class ClaudeHookTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'AGENTS.md').write_text('rules\n')

    def response(self, **overrides):
        return {'type': 'system', 'subtype': 'hook_response', 'hook_event': 'SessionStart',
                'exit_code': 0, 'outcome': 'success',
                'stdout': 'Global rules from /x/AGENTS.md:\n\nrules\n', **overrides}

    def test_one_successful_response(self):
        checks.claude_hook(self.root, [{'type': 'system', 'subtype': 'init'}, self.response()])

    def test_rejected_responses(self):
        cases = {
            'no response': [],
            'two responses': [self.response(), self.response()],
            'other event only': [self.response(hook_event='Stop')],
            'nonzero exit': [self.response(exit_code=1)],
            'failed outcome': [self.response(outcome='error')],
            'wrong rules': [self.response(stdout='other')],
            'missing stdout': [{k: v for k, v in self.response().items() if k != 'stdout'}],
        }
        for case, events in cases.items():
            with self.subTest(case=case), self.assertRaises(SystemExit):
                checks.claude_hook(self.root, events)

    def test_empty_rules_fail(self):
        (self.root / 'AGENTS.md').write_text('')
        with self.assertRaises(SystemExit):
            checks.claude_hook(self.root, [self.response()])


if __name__ == '__main__':
    unittest.main()
