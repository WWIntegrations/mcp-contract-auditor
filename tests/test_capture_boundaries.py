import subprocess
import sys
import unittest
from mcp_auditor.demo import _capture, Clock
from mcp_auditor.strict_json import AuditError
SERVER = "import json,sys,time\nMODE = %r\nfor index,line in enumerate(sys.stdin.buffer):\n    request=json.loads(line)\n    result={'resultType':'complete','tools':[],'ttlMs':0,'cacheScope':'private'}\n    if MODE=='nine-pages':result['nextCursor']=str(index)\n    response={'jsonrpc':'2.0','id':request['id'],'result':result}\n    output=json.dumps(response).encode()+b'\\n'\n    sys.stdout.buffer.write(output);sys.stdout.buffer.flush()\n    if MODE=='extra':\n        sys.stdout.buffer.write(output);sys.stdout.buffer.flush();break\n    if MODE=='nonzero':sys.exit(9)\n    if MODE=='missing-lf':\n        sys.stdout.buffer.write(b'{}');sys.stdout.buffer.flush();break\n    if MODE=='hold-after-final':time.sleep(10)\n"

class NoUTC(Clock):

    def utc_ms(self):
        raise AssertionError('UTC must not drive capture')

class CaptureBoundaryTests(unittest.TestCase):

    def test_actual_extra_page_message_exit_and_cleanup(self):
        for mode, expected in [
            ('nine-pages', 'pagination_error'),
            ('extra', 'unexpected_message'),
            ('nonzero', 'capture_exit'),
            ('missing-lf', 'capture_error'),
            ('hold-after-final', 'capture_timeout'),
        ]:
            process = subprocess.Popen(
                [sys.executable, '-I', '-B', '-c', SERVER % mode],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={},
            )
            with self.subTest(mode=mode), self.assertRaises(AuditError) as error:
                _capture(process, NoUTC())
            self.assertEqual(error.exception.code, expected)
            self.assertIsNotNone(process.poll())

    def test_capture_does_not_consult_utc(self):
        process = subprocess.Popen(
            [sys.executable, '-I', '-B', '-c', SERVER % 'normal'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={},
        )
        value = _capture(process, NoUTC())
        self.assertEqual(len(value['exchanges']), 1)
        self.assertEqual(value['exchanges'][0]['response']['result']['tools'], [])
        self.assertEqual(process.returncode, 0)
