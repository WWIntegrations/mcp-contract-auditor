import copy
import unittest
from mcp_auditor.schema_diff import relation, compatibility, analyze

def schema():
    return {
        'type': 'object',
        'properties': {'a': {'type': 'integer'}, 'b': {'type': 'string'}},
        'required': ['a'],
        'additionalProperties': False,
    }

class SchemaDiffTests(unittest.TestCase):

    def test_single_constraint_rules_both_directions(self):
        changes = [
            ('required', ['a', 'b'], 'narrows'),
            ('required', [], 'widens'),
            ('additionalProperties', True, 'widens'),
        ]
        for key, value, expected in changes:
            old = schema()
            new = copy.deepcopy(old)
            new[key] = value
            self.assertEqual(relation(old, new), expected)
            self.assertEqual(relation(new, old), 'narrows' if expected == 'widens' else 'widens')
        old = schema()
        new = copy.deepcopy(old)
        new['properties']['a']['type'] = 'number'
        self.assertEqual(relation(old, new), 'widens')
        self.assertEqual(compatibility('widens', 'input'), 'compatible')
        self.assertEqual(compatibility('widens', 'output'), 'breaking')
        new = copy.deepcopy(old)
        new['properties']['b']['enum'] = ['x', 'y']
        self.assertEqual(relation(old, new), 'narrows')
        newer = copy.deepcopy(new)
        newer['properties']['b']['enum'] = ['x']
        self.assertEqual(relation(new, newer), 'narrows')
        newer['properties']['b']['enum'] = ['z']
        self.assertEqual(relation(new, newer), 'unknown')

    def test_finite_domains_and_representation_equivalence(self):
        for kind, values in [('boolean', [True, False]), ('null', [None])]:
            old = {'type': 'object', 'properties': {'a': {'type': kind}}}
            new = copy.deepcopy(old)
            new['properties']['a']['enum'] = values
            self.assertEqual(relation(old, new), 'equivalent')
        bad = {'type': 'object', 'properties': {'a': {'type': 'integer', 'enum': [True]}}}
        self.assertIsNone(analyze(bad))
        old = schema()
        old['required'] = ['a', 'b']
        new = copy.deepcopy(old)
        new['required'] = ['b', 'a']
        new['title'] = 'Label'
        self.assertEqual(relation(old, new), 'equivalent')

    def test_unsupported_and_multi_change_do_not_infer_compatibility(self):
        old = schema()
        for new in [
            old | {'$ref': 'file:///not-read'},
            old | {'pattern': '(a+)+$'},
            old | {'type': ['object']},
            old | {'required': ['a', 'b'], 'additionalProperties': True},
            old | {'properties': old['properties'] | {'c': {'type': 'string'}}},
        ]:
            self.assertEqual(relation(old, new), 'unknown')
        self.assertEqual(
            relation(old | {'$ref': 'https://example.invalid/'}, old | {'$ref': 'https://example.invalid/'}),
            'unknown',
        )
