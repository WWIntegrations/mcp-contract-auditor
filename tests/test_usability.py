import contextlib
import io
import json
from pathlib import Path
import tempfile
import unicodedata
import unittest
from mcp_auditor import summary
from mcp_auditor.cli import main

ROOT = Path(__file__).resolve().parents[1]
BASE = str(ROOT / 'examples' / 'baseline-transcript.json')
CAND = str(ROOT / 'examples' / 'candidate-transcript.json')


def call(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


class UsabilityTests(unittest.TestCase):
    def test_demo_default_is_short_human_summary_and_json_flag_keeps_artifact(self):
        code, out, err = call(['demo'])
        self.assertEqual((code, err), (0, ''))
        self.assertLess(len(out), 2500)
        for word in ('CHANGES NEED REVIEW', 'Findings:', 'Audit digest', 'rejected (stale)', 'Limits:'):
            self.assertIn(word, out)
        self.assertNotIn('{', out)
        self.assertIn('Receipt by Synthetic local operator', out)
        code, out, err = call(['demo', '--json'])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)['synthetic'])

    def test_compare_examples_exit_zero_unless_strict(self):
        code, out, err = call(['compare', BASE, CAND])
        self.assertEqual((code, err), (0, ''))
        self.assertIn('tool_added', out)
        self.assertEqual(call(['compare', BASE, CAND, '--strict'])[0], 1)
        self.assertIn('IDENTICAL', call(['compare', BASE, BASE])[1])
        report = json.loads(call(['compare', BASE, CAND, '--json'])[1])
        self.assertEqual(len(report['findings']), 5)

    def test_out_refuses_overwrite_unless_forced(self):
        with tempfile.TemporaryDirectory() as td:
            target = str(Path(td) / 'baseline.json')
            code, out, err = call(['import', BASE, '--out', target])
            self.assertEqual(code, 0)
            self.assertIn('Imported 5 tools', out)
            self.assertEqual(json.loads(Path(target).read_text())['format_version'], 1)
            code, out, err = call(['import', BASE, '--out', target])
            self.assertEqual((code, out, err.strip()), (2, '', 'output_exists'))
            self.assertEqual(call(['import', BASE, '--out', target, '--force'])[0], 0)

    def test_full_flow_with_summaries(self):
        with tempfile.TemporaryDirectory() as td:
            b, c, r = (str(Path(td) / n) for n in ('b.json', 'c.json', 'r.json'))
            call(['import', BASE, '--out', b])
            call(['import', CAND, '--out', c])
            code, out, _ = call(['diff', b, c])
            self.assertEqual(code, 1)
            self.assertIn('To acknowledge', out)
            digest = json.loads(call(['diff', b, c, '--json'])[1])['audit_digest']
            code, out, _ = call(['confirm', b, c, '--expected-digest', digest, '--reviewer', 'Me', '--out', r])
            self.assertEqual(code, 0)
            self.assertIn('not authorization', out)
            code, out, _ = call(['check-receipt', b, c, r])
            self.assertEqual(code, 0)
            self.assertIn('MATCHES', out)
            self.assertEqual(call(['check-receipt', b, b, r])[0], 1)

    def test_terminal_control_characters_are_escaped(self):
        evil = '\x1b]8;;http://evil\x1b\\X‮\r\n⁦'
        escaped = summary.safe(evil)
        self.assertIn('\\x1b', escaped)
        self.assertIn('\\u202e', escaped)
        self.assertFalse([ch for ch in escaped if unicodedata.category(ch).startswith('C')])
        snap = {'tools': [{'name': evil}], 'origin_id': evil, 'scope_id': evil, 'contract_digest': 'd'}
        sev = dict(high=1, review=0, unknown=0, info=0)
        side = dict(compatible=0, breaking=0, unknown=0, not_declared=0)
        report = {'summary': {'severity': sev, 'input': side, 'output': side}, 'baseline_digest': 'a', 'candidate_digest': 'b',
                  'tool_count': {'baseline': 1, 'candidate': 1}, 'origin_id': evil, 'scope_id': evil, 'audit_digest': 'x',
                  'findings': [{'severity': evil, 'tool': evil, 'reason_code': evil, 'pointer': evil}]}
        for text in (summary.import_text(snap, evil), summary.diff_text(report, hint=True),
                     summary.confirm_text({'audit_digest': 'x', 'reviewer': evil}, evil)):
            self.assertFalse([ch for ch in text if ch != '\n' and unicodedata.category(ch).startswith('C')], repr(text))
            self.assertIn('\\x1b', text)


if __name__ == '__main__':
    unittest.main()
