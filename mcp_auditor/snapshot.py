"""Immutable value snapshots; transcript digest is only a reference on re-import."""
from .strict_json import parse_json, digest, integer, AuditError, fail
from .protocol import fields, version, label, hash_value, validate_tool, validate_transcript, model_copy, CANONICAL
SNAPSHOT_FIELDS = {
    'format_version',
    'protocol_version',
    'origin_id',
    'scope_id',
    'canonical_version',
    'tools',
    'contract_digest',
    'transcript_digest',
}

def contract_body(snapshot):
    return {key: value for key, value in snapshot.items() if key not in ('contract_digest', 'transcript_digest')}

def import_transcript(data):
    transcript = parse_json(data, limit=4 * 1024 * 1024)
    tools = validate_transcript(transcript)
    snapshot = dict(
        format_version=1,
        protocol_version=transcript['protocol_version'],
        origin_id=transcript['origin_id'],
        scope_id=transcript['scope_id'],
        canonical_version=CANONICAL,
        tools=tools,
    )
    snapshot['contract_digest'] = digest(snapshot)
    snapshot['transcript_digest'] = digest(transcript)
    return validate_snapshot(snapshot)

def validate_snapshot(value):
    try:
        return _validate_snapshot(value)
    except AuditError as exc:
        if exc.code in {
            'unsupported_protocol',
            'input_limit',
            'output_limit',
            'node_limit',
            'depth_limit',
            'string_limit',
            'numeric_limit',
            'numeric_serialization_error',
        }:
            raise
        raise AuditError('integrity_error') from exc

def _validate_snapshot(value):
    snapshot = model_copy(value)
    fields(snapshot, SNAPSHOT_FIELDS)
    integer(snapshot['format_version'], 1, 1)
    version(snapshot['protocol_version'])
    label(snapshot['origin_id'])
    label(snapshot['scope_id'])
    if snapshot['canonical_version'] != CANONICAL:
        fail('integrity_error')
    hash_value(snapshot['contract_digest'])
    hash_value(snapshot['transcript_digest'])
    tools = snapshot['tools']
    if type(tools) is not list or len(tools) > 256:
        fail('invalid_tool')
    for tool in tools:
        validate_tool(tool)
    names = [tool['name'] for tool in tools]
    if names != sorted(set(names)):
        fail('integrity_error')
    if digest(contract_body(snapshot)) != snapshot['contract_digest']:
        fail('integrity_error')
    return snapshot
