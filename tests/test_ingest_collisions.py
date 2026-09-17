import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import chubby_ingest


class CollisionSafetyTest(unittest.TestCase):
    def make_note(self, root, body='Original'):
        root.mkdir(parents=True, exist_ok=True)
        note = root / 'Same title.md'
        assets = root / 'Same title.assets'
        assets.mkdir()
        (assets / 'image.png').write_bytes(body.encode())
        note.write_text(f'# Same title\n{body}\n![image](Same title.assets/image.png)\n', encoding='utf-8')
        return note

    def test_same_title_different_source_keeps_both_bundles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.make_note(root/'a', 'first')
            second = self.make_note(root/'b', 'second')
            a = Path(chubby_ingest.publish_bundle(first, root/'out', source='https://x.com/u/status/1'))
            b = Path(chubby_ingest.publish_bundle(second, root/'out', source='https://x.com/u/status/2'))
            self.assertNotEqual(a, b)
            for output, expected in ((a, 'first'), (b, 'second')):
                self.assertIn(expected, output.read_text())
                self.assertIn(output.stem+'.assets/image.png', output.read_text())
                self.assertEqual((output.with_suffix('.assets')/'image.png').read_bytes(), expected.encode())

    def test_refresh_never_overwrites_user_edits_or_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staged = self.make_note(root/'stage')
            first = Path(chubby_ingest.publish_bundle(staged, root/'out', source='https://x.com/u/status/1'))
            first.write_text('User edits')
            (first.with_suffix('.assets')/'image.png').write_bytes(b'user asset')
            second = Path(chubby_ingest.publish_bundle(staged, root/'out', source='https://x.com/u/status/1'))
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_text(), 'User edits')
            self.assertEqual((first.with_suffix('.assets')/'image.png').read_bytes(), b'user asset')

    def test_vault_copy_collision_also_preserves_existing_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            note = self.make_note(root/'stage')
            one = Path(chubby_ingest.copy_into_vault(str(note), str(root/'vault')))
            one.write_text('User edits')
            two = Path(chubby_ingest.copy_into_vault(str(note), str(root/'vault')))
            self.assertNotEqual(one, two)
            self.assertEqual(one.read_text(), 'User edits')
            self.assertIn(two.stem+'.assets/image.png', two.read_text())

    def test_adapter_runs_in_isolated_output_before_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'output'
            seen = []
            def run(cmd, dry_run=False):
                stage = Path(cmd[cmd.index('--output')+1])
                seen.append(stage)
                return str(self.make_note(stage))
            with patch.object(chubby_ingest, 'run_command', side_effect=run), patch('sys.argv',
                    ['chubby_ingest.py', 'https://x.com/u/status/1', '--output', str(output)]):
                self.assertEqual(chubby_ingest.main(), 0)
            self.assertNotEqual(seen[0], output)
            self.assertFalse(seen[0].exists())
            self.assertEqual(len(list(output.glob('*.md'))), 1)


if __name__ == '__main__':
    unittest.main()
