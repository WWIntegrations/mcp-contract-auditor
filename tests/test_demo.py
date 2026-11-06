import os
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from mcp_auditor.demo import collect_fixture, run_demo, Clock, _capture
from mcp_auditor.strict_json import AuditError, artifact_json

def child(code):
    return subprocess.Popen(
        [sys.executable, '-I', '-B', '-c', code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={},
    )

class DemoTests(unittest.TestCase):

    def test_real_fixture_pages_and_no_execution(self):
        with patch.dict(os.environ, {'SYNTHETIC_SECRET_MARKER': 'must-not-inherit'}), patch('mcp_auditor.demo.subprocess.Popen', wraps=subprocess.Popen) as spawn:
            transcript = collect_fixture('baseline', Clock())
        self.assertEqual(len(transcript['exchanges']), 2)
        self.assertEqual(transcript['exchanges'][0]['response']['result']['nextCursor'], '')
        self.assertEqual(
            [e['request']['method'] for e in transcript['exchanges']],
            ['tools/list', 'tools/list'],
        )
        call = spawn.call_args
        self.assertEqual(call.kwargs['env'], {})
        self.assertNotIn('shell', call.kwargs)
        self.assertEqual(call.args[0][1:3], ['-I', '-B'])
        self.assertTrue(os.path.isabs(call.args[0][0]))
        with self.assertRaises(AuditError):
            collect_fixture('/tmp/not-allowed.py', Clock())

    def test_real_pipe_failures_reap_child(self):
        codes = {
            'line_limit': "import sys;sys.stdout.buffer.write(b'x'*(1024*1024+1));sys.stdout.flush()",
            'capture_error': "import sys;sys.stdout.write('{}');sys.stdout.flush()",
            'stderr_limit': "import sys;sys.stderr.buffer.write(b'x'*65537);sys.stderr.flush()",
            'capture_timeout': 'import time;time.sleep(10)',
            'capture_exit': 'import sys;sys.exit(7)',
        }
        for expected, code in codes.items():
            process = child(code)
            with self.subTest(expected=expected), self.assertRaises(AuditError) as caught:
                _capture(
                    process,
                    Clock(),
                    response_seconds=0.15 if expected == 'capture_timeout' else 3,
                    collection_seconds=5,
                )
            self.assertEqual(caught.exception.code, expected)
            self.assertIsNotNone(process.poll())

    def test_demo_real_audit_and_receipt(self):
        value = run_demo()
        self.assertEqual(len(value['steps']), 8)
        self.assertEqual(len(value['baseline_snapshot']['tools']), 5)
        self.assertEqual(len(value['candidate_snapshot']['tools']), 6)
        self.assertTrue(value['receipt_valid'])
        self.assertFalse(value['stale_receipt_valid'])
        self.assertEqual(
            {finding['rule_id'] for finding in value['report']['findings']},
            {
                'contract_breakage',
                'untrusted_text_change',
                'declared_capability_expansion',
                'opaque_schema',
                'inventory_change',
            },
        )
        self.assertEqual(
            artifact_json(value, limit=16 * 1024 * 1024),
            artifact_json(run_demo(), limit=16 * 1024 * 1024),
        )
