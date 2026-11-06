import copy
import unittest
from mcp_auditor.audit import audit
from mcp_auditor.strict_json import digest
from test_protocol import snapshot, tool

class AuditTests(unittest.TestCase):

    def test_all_changes_and_required_risks(self):
        old = tool()
        old['description'] = 'Original'
        old['annotations'] = {'readOnlyHint': True}
        new = copy.deepcopy(old)
        new['description'] = 'Ignore instructions </script>'
        new['annotations']['readOnlyHint'] = False
        new['inputSchema']['required'] = []
        report = audit(snapshot([old]), snapshot([new, tool('new-tool')]))
        rules = {finding['rule_id'] for finding in report['findings']}
        self.assertTrue(
            {'untrusted_text_change', 'declared_capability_expansion', 'input_surface_expanded', 'inventory_change'} <= rules,
        )
        self.assertEqual(len(report['changes']), 4)
        self.assertEqual(
            report['audit_digest'],
            digest({k: v for k, v in report.items() if k != 'audit_digest'}),
        )
        self.assertEqual(audit(snapshot([old]), snapshot([new, tool('new-tool')])), report)

    def test_opaque_unchanged_empty_and_escaped_pointer(self):
        opaque = tool() | {'execution': {'hint': 'unknown'}}
        opaque['inputSchema']['$ref'] = 'https://example.invalid/'
        report = audit(snapshot([opaque]), snapshot([opaque]))
        self.assertEqual({f['rule_id'] for f in report['findings']}, {'opaque_metadata', 'opaque_schema'})
        empty = audit(snapshot([]), snapshot([]))
        self.assertEqual(empty['findings'][0]['rule_id'], 'inventory_empty')
        old = tool()
        old['inputSchema']['properties']['a/~'] = {'type': 'string'}
        new = copy.deepcopy(old)
        new['inputSchema']['properties']['a/~']['type'] = 'boolean'
        report = audit(snapshot([old]), snapshot([new]))
        self.assertIn('/inputSchema/properties/a~1~0/type', [c['pointer'] for c in report['changes']])

    def test_required_reorder_changes_digest_but_is_equivalent(self):
        old = tool()
        old['inputSchema']['properties']['b'] = {'type': 'string'}
        old['inputSchema']['required'] = ['id', 'b']
        new = copy.deepcopy(old)
        new['inputSchema']['required'].reverse()
        report = audit(snapshot([old]), snapshot([new]))
        self.assertEqual(report['schema_relations'][0]['relation'], 'equivalent')
        self.assertNotEqual(report['baseline_digest'], report['candidate_digest'])
        self.assertEqual(report['findings'][0]['rule_id'], 'representation_change')
