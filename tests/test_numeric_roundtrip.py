import decimal
import unittest
from mcp_auditor.strict_json import artifact_json, parse_json, canonical
from mcp_auditor.snapshot import import_transcript, validate_snapshot
from mcp_auditor.audit import audit
from mcp_auditor.receipt import confirm, check_receipt
from test_protocol import transcript

class Clock:

    def utc_ms(self):
        return 1793980800000

class NumericRoundtripTests(unittest.TestCase):

    def test_complete_artifact_pipeline_preserves_large_and_precise_numbers(self):
        values = [
            '1e308',
            '1e-308',
            '123e308',
            '123456789012345678901234567890123456789',
            '0.123456789012345678901234567890123456789',
        ]
        for precision in (6, 28):
            for tokens in [[value] for value in values] + [values]:
                with self.subTest(precision=precision, tokens=tokens), decimal.localcontext() as context:
                    context.prec = precision
                    data = transcript()
                    data['exchanges'][0]['response']['result']['tools'][0]['inputSchema']['properties']['id'] = {'type': 'number', 'enum': parse_json(('[' + ','.join(tokens) + ']').encode())}
                    first = import_transcript(artifact_json(data, limit=4 * 1024 * 1024))
                    second = validate_snapshot(parse_json(artifact_json(first)))
                    self.assertEqual(canonical(first), canonical(second))
                    report = audit(first, second)
                    self.assertEqual(report['schema_relations'][0]['relation'], 'equivalent')
                    receipt = confirm(first, second, report['audit_digest'], 'Operator', Clock())
                    loaded = parse_json(artifact_json(receipt))
                    self.assertTrue(check_receipt(first, second, loaded))
                    self.assertEqual(canonical(loaded), canonical(receipt))
