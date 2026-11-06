"""Local acknowledgement of a recomputed comparison, never authorization."""
from .audit import audit
from .protocol import fields, string, label, hash_value, model_copy, RULESET
from .strict_json import integer, digest, fail, AuditError
RECEIPT_FIELDS = {
    'format_version',
    'decision',
    'reviewer',
    'reviewed_at',
    'origin_id',
    'scope_id',
    'baseline_digest',
    'candidate_digest',
    'ruleset_version',
    'audit_digest',
    'receipt_digest',
}

def confirm(old, new, expected_digest, reviewer, utc_clock):
    hash_value(expected_digest)
    string(reviewer, 1, 80)
    report = audit(old, new)
    if report['audit_digest'] != expected_digest:
        fail('stale_confirmation')
    receipt = dict(
        format_version=1,
        decision='acknowledged',
        reviewer=reviewer,
        reviewed_at=integer(utc_clock.utc_ms(), 0, 4102444800000),
        origin_id=report['origin_id'],
        scope_id=report['scope_id'],
        baseline_digest=report['baseline_digest'],
        candidate_digest=report['candidate_digest'],
        ruleset_version=RULESET,
        audit_digest=report['audit_digest'],
    )
    receipt['receipt_digest'] = digest(receipt)
    return model_copy(receipt)

def check_receipt(old, new, receipt):
    report = audit(old, new)
    receipt = model_copy(receipt)
    fields(receipt, RECEIPT_FIELDS)
    integer(receipt['format_version'], 1, 1)
    string(receipt['reviewer'], 1, 80)
    integer(receipt['reviewed_at'], 0, 4102444800000)
    label(receipt['origin_id'])
    label(receipt['scope_id'])
    for key in ('baseline_digest', 'candidate_digest', 'audit_digest', 'receipt_digest'):
        hash_value(receipt[key])
    if receipt['decision'] != 'acknowledged':
        return False
    if digest({key: value for key, value in receipt.items() if key != 'receipt_digest'}) != receipt['receipt_digest']:
        return False
    return all(
        ((receipt[key] == report[key] for key in ('origin_id', 'scope_id', 'baseline_digest', 'candidate_digest', 'ruleset_version', 'audit_digest'))),
    )
