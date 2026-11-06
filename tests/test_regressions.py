import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mcp_auditor.strict_json import parse_json, artifact_json, read_file, AuditError
from mcp_auditor.protocol import validate_transcript
from mcp_auditor.snapshot import import_transcript
from mcp_auditor.schema_diff import relation
from mcp_auditor.demo import run_demo
from test_protocol import transcript, tool, snapshot
from mcp_auditor.audit import audit

class RegressionTests(unittest.TestCase):

    def test_golden_demo_audit(self):
        value = run_demo()
        self.assertEqual(
            value['report']['audit_digest'],
            '0a5ef0817c5a914143e87183aef269219bf844e66bf670fef0c4a6873b488125',
        )
        self.assertEqual(
            value['report']['summary']['severity'],
            {'info': 0, 'review': 1, 'high': 3, 'unknown': 1},
        )
        self.assertEqual(value['report']['tool_count'], {'baseline': 5, 'candidate': 6})

    def test_regular_file_bound_and_snapshot_node_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            exact = Path(directory) / 'exact.json'
            larger = Path(directory) / 'larger.json'
            with exact.open('xb') as stream:
                stream.write(b' ' * (8 * 1024 * 1024))
            with larger.open('xb') as stream:
                stream.write(b' ' * (8 * 1024 * 1024 + 1))
            self.assertEqual(len(read_file(exact, limit=8 * 1024 * 1024)), 8 * 1024 * 1024)
            with self.assertRaises(AuditError):
                read_file(larger, limit=8 * 1024 * 1024)
        value = transcript()
        value['exchanges'][0]['request']['params']['_meta']['extra'] = [0] * 50000
        with self.assertRaises(AuditError) as error:
            import_transcript(artifact_json(value))
        self.assertEqual(error.exception.code, 'node_limit')

    def test_opaque_schema_never_opens_files_compiles_patterns_or_network(self):
        left = {'type': 'object', '$ref': 'file:///not-opened', 'pattern': '(a+)+$'}
        right = left | {'$ref': 'https://example.invalid/not-fetched'}
        with patch('builtins.open', side_effect=AssertionError('file access')), patch('socket.socket', side_effect=AssertionError('network')), patch('re.compile', side_effect=AssertionError('pattern compiled')):
            self.assertEqual(relation(left, right), 'unknown')

    def test_integral_numeric_rpc_ids_and_bool_separation(self):
        data = transcript()
        data['exchanges'][0]['request']['id'] = parse_json(b'1.0')
        data['exchanges'][0]['response']['id'] = parse_json(b'1e0')
        validate_transcript(data)
        data['exchanges'][0]['response']['id'] = True
        with self.assertRaises(AuditError):
            validate_transcript(data)

    def test_missing_hint_versus_explicit_and_metadata_property_names(self):
        old = tool()
        new = copy.deepcopy(old)
        new['annotations'] = {'readOnlyHint': False}
        report = audit(snapshot([old]), snapshot([new]))
        self.assertIn('hint_change', [item['rule_id'] for item in report['findings']])
        old = tool()
        old['inputSchema']['properties']['description'] = {'type': 'string'}
        new = copy.deepcopy(old)
        new['inputSchema']['properties']['description']['type'] = 'boolean'
        report = audit(snapshot([old]), snapshot([new]))
        self.assertNotIn('untrusted_text_change', [item['rule_id'] for item in report['findings']])
