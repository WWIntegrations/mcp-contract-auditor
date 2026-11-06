import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mcp_auditor.cli import main
from mcp_auditor.strict_json import artifact_json, parse_json, AuditError, read_file
from test_protocol import transcript, tool

class CLITests(unittest.TestCase):

    def call(self, args):
        output, error = (io.StringIO(), io.StringIO())
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = main(args)
        return (code, output.getvalue(), error.getvalue())

    def test_complete_flow_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'input.json'
            source.write_bytes(artifact_json(transcript()))
            code, output, error = self.call(['import', str(source)])
            self.assertEqual((code, error), (0, ''))
            baseline = root / 'baseline.json'
            baseline.write_text(output)
            candidate = root / 'candidate.json'
            candidate.write_text(output)
            code, output, error = self.call(['diff', str(baseline), str(candidate)])
            self.assertEqual(code, 0)
            report = parse_json(output.encode())
            code, output, error = self.call(
                [
                    'confirm',
                    str(baseline),
                    str(candidate),
                    '--expected-digest',
                    report['audit_digest'],
                    '--reviewer',
                    'Operator',
                ],
            )
            self.assertEqual(code, 0)
            receipt = root / 'receipt.json'
            receipt.write_text(output)
            self.assertEqual(self.call(['check-receipt', str(baseline), str(candidate), str(receipt)])[0], 0)
            changed = tool()
            changed['description'] = 'Changed'
            source.write_bytes(artifact_json(transcript([changed])))
            candidate.write_text(self.call(['import', str(source)])[1])
            self.assertEqual(self.call(['diff', str(baseline), str(candidate)])[0], 1)
            self.assertEqual(self.call(['check-receipt', str(baseline), str(candidate), str(receipt)])[0], 1)
            code, output, error = self.call(
                [
                    'confirm',
                    str(baseline),
                    str(candidate),
                    '--expected-digest',
                    report['audit_digest'],
                    '--reviewer',
                    'Operator',
                ],
            )
            self.assertEqual((code, output, error.strip()), (2, '', 'stale_confirmation'))

    def test_reject_files_and_errors_do_not_emit_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / 'data.json'
            file.write_bytes(b'{}')
            link = root / 'link.json'
            link.symlink_to(file)
            fifo = root / 'pipe'
            os.mkfifo(fifo)
            for path in (link, fifo, root):
                with self.assertRaises(AuditError):
                    read_file(path, limit=1024)
            self.assertEqual(self.call(['import', str(file)])[0], 2)
            file.write_bytes(artifact_json(transcript()))
            with patch('mcp_auditor.cli.emit', side_effect=AuditError('output_limit')):
                code, output, error = self.call(['import', str(file)])
            self.assertEqual((code, output, error.strip()), (2, '', 'output_limit'))
