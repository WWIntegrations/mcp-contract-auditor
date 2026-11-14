"""Regressions for declarations shaped by a hostile server, within the documented bounds."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from mcp_auditor.audit import audit
from mcp_auditor.cli import main
from mcp_auditor.demo import _capture, Clock
from mcp_auditor.strict_json import artifact_json, parse_json, AuditError
from mcp_auditor.snapshot import import_transcript
from test_protocol import transcript, tool


class HostileServerTests(unittest.TestCase):

    def test_many_unknown_annotation_keys_audit_in_linear_time(self):
        # 20 tools x 1000 unknown keys is a 181 KB transcript, far inside the
        # 4 MiB / 50,000 node bounds. Deduplicating findings with a list scan
        # made this take about 8 s; it must stay well under that.
        tools = []
        for index in range(20):
            item = tool('t%d' % index)
            item['annotations'] = {'k%d' % key: 0 for key in range(1000)}
            tools.append(item)
        value = import_transcript(artifact_json(transcript(tools)))
        started = time.monotonic()
        report = audit(value, value)
        elapsed = time.monotonic() - started
        self.assertEqual(report['summary']['severity']['unknown'], 20000)
        self.assertLess(elapsed, 3.0)

    def test_drain_after_final_page_stays_inside_capture_window(self):
        # The final page arrives late, then the server keeps its pipes open.
        # The one-second exit grace must not extend the whole capture window.
        code = (
            "import json,sys,time\n"
            "line=sys.stdin.buffer.readline();request=json.loads(line);time.sleep(0.2)\n"
            "result={'resultType':'complete','tools':[],'ttlMs':0,'cacheScope':'private'}\n"
            "sys.stdout.buffer.write(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result}).encode()+b'\\n')\n"
            "sys.stdout.flush();time.sleep(10)\n"
        )
        process = subprocess.Popen(
            [sys.executable, '-I', '-B', '-c', code],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={},
        )
        started = time.monotonic()
        with self.assertRaises(AuditError) as caught:
            _capture(process, Clock(), response_seconds=3, collection_seconds=0.6, started=started)
        elapsed = time.monotonic() - started
        self.assertEqual(caught.exception.code, 'capture_timeout')
        self.assertIsNotNone(process.poll())
        # Window 0.6 s plus SIGTERM of a sleeping child; the old code took about 1.2 s.
        self.assertLess(elapsed, 0.95)

    def test_non_ascii_description_on_non_utf8_stdout_keeps_exit_contract(self):
        # A console or redirect in a legacy encoding (cp1252, ascii) used to raise
        # UnicodeEncodeError: a traceback with exit 1, which reads as "needs review".
        old = tool('lookup')
        new = tool('lookup')
        new['description'] = 'Zażółć → 漢字'
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for name, item in (('old.json', old), ('new.json', new)):
                path = Path(directory) / name
                path.write_bytes(artifact_json(transcript([item])))
                paths.append(str(path))
            for extra, expected in (([], 0), (['--json'], 0), (['--strict'], 1)):
                with self.subTest(extra=extra):
                    raw = io.BytesIO()
                    stdout = io.TextIOWrapper(raw, encoding='ascii', errors='strict')
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                        code = main(['compare', *paths, *extra])
                        stdout.flush()
                    self.assertEqual(code, expected)
                    if extra == ['--json']:
                        report = parse_json(raw.getvalue())
                        self.assertIn('Zażółć', report['changes'][0]['after']['value'])


if __name__ == '__main__':
    unittest.main()
