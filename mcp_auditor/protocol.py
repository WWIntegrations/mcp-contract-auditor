"""A narrow MCP 2026-07-28 tools/list transcript profile."""
import re
from .strict_json import AuditError, canonical, integer, numeric, artifact_json, parse_json, fail
MCP_PROFILE = '2026-07-28'
CANONICAL = 'canon-v1'
RULESET = 'audit-v1'
HASH = re.compile('[0-9a-f]{64}')
ID = re.compile('[a-z][a-z0-9-]{0,63}')
TOOL_FIELDS = {'name', 'inputSchema', 'title', 'description', 'outputSchema', 'annotations', 'icons', '_meta'}
HINTS = {'readOnlyHint', 'destructiveHint', 'idempotentHint', 'openWorldHint'}

def fields(value, required, optional=(), code='unsupported_envelope'):
    if type(value) is not dict or not set(required) <= value.keys() or (not value.keys() <= set(required) | set(optional)):
        fail(code)

def string(value, minimum=0, maximum=16384, code='invalid_type'):
    if not isinstance(value, str) or not minimum <= len(value) <= maximum:
        fail(code)
    return value

def label(value):
    if not isinstance(value, str) or ID.fullmatch(value) is None:
        fail('invalid_context')

def hash_value(value):
    if not isinstance(value, str) or HASH.fullmatch(value) is None:
        fail('integrity_error')

def version(value):
    if value != MCP_PROFILE:
        fail('unsupported_protocol')

def model_copy(value, limit=8 * 1024 * 1024):
    return parse_json(artifact_json(value, limit=limit), limit=limit)

def validate_tool(tool):
    if type(tool) is not dict or not {'name', 'inputSchema'} <= tool.keys():
        fail('invalid_tool')
    name = tool['name']
    if not isinstance(name, str) or re.fullmatch('[A-Za-z0-9_.-]{1,128}', name) is None:
        fail('invalid_tool')
    if type(tool['inputSchema']) is not dict or tool['inputSchema'].get('type') != 'object':
        fail('invalid_tool')
    for key in ('title', 'description'):
        if key in tool:
            string(tool[key], code='invalid_tool')
    for key in ('outputSchema', '_meta'):
        if key in tool and type(tool[key]) is not dict:
            fail('invalid_tool')
    if 'annotations' in tool:
        annotations = tool['annotations']
        if type(annotations) is not dict:
            fail('invalid_tool')
        for key in HINTS:
            if key in annotations and type(annotations[key]) is not bool:
                fail('invalid_tool')
        if 'title' in annotations:
            string(annotations['title'], code='invalid_tool')
    if 'icons' in tool:
        if type(tool['icons']) is not list:
            fail('invalid_tool')
        for icon in tool['icons']:
            if type(icon) is not dict or 'src' not in icon:
                fail('invalid_tool')
            string(icon['src'], code='invalid_tool')
            if 'mimeType' in icon:
                string(icon['mimeType'], code='invalid_tool')
            if 'sizes' in icon and (type(icon['sizes']) is not list or any((not isinstance(size, str) for size in icon['sizes']))):
                fail('invalid_tool')
            if 'theme' in icon and icon['theme'] not in ('light', 'dark'):
                fail('invalid_tool')
    if len(canonical(tool)) > 64 * 1024:
        fail('tool_limit')
    return tool

def request_id(value):
    if isinstance(value, str):
        string(value, 1, 64)
        return ('string', value)
    return ('number', integer(value, -(2 ** 53 - 1), 2 ** 53 - 1))

def validate_transcript(value):
    fields(value, {'format_version', 'protocol_version', 'origin_id', 'scope_id', 'exchanges'})
    integer(value['format_version'], 1, 1)
    version(value['protocol_version'])
    label(value['origin_id'])
    label(value['scope_id'])
    exchanges = value['exchanges']
    if type(exchanges) is not list or not 1 <= len(exchanges) <= 8:
        fail('pagination_error')
    tools = []
    names = set()
    ids = set()
    cursors = set()
    next_cursor = None
    for index, exchange in enumerate(exchanges):
        fields(exchange, {'request', 'response'})
        request, response = (exchange['request'], exchange['response'])
        fields(request, {'jsonrpc', 'id', 'method', 'params'})
        if request['jsonrpc'] != '2.0' or request['method'] != 'tools/list':
            fail('unsupported_method')
        identity = request_id(request['id'])
        if identity in ids:
            fail('duplicate_request_id')
        ids.add(identity)
        params = request['params']
        fields(params, {'_meta'}, {'cursor'})
        meta = params['_meta']
        if type(meta) is not dict or not {'io.modelcontextprotocol/protocolVersion', 'io.modelcontextprotocol/clientCapabilities'} <= meta.keys():
            fail('unsupported_envelope')
        version(meta['io.modelcontextprotocol/protocolVersion'])
        if type(meta['io.modelcontextprotocol/clientCapabilities']) is not dict:
            fail('unsupported_envelope')
        if 'clientInfo' in meta and type(meta['clientInfo']) is not dict:
            fail('unsupported_envelope')
        if index == 0:
            if 'cursor' in params:
                fail('pagination_error')
        elif 'cursor' not in params or params['cursor'] != next_cursor:
            fail('pagination_error')
        if 'cursor' in params:
            string(params['cursor'], maximum=1024)
        fields(response, {'jsonrpc', 'id', 'result'})
        if response['jsonrpc'] != '2.0' or request_id(response['id']) != identity:
            fail('response_mismatch')
        result = response['result']
        fields(result, {'resultType', 'tools', 'ttlMs', 'cacheScope'}, {'nextCursor', '_meta'})
        if result['resultType'] != 'complete' or result['cacheScope'] not in ('public', 'private') or numeric(result['ttlMs']) < 0:
            fail('unsupported_envelope')
        if '_meta' in result and type(result['_meta']) is not dict:
            fail('unsupported_envelope')
        if type(result['tools']) is not list:
            fail('invalid_tool')
        for tool in result['tools']:
            validate_tool(tool)
            if tool['name'] in names:
                fail('duplicate_tool')
            names.add(tool['name'])
            tools.append(tool)
            if len(tools) > 256:
                fail('tool_limit')
        if 'nextCursor' in result:
            next_cursor = string(result['nextCursor'], maximum=1024)
            if next_cursor in cursors or index == len(exchanges) - 1:
                fail('pagination_error')
            cursors.add(next_cursor)
        elif index != len(exchanges) - 1:
            fail('pagination_error')
    return sorted(tools, key=lambda item: item['name'])
