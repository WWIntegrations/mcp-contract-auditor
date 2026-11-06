import copy
import unittest
from mcp_auditor.audit import audit
from mcp_auditor.receipt import confirm, check_receipt
from mcp_auditor.snapshot import contract_body
from mcp_auditor.strict_json import digest, AuditError
from test_protocol import snapshot, tool
from test_numeric_roundtrip import Clock

class ReceiptTests(unittest.TestCase):

    def test_bindings_and_stale_confirmation(self):
        old = snapshot()
        item = tool()
        item['description'] = 'New'
        new = snapshot([item])
        report = audit(old, new)
        receipt = confirm(old, new, report['audit_digest'], 'Operator', Clock())
        self.assertTrue(check_receipt(old, new, receipt))
        self.assertTrue(report['summary']['severity']['high'])
        changed = copy.deepcopy(new)
        changed['tools'][0]['description'] = 'New '
        changed['contract_digest'] = digest(contract_body(changed))
        self.assertFalse(check_receipt(old, changed, receipt))
        with self.assertRaises(AuditError) as caught:
            confirm(old, changed, report['audit_digest'], 'Operator', Clock())
        self.assertEqual(caught.exception.code, 'stale_confirmation')
        for field in ('scope_id', 'origin_id'):
            a, b = (copy.deepcopy(old), copy.deepcopy(new))
            a[field] = b[field] = 'different'
            a['contract_digest'] = digest(contract_body(a))
            b['contract_digest'] = digest(contract_body(b))
            self.assertFalse(check_receipt(a, b, receipt))
        wrong = receipt | {'ruleset_version': 'audit-v2'}
        wrong['receipt_digest'] = digest({k: v for k, v in wrong.items() if k != 'receipt_digest'})
        self.assertFalse(check_receipt(old, new, wrong))
        with self.assertRaises(AuditError):
            audit(old, new | {'scope_id': 'different'})
