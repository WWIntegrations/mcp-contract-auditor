import copy
import unittest
from mcp_auditor.strict_json import artifact_json, parse_json, AuditError
from mcp_auditor.protocol import MCP_PROFILE
from mcp_auditor.snapshot import import_transcript, validate_snapshot

def tool(name='lookup'):
    return dict(
        name=name,
        inputSchema=dict(
            type='object',
            properties={'id': {'type': 'string'}},
            required=['id'],
            additionalProperties=False,
        ),
    )

def transcript(tools=None):
    return dict(
        format_version=1,
        protocol_version='2026-07-28',
        origin_id='synthetic',
        scope_id='local',
        exchanges=[
            dict(
                request=dict(
                    jsonrpc='2.0',
                    id=1,
                    method='tools/list',
                    params={
                        '_meta': {
                            'io.modelcontextprotocol/protocolVersion': '2026-07-28',
                            'io.modelcontextprotocol/clientCapabilities': {},
                        },
                    },
                ),
                response=dict(
                    jsonrpc='2.0',
                    id=1,
                    result=dict(
                        resultType='complete',
                        ttlMs=0,
                        cacheScope='private',
                        tools=tools if tools is not None else [tool()],
                    ),
                ),
            ),
        ],
    )

def snapshot(tools=None):
    return import_transcript(artifact_json(transcript(tools)))

class ProtocolTests(unittest.TestCase):

    def test_empty_cursor_is_not_end_and_order_does_not_change_contract(self):
        data = transcript([tool('b')])
        data['exchanges'][0]['response']['result']['nextCursor'] = ''
        page = copy.deepcopy(data['exchanges'][0])
        page['request']['id'] = 2
        page['response']['id'] = 2
        page['request']['params']['cursor'] = ''
        page['response']['result'].pop('nextCursor')
        page['response']['result']['tools'] = [tool('a')]
        data['exchanges'].append(page)
        first = import_transcript(artifact_json(data))
        second = snapshot([tool('a'), tool('b')])
        self.assertEqual(first['contract_digest'], second['contract_digest'])
        self.assertNotEqual(first['transcript_digest'], second['transcript_digest'])
        self.assertEqual([item['name'] for item in first['tools']], ['a', 'b'])
        self.assertEqual(
            validate_snapshot(parse_json(artifact_json(first)))['contract_digest'],
            first['contract_digest'],
        )

    def test_protocol_rejects_incomplete_legacy_mismatched_ids_and_errors(self):
        for case in ('version', 'meta', 'legacy', 'id', 'error', 'cursor', 'duplicate', 'extra', 'method', 'null-cursor'):
            data = transcript()
            exchange = data['exchanges'][0]
            if case == 'version':
                data['protocol_version'] = '2025-11-25'
            if case == 'meta':
                exchange['request']['params'] = {}
            if case == 'legacy':
                exchange['response']['result'].pop('resultType')
            if case == 'id':
                exchange['response']['id'] = '1'
            if case == 'error':
                exchange['response']['error'] = {'message': 'DO NOT PRINT', 'code': -1}
            if case == 'cursor':
                exchange['response']['result']['nextCursor'] = ''
            if case == 'duplicate':
                exchange['response']['result']['tools'] *= 2
            if case == 'extra':
                exchange['response']['result']['extra'] = True
            if case == 'method':
                exchange['request']['method'] = 'tools/call'
            if case == 'null-cursor':
                exchange['response']['result']['nextCursor'] = None
            with self.subTest(case=case), self.assertRaises(AuditError):
                import_transcript(artifact_json(data))

    def test_shapes_unknown_fields_preserved_and_digest_rechecked(self):
        item = tool()
        item['execution'] = {'hint': 'untrusted'}
        first = snapshot([item])
        self.assertEqual(first['tools'][0]['execution'], item['execution'])
        broken = copy.deepcopy(first)
        broken['tools'][0]['inputSchema']['required'] = []
        with self.assertRaises(AuditError) as error:
            validate_snapshot(broken)
        self.assertEqual(error.exception.code, 'integrity_error')
        for change in (
            {'inputSchema': None},
            {'inputSchema': {'type': ['object']}},
            {'annotations': {'readOnlyHint': 1}},
            {'icons': [{'src': 1}]},
        ):
            with self.assertRaises(AuditError):
                snapshot([tool() | change])
        self.assertEqual(snapshot([])['tools'], [])

    def test_invalid_snapshot_tool_is_integrity_error(self):
        value = snapshot()
        value['tools'][0]['annotations'] = {'readOnlyHint': 'not boolean'}
        with self.assertRaises(AuditError) as caught:
            validate_snapshot(value)
        self.assertEqual(caught.exception.code, 'integrity_error')
