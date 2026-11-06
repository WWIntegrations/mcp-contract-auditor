"""Single-constraint set relations for the explicit flat-object-v1 profile."""
from .strict_json import AuditError, canonical, numeric, integer
COMMENTS = {'title', 'description', '$comment', 'default'}
DIALECT = 'https://json-schema.org/draft/2020-12/schema'
SCALARS = {'string', 'boolean', 'null', 'integer', 'number'}

def _matches(value, kind):
    if kind == 'string':
        return isinstance(value, str)
    if kind == 'boolean':
        return type(value) is bool
    if kind == 'null':
        return value is None
    try:
        integer(value) if kind == 'integer' else numeric(value)
        return True
    except AuditError:
        return False

def _comments_valid(value):
    return all((key not in value or isinstance(value[key], str) for key in ('title', 'description', '$comment')))

def analyze(schema):
    """Return a semantic projection, or None without interpreting opaque keywords."""
    if type(schema) is not dict or schema.get('type') != 'object':
        return None
    allowed = {'type', 'properties', 'required', 'additionalProperties', '$schema'} | COMMENTS
    if not schema.keys() <= allowed or schema.get('$schema', DIALECT) != DIALECT or (not _comments_valid(schema)):
        return None
    properties = schema.get('properties', {})
    required = schema.get('required', [])
    additional = schema.get('additionalProperties', True)
    if type(properties) is not dict or len(properties) > 64 or type(required) is not list or (type(additional) is not bool):
        return None
    if any((not isinstance(name, str) for name in required)) or len(required) != len(set(required)) or (not set(required) <= properties.keys()):
        return None
    projection = {}
    for name, scalar in properties.items():
        if type(scalar) is not dict or not scalar.keys() <= {'type', 'enum'} | COMMENTS or (not _comments_valid(scalar)):
            return None
        kind = scalar.get('type')
        if not isinstance(kind, str) or kind not in SCALARS:
            return None
        domain = None
        if 'enum' in scalar:
            values = scalar['enum']
            if type(values) is not list or not 1 <= len(values) <= 64 or (not all((_matches(value, kind) for value in values))):
                return None
            domain = frozenset((canonical(value) for value in values))
            if len(domain) != len(values):
                return None
        elif kind == 'boolean':
            domain = frozenset((b'true', b'false'))
        elif kind == 'null':
            domain = frozenset((b'null',))
        projection[name] = {'type': kind, 'enum': domain}
    return {'properties': projection, 'required': frozenset(required), 'additionalProperties': additional}

def _set_relation(old, new):
    if old == new:
        return 'equivalent'
    if old is None:
        return 'narrows'
    if new is None:
        return 'widens'
    if new < old:
        return 'narrows'
    if old < new:
        return 'widens'
    return 'unknown'

def relation(old, new):
    left, right = (analyze(old), analyze(new))
    if left is None or right is None:
        return 'unknown'
    if left == right:
        return 'equivalent'
    if left['properties'].keys() != right['properties'].keys():
        return 'unknown'
    differences = []
    for key in ('required', 'additionalProperties'):
        if left[key] != right[key]:
            differences.append((key, left[key], right[key], None, None))
    for name in left['properties']:
        a, b = (left['properties'][name], right['properties'][name])
        for key in ('type', 'enum'):
            if a[key] != b[key]:
                differences.append((key, a[key], b[key], a, b))
    if len(differences) != 1:
        return 'unknown'
    key, a, b, old_scalar, new_scalar = differences[0]
    if key == 'required':
        return _set_relation(b, a)
    if key == 'additionalProperties':
        return 'widens' if b else 'narrows'
    if key == 'enum':
        return _set_relation(a, b)
    if key == 'type' and {a, b} == {'integer', 'number'} and (old_scalar['enum'] is None) and (new_scalar['enum'] is None):
        return 'widens' if b == 'number' else 'narrows'
    return 'unknown'

def compatibility(result, side):
    if result is None:
        return 'not_declared'
    if result == 'unknown':
        return 'unknown'
    if result == 'equivalent' or result == ('widens' if side == 'input' else 'narrows'):
        return 'compatible'
    return 'breaking'
