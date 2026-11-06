import decimal
import hashlib
import unittest
from mcp_auditor.strict_json import parse_json, canonical, artifact_json, AuditError, Number

class StrictJSONTests(unittest.TestCase):

    def test_rejects_ambiguous_and_unbounded_input(self):
        for data in [
            b'{"a":1,"a":2}',
            b'NaN',
            b'Infinity',
            b'1e309',
            b'1e-309',
            b'1' * 65,
            b'"\\ud800"',
            b'\xef\xbb\xbf{}',
            b'\xff',
            b'{}{}',
            ('[' * 33 + '0' + ']' * 33).encode(),
            ('"' + 'x' * 16385 + '"').encode(),
        ]:
            with self.subTest(data=data[:30]), self.assertRaises(AuditError):
                parse_json(data)
        with self.assertRaises(AuditError):
            parse_json(b'[0,0,0]', max_nodes=3)
        with self.assertRaises(AuditError):
            parse_json(b'123', limit=2)

    def test_numeric_canonical_and_roundtrip_are_context_independent(self):
        texts = [
            '1e308',
            '1e-308',
            '123e308',
            '123456789012345678901234567890123456789',
            '0.123456789012345678901234567890123456789',
            '-0.0',
        ]
        expected = [decimal.Decimal(text) for text in texts]
        for precision in (6, 28):
            with decimal.localcontext() as context:
                context.prec = precision
                numbers = parse_json(('[' + ','.join(texts) + ']').encode())
                encoded = artifact_json(numbers)
                decoded = parse_json(encoded)
                self.assertEqual([number.value for number in decoded], expected)
                self.assertEqual(canonical(decoded), canonical(numbers))
                self.assertIn(b'1e308', encoded)
                self.assertEqual(len(canonical(numbers[0])), 309)
        self.assertEqual(canonical(parse_json(b'1')), canonical(parse_json(b'1.0')))
        self.assertEqual(canonical(parse_json(b'1.0')), canonical(parse_json(b'1e0')))
        self.assertNotEqual(canonical(True), canonical(parse_json(b'1')))
        self.assertEqual(canonical(parse_json(b'-0.0')), b'0')
        with self.assertRaises(AuditError):
            artifact_json(float('nan'))

    def test_exact_artifact_byte_limits_include_utf8_and_newline(self):
        for limit in (4 * 1024 * 1024, 8 * 1024 * 1024, 16 * 1024 * 1024):
            value = 'a' * (limit - 3)
            self.assertEqual(len(artifact_json(value, limit=limit)), limit)
            with self.assertRaises(AuditError) as error:
                artifact_json(value + 'a', limit=limit)
            self.assertEqual(error.exception.code, 'output_limit')
        self.assertEqual(len(artifact_json('é', limit=5)), 5)
        with self.assertRaises(AuditError):
            artifact_json('é', limit=4)

    def test_numeric_model_equality_ignores_lexeme(self):
        self.assertEqual(parse_json(b'1'), parse_json(b'1.0'))
        self.assertEqual(hash(parse_json(b'1')), hash(parse_json(b'1e0')))
        self.assertNotEqual(parse_json(b'1'), True)

    def test_artifact_escapes_bidi_without_changing_model_or_hash(self):
        original = {'description': 'Literal \u202e \u009b </script>'}
        encoded = artifact_json(original)
        self.assertNotIn('\u202e'.encode(), encoded)
        self.assertNotIn('\u009b'.encode(), encoded)
        self.assertIn(b'\\u202e', encoded)
        self.assertEqual(canonical(parse_json(encoded)), canonical(original))
        self.assertIn('\u202e'.encode(), canonical(original))

    def test_node_limit_is_enforced_before_materializing_json(self):
        from unittest.mock import patch
        import json
        data = b'[0,0,0]'
        with patch('mcp_auditor.strict_json.json.loads', wraps=json.loads) as parser:
            with self.assertRaises(AuditError) as error:
                parse_json(data, max_nodes=3)
            self.assertEqual(error.exception.code, 'node_limit')
            self.assertEqual(parser.call_count, 0)
