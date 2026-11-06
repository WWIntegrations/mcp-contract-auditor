"""Real bounded stdio capture, restricted to the supplied synthetic fixture."""
import copy
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time
from .strict_json import artifact_json, parse_json, AuditError, fail, digest
from .protocol import MCP_PROFILE, validate_transcript, request_id, fields, string
from .snapshot import import_transcript, contract_body
from .audit import audit
from .receipt import confirm, check_receipt

class Clock:

    def monotonic(self):
        return time.monotonic()

    def utc_ms(self):
        return time.time_ns() // 1000000

class DemoClock(Clock):

    def utc_ms(self):
        return 1793980800000

def _request(identity, cursor=None, has_cursor=False):
    params = {
        '_meta': {
            'io.modelcontextprotocol/protocolVersion': MCP_PROFILE,
            'io.modelcontextprotocol/clientCapabilities': {},
            'clientInfo': {'name': 'mcp-contract-auditor', 'version': '1.0.0'},
        },
    }
    if has_cursor:
        params['cursor'] = cursor
    return dict(jsonrpc='2.0', id=identity, method='tools/list', params=params)

def _cleanup(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    else:
        process.wait()
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream is not None:
            stream.close()

def _capture(process, clock, *, response_seconds=3, collection_seconds=15, started=None):
    """Internal test seam accepts an owned process; public collection never accepts commands."""
    start = clock.monotonic() if started is None else started
    collection_deadline = start + collection_seconds
    deadline = min(collection_deadline, clock.monotonic() + response_seconds)
    current = _request(1)
    pending = bytearray(artifact_json(current, limit=1024 * 1024))
    buffer = bytearray()
    exchanges = []
    returned_cursors = set()
    totals = {'stdout': 0, 'stderr': 0}
    finished = False
    selector = selectors.DefaultSelector()
    for stream, name in ((process.stdout, 'stdout'), (process.stderr, 'stderr')):
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, name)
    os.set_blocking(process.stdin.fileno(), False)
    selector.register(process.stdin, selectors.EVENT_WRITE, 'stdin')
    try:
        while selector.get_map():
            remaining = deadline - clock.monotonic()
            if remaining <= 0:
                fail('capture_timeout')
            events = selector.select(remaining)
            if not events:
                fail('capture_timeout')
            for key, _ in events:
                if key.data == 'stdin':
                    try:
                        count = os.write(process.stdin.fileno(), pending)
                        del pending[:count]
                    except BrokenPipeError:
                        pending.clear()
                    if not pending:
                        selector.unregister(process.stdin)
                    continue
                chunk = os.read(key.fd, 16384)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                totals[key.data] += len(chunk)
                if totals[key.data] > (65536 if key.data == 'stderr' else 4 * 1024 * 1024):
                    fail('stderr_limit' if key.data == 'stderr' else 'stdout_limit')
                if key.data == 'stderr':
                    continue
                buffer.extend(chunk)
                while b'\n' in buffer:
                    position = buffer.index(10) + 1
                    if position > 1024 * 1024:
                        fail('line_limit')
                    line = bytes(buffer[:position])
                    del buffer[:position]
                    if finished or pending:
                        fail('unexpected_message')
                    response = parse_json(line, limit=1024 * 1024)
                    fields(response, {'jsonrpc', 'id', 'result'})
                    if response['jsonrpc'] != '2.0' or request_id(response['id']) != request_id(current['id']):
                        fail('response_mismatch')
                    result = response['result']
                    if type(result) is not dict:
                        fail('unsupported_envelope')
                    exchanges.append(dict(request=current, response=response))
                    if 'nextCursor' in result:
                        cursor = string(result['nextCursor'], maximum=1024)
                        if cursor in returned_cursors or len(exchanges) >= 8:
                            fail('pagination_error')
                        returned_cursors.add(cursor)
                        current = _request(len(exchanges) + 1, cursor, True)
                        pending.extend(artifact_json(current, limit=1024 * 1024))
                        selector.register(process.stdin, selectors.EVENT_WRITE, 'stdin')
                        deadline = min(collection_deadline, clock.monotonic() + response_seconds)
                    else:
                        finished = True
                        process.stdin.close()
                        deadline = clock.monotonic() + 1
                if len(buffer) >= 1024 * 1024:
                    fail('line_limit')
        try:
            process.wait(timeout=max(0, deadline - clock.monotonic()))
        except subprocess.TimeoutExpired:
            fail('capture_timeout')
        if process.returncode != 0:
            fail('capture_exit')
        if not finished or buffer:
            fail('capture_error')
        transcript = dict(
            format_version=1,
            protocol_version=MCP_PROFILE,
            origin_id='synthetic-fixture',
            scope_id='local-demo',
            exchanges=exchanges,
        )
        validate_transcript(transcript)
        # Check the complete stored transcript, including request envelopes.
        parse_json(artifact_json(transcript, limit=4 * 1024 * 1024), limit=4 * 1024 * 1024)
        return transcript
    finally:
        selector.close()
        _cleanup(process)

def collect_fixture(case, clock=None):
    if case not in ('baseline', 'candidate'):
        fail('invalid_fixture')
    clock = clock or Clock()
    script = Path(__file__).with_name('fixture_server.py').resolve()
    command = [str(Path(sys.executable).resolve()), '-I', '-B', str(script), case]
    started = clock.monotonic()
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={},
        cwd=script.parent,
        close_fds=True,
    )
    return _capture(process, clock, started=started)

def run_demo():
    clock = DemoClock()
    baseline = collect_fixture('baseline', clock)
    candidate = collect_fixture('candidate', clock)
    old = import_transcript(artifact_json(baseline, limit=4 * 1024 * 1024))
    new = import_transcript(artifact_json(candidate, limit=4 * 1024 * 1024))
    report = audit(old, new)
    receipt = confirm(old, new, report['audit_digest'], 'Synthetic local operator', clock)
    changed = copy.deepcopy(new)
    next((tool for tool in changed['tools'] if tool['name'] == 'draft_note'))['description'] += ' '
    changed['contract_digest'] = digest(contract_body(changed))
    steps = [
        dict(step_id='capture-baseline', label='Capture two baseline pages', tool=None, pointer=''),
        dict(
            step_id='capture-candidate',
            label='Capture two candidate pages',
            tool='archive_note',
            pointer='',
        ),
        dict(
            step_id='input-contract',
            label='A required input narrows the contract',
            tool='get_document',
            pointer='/inputSchema/required',
        ),
        dict(
            step_id='description',
            label='Changed instructions remain untrusted data',
            tool='draft_note',
            pointer='/description',
        ),
        dict(
            step_id='hints',
            label='A declared capability expands',
            tool='save_note',
            pointer='/annotations/readOnlyHint',
        ),
        dict(
            step_id='opaque-schema',
            label='An unchanged reference remains unsupported',
            tool='opaque_lookup',
            pointer='/inputSchema',
        ),
        dict(step_id='receipt', label='Acknowledge this exact audit digest', tool=None, pointer=''),
        dict(
            step_id='stale-receipt',
            label='A later description change invalidates the receipt',
            tool='draft_note',
            pointer='/description',
        ),
    ]
    result = dict(
        format_version=1,
        synthetic=True,
        baseline_transcript=baseline,
        candidate_transcript=candidate,
        baseline_snapshot=old,
        candidate_snapshot=new,
        report=report,
        receipt=receipt,
        receipt_valid=check_receipt(old, new, receipt),
        stale_receipt_valid=check_receipt(old, changed, receipt),
        steps=steps,
    )
    if not result['receipt_valid'] or result['stale_receipt_valid']:
        fail('demo_assertion')
    artifact_json(result, limit=16 * 1024 * 1024)
    return result
