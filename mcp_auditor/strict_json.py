"""Bounded JSON with exact numbers and separate hash/artifact encodings."""
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from decimal import Decimal

class AuditError(ValueError):

    def __init__(self, code):
        self.code = code
        super().__init__(code)

@dataclass(frozen=True, eq=False)
class Number:
    value: Decimal
    lexeme: str | None = None

    def __eq__(self, other):
        return isinstance(other, Number) and self.value == other.value

    def __hash__(self):
        return hash(self.value)

def fail(code='invalid_json'):
    raise AuditError(code)

def number(token):
    if len(token) > 64:
        fail('numeric_limit')
    match = re.search('[eE]([+-]?[0-9]+)$', token)
    if match and abs(int(match.group(1))) > 308:
        fail('numeric_limit')
    value = Decimal(token)
    if not value.is_finite():
        fail('invalid_json')
    return Number(value, token)

def numeric(value):
    if isinstance(value, Number):
        return value.value
    if type(value) is int:
        return Decimal(value)
    fail('invalid_type')

def integer(value, low=None, high=None):
    exact = numeric(value)
    result = int(exact)
    if exact != Decimal(result) or (low is not None and result < low) or (high is not None and result > high):
        fail('invalid_integer')
    return result

def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail('duplicate_key')
        result[key] = value
    return result

def parse_json(data, *, limit=8 * 1024 * 1024, max_nodes=50000):
    if not isinstance(data, bytes) or len(data) > limit:
        fail('input_limit')
    try:
        text = data.decode('utf-8')
    except UnicodeError:
        fail('invalid_utf8')
    if text.startswith('\ufeff'):
        fail('invalid_json')
    # Preflight before calling a recursive parser, respecting escaped quotes.
    depth, quoted, escaped = (0, False, False)
    nodes = 0
    primitive = False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
            primitive = False
            nodes += 1
        elif character in '[{':
            depth += 1
            primitive = False
            nodes += 1
            if depth > 32:
                fail('depth_limit')
        elif character in ']}':
            depth -= 1
            primitive = False
        elif character in ',: \t\r\n':
            primitive = False
        elif not primitive:
            primitive = True
            nodes += 1
        if nodes > max_nodes:
            fail('node_limit')
    try:
        result = json.loads(
            text,
            parse_int=number,
            parse_float=number,
            parse_constant=lambda token: fail(),
            object_pairs_hook=_pairs,
        )
    except (ValueError, RecursionError) as exc:
        if isinstance(exc, AuditError):
            raise
        raise AuditError('invalid_json') from exc
    stack = [result]
    nodes = 0
    while stack:
        item = stack.pop()
        nodes += 1
        if nodes > max_nodes:
            fail('node_limit')
        if isinstance(item, str):
            if len(item) > 16384:
                fail('string_limit')
            if any((55296 <= ord(char) <= 57343 for char in item)):
                fail('invalid_unicode')
        elif isinstance(item, dict):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return result

def decimal_plain(value):
    sign, digits, exponent = value.as_tuple()
    text = ''.join((str(digit) for digit in digits))
    if not any(digits):
        return '0'
    point = len(text) + exponent
    if point <= 0:
        text = '0.' + '0' * -point + text
    elif point < len(text):
        text = text[:point] + '.' + text[point:]
    else:
        text += '0' * (point - len(text))
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return ('-' if sign else '') + text

def decimal_artifact(item):
    value = item.value
    sign, digits, exponent = value.as_tuple()
    text = ''.join((str(digit) for digit in digits))
    if not any(digits):
        return '0'
    tail = text[1:].rstrip('0')
    coefficient = ('-' if sign else '') + text[0] + ('.' + tail if tail else '')
    power = exponent + len(text) - 1
    candidate = coefficient + ('e' + str(power) if power else '')
    for token in (candidate, item.lexeme):
        if token is None:
            continue
        try:
            parsed = number(token)
        except AuditError:
            continue
        if parsed.value == value:
            return token
    fail('numeric_serialization_error')

def _encode(value, artifact):
    if value is None:
        return 'null'
    if type(value) is bool:
        return 'true' if value else 'false'
    if isinstance(value, str):
        try:
            value.encode('utf-8')
        except UnicodeError:
            fail('invalid_unicode')
        encoded = json.dumps(value, ensure_ascii=False)
        if artifact:
            controls = list(range(127, 160)) + [0x061C, 0x200E, 0x200F]
            controls += list(range(0x202A, 0x202F)) + list(range(0x2066, 0x206A))
            encoded = encoded.translate({code: '\\u%04x' % code for code in controls})
        return encoded
    if isinstance(value, Number):
        return decimal_artifact(value) if artifact else decimal_plain(value.value)
    if type(value) is int:
        token = str(value)
        if artifact and len(token) > 64:
            fail('numeric_serialization_error')
        return token
    if isinstance(value, list):
        return '[' + ','.join((_encode(item, artifact) for item in value)) + ']'
    if isinstance(value, dict) and all((isinstance(key, str) for key in value)):
        return '{' + ','.join((_encode(key, artifact) + ':' + _encode(value[key], artifact) for key in sorted(value))) + '}'
    fail('numeric_serialization_error' if isinstance(value, (float, Decimal)) else 'invalid_type')

def canonical(value):
    return _encode(value, False).encode('utf-8')

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def artifact_json(value, *, limit=8 * 1024 * 1024):
    data = (_encode(value, True) + '\n').encode('utf-8')
    if len(data) > limit:
        fail('output_limit')
    return data

def read_file(path, *, limit):
    """Open once, refuse symlinks/devices/FIFOs, then bound the actual read."""
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0)
    try:
        if stat.S_ISLNK(os.lstat(path).st_mode):
            fail('invalid_file')
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, 'rb') as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                fail('invalid_file')
            if metadata.st_size > limit:
                fail('input_limit')
            data = stream.read(limit + 1)
            if len(data) > limit:
                fail('input_limit')
            return data
    except OSError as exc:
        raise AuditError('invalid_file') from exc
