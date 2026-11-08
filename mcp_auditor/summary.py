"""Short human-readable summaries. Machine consumers use --json."""
import unicodedata

ORDER = {'high': 0, 'unknown': 1, 'review': 2, 'info': 3}


def safe(value):
    """Escape control and format characters (ESC, CR, LF, bidi) so input-derived text cannot drive the terminal."""
    out = []
    for ch in str(value):
        if unicodedata.category(ch).startswith('C'):
            code = ord(ch)
            out.append(f'\\x{code:02x}' if code < 256 else f'\\u{code:04x}' if code < 0x10000 else f'\\U{code:08x}')
        else:
            out.append(ch)
    return ''.join(out)


def import_text(snapshot, out=None):
    names = [safe(t['name']) for t in snapshot['tools']]
    shown = ', '.join(names[:8]) + (f' and {len(names) - 8} more' if len(names) > 8 else '')
    return (f"Imported {len(names)} tools from origin {safe(snapshot['origin_id'])}, scope {safe(snapshot['scope_id'])}: {shown or 'none'}\n"
            f"Contract digest {snapshot['contract_digest']}\n"
            + (f'Wrote {safe(out)}\n' if out else 'Nothing written; pass --out FILE to save the snapshot.\n'))


def diff_text(report, top=10, hint=False):
    sev = report['summary']['severity']
    changed = report['baseline_digest'] != report['candidate_digest']
    needs = any(sev[k] for k in ('high', 'review', 'unknown'))
    if not changed:
        verdict = 'IDENTICAL: no contract change'
    elif needs:
        verdict = 'CHANGES NEED REVIEW'
    else:
        verdict = 'CHANGED, nothing needs review'
    lines = [f"{verdict}  ({sev['high']} high, {sev['review']} review, {sev['unknown']} unknown, {sev['info']} info)",
             f"Tools: baseline {report['tool_count']['baseline']}, candidate {report['tool_count']['candidate']}; "
             f"origin {safe(report['origin_id'])}, scope {safe(report['scope_id'])}"]
    for side in ('input', 'output'):
        s = report['summary'][side]
        lines.append(f"Schema {side}: compatible {s['compatible']}, breaking {s['breaking']}, unknown {s['unknown']}, not declared {s['not_declared']}")
    findings = sorted(report['findings'], key=lambda x: (ORDER.get(x['severity'], 9), str(x['tool']), x['pointer']))
    if findings:
        lines.append('Findings:')
        for x in findings[:top]:
            lines.append(f"  {safe(x['severity']):<8}{safe(x['tool'] or '(server)'):<18}{safe(x['reason_code']):<28}{safe(x['pointer'] or '/')}")
        if len(findings) > top:
            lines.append(f'  ... and {len(findings) - top} more (use --json)')
    lines.append(f"Audit digest {report['audit_digest']}")
    if needs and hint:
        lines.append('To acknowledge: confirm BASELINE CANDIDATE --expected-digest <audit digest> --reviewer NAME --out receipt.json')
    return '\n'.join(lines) + '\n'


def demo_text(demo):
    r = demo['receipt']
    return ('Demo: two real fixture processes, synthetic tool declarations, no network.\n'
            + diff_text(demo['report'])
            + f"Receipt by {safe(r['reviewer'])} for that exact digest: {'valid' if demo['receipt_valid'] else 'INVALID'}\n"
            + f"Same receipt after a later description change: {'still valid' if demo['stale_receipt_valid'] else 'rejected (stale), as intended'}\n"
            + 'Limits: declarations only; no tool is called and no server is declared safe. Add --json for the full artifact.\n')


def confirm_text(receipt, out=None):
    return (f"Acknowledged audit digest {receipt['audit_digest']}\n  by {safe(receipt['reviewer'])}; this is a local note, not authorization.\n"
            + (f'Wrote {safe(out)}\n' if out else 'Nothing written; pass --out FILE to save the receipt.\n'))


def receipt_text(matches, report=None):
    return ('Receipt MATCHES this exact comparison.\n' if matches else
            'Receipt does NOT match this comparison (changed declarations, other digest or invalid receipt).\n')
