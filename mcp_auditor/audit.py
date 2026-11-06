"""Versioned, deterministic explanations; no execution or trust verdict."""
from .strict_json import canonical, digest, fail
from .snapshot import validate_snapshot
from .protocol import MCP_PROFILE, CANONICAL, RULESET, TOOL_FIELDS, HINTS
from .schema_diff import analyze, relation, compatibility
SEVERITIES = ('info', 'review', 'high', 'unknown')
COMPATIBILITIES = ('compatible', 'breaking', 'unknown', 'not_declared')
DEFAULT_HINTS = dict(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True)

def pointer_part(key):
    return key.replace('~', '~0').replace('/', '~1')

def structural(old, new, path='', old_present=True, new_present=True):
    if old_present and new_present and (canonical(old) == canonical(new)):
        return []
    if old_present and new_present and (type(old) is dict) and (type(new) is dict):
        changes = []
        for key in sorted(old.keys() | new.keys()):
            changes.extend(
                structural(old.get(key), new.get(key), path + '/' + pointer_part(key), key in old, key in new),
            )
        return changes
    return [
        dict(
            pointer=path,
            kind='added' if not old_present else 'removed' if not new_present else 'changed',
            before=dict(present=old_present, value=old if old_present else None),
            after=dict(present=new_present, value=new if new_present else None),
        ),
    ]

def opaque_paths(tool):
    paths = {'/' + pointer_part(key) for key in tool.keys() - TOOL_FIELDS}
    annotations = tool.get('annotations', {})
    paths.update(('/annotations/' + pointer_part(key) for key in annotations.keys() - (HINTS | {'title'})))
    for index, icon in enumerate(tool.get('icons', [])):
        paths.update(
            (('/icons/' + str(index) + '/' + pointer_part(key) for key in icon.keys() - {'src', 'mimeType', 'sizes', 'theme'})),
        )
    return paths

def text_paths(tool):
    paths = {'/' + key for key in ('title', 'description') if key in tool}
    if 'title' in tool.get('annotations', {}):
        paths.add('/annotations/title')

    def walk(node, path):
        if type(node) is dict:
            for key, value in node.items():
                child = path + '/' + pointer_part(key)
                if key in ('title', 'description', '$comment', 'default'):
                    paths.add(child)
                elif key in ('properties', '$defs', 'definitions', 'patternProperties') and type(value) is dict:
                    for name, subschema in value.items():
                        walk(subschema, child + '/' + pointer_part(name))
                else:
                    walk(value, child)
        elif type(node) is list:
            for index, value in enumerate(node):
                walk(value, path + '/' + str(index))
    for key in ('inputSchema', 'outputSchema'):
        if key in tool:
            walk(tool[key], '/' + key)
    return paths

def audit(old, new):
    old, new = (validate_snapshot(old), validate_snapshot(new))
    if (old['origin_id'], old['scope_id']) != (new['origin_id'], new['scope_id']):
        fail('input_context_mismatch')
    before = {tool['name']: tool for tool in old['tools']}
    after = {tool['name']: tool for tool in new['tools']}
    changes = []
    findings = []
    relations = []
    coverage = {side: dict(supported=0, unsupported=0, not_declared=0) for side in ('input', 'output')}

    def finding(rule, severity, tool, pointer, reason):
        item = dict(rule_id=rule, severity=severity, tool=tool, pointer=pointer, reason_code=reason)
        if item not in findings:
            findings.append(item)
    for name in sorted(before.keys() | after.keys()):
        left, right = (before.get(name), after.get(name))
        tool_changes = structural(left, right, old_present=name in before, new_present=name in after)
        changes.extend((dict(tool=name, **item) for item in tool_changes))
        if left is None or right is None:
            finding(
                'inventory_change',
                'review' if left is None else 'high',
                name,
                '',
                'tool_added' if left is None else 'tool_removed',
            )
        if right is not None:
            for side, key in (('input', 'inputSchema'), ('output', 'outputSchema')):
                status = 'not_declared' if key not in right else 'supported' if analyze(right[key]) is not None else 'unsupported'
                coverage[side][status] += 1
                if status == 'unsupported':
                    finding('opaque_schema', 'unknown', name, '/' + key, 'unsupported_schema')
        for path in sorted((opaque_paths(left) if left else set()) | (opaque_paths(right) if right else set())):
            finding('opaque_metadata', 'unknown', name, path, 'unknown_metadata')
        if left is None or right is None:
            continue
        for side, key in (('input', 'inputSchema'), ('output', 'outputSchema')):
            result = None if key not in left and key not in right else 'unknown' if key not in left or key not in right else relation(left[key], right[key])
            compatible = compatibility(result, side)
            relations.append(dict(tool=name, side=side, relation=result, compatibility=compatible))
            if compatible == 'breaking':
                finding('contract_breakage', 'high', name, '/' + key, side + '_breaking')
            if result == 'widens' and side == 'input':
                finding('input_surface_expanded', 'review', name, '/' + key, 'input_widens')
            if result == 'unknown':
                finding(
                    'opaque_schema',
                    'unknown',
                    name,
                    '/' + key,
                    'unsupported_schema' if key in right and analyze(right[key]) is None else 'relation_unknown',
                )
        protected = text_paths(left) | text_paths(right)
        for change in tool_changes:
            path = change['pointer']
            if any(
                ((path == text or path.startswith(text + '/') or text.startswith(path + '/') for text in protected)),
            ):
                finding('untrusted_text_change', 'high', name, path, 'text_changed')
            if path == '/icons' or path.startswith('/icons/') or path == '/_meta' or path.startswith('/_meta/'):
                finding('opaque_metadata', 'unknown', name, path, 'opaque_metadata_changed')
        a = DEFAULT_HINTS | {key: value for key, value in left.get('annotations', {}).items() if key in HINTS}
        b = DEFAULT_HINTS | {key: value for key, value in right.get('annotations', {}).items() if key in HINTS}
        for key in HINTS:
            old_annotations = left.get('annotations', {})
            new_annotations = right.get('annotations', {})
            if (key in old_annotations) == (key in new_annotations) and old_annotations.get(key) == new_annotations.get(key):
                continue
            expands = key == 'readOnlyHint' and a[key] and (not b[key]) or (key == 'openWorldHint' and (not a[key]) and b[key]) or (not b['readOnlyHint'] and (key == 'destructiveHint' and (not a[key]) and b[key] or (key == 'idempotentHint' and a[key] and (not b[key]))))
            finding(
                'declared_capability_expansion' if expands else 'hint_change',
                'high' if expands else 'review',
                name,
                '/annotations/' + key,
                'declared_expansion' if expands else 'hint_changed',
            )
        for change in tool_changes:
            if change['pointer'].startswith('/annotations/') and change['pointer'].split('/')[2] not in HINTS | {'title'}:
                finding('hint_change', 'review', name, change['pointer'], 'hint_changed')
        if tool_changes and (not any((item['tool'] == name for item in findings))):
            finding('representation_change', 'info', name, '', 'representation_changed')
    if not after:
        finding('inventory_empty', 'review', None, '', 'empty_candidate')
    changes.sort(key=lambda item: (item['tool'], item['pointer'], item['kind']))
    findings.sort(
        key=lambda item: (item['tool'] or '', item['pointer'], item['rule_id'], item['reason_code']),
    )
    relations.sort(key=lambda item: (item['tool'], item['side']))
    summary = {
        'severity': {severity: sum((item['severity'] == severity for item in findings)) for severity in SEVERITIES},
    }
    for side in ('input', 'output'):
        summary[side] = {status: sum((item['side'] == side and item['compatibility'] == status for item in relations)) for status in COMPATIBILITIES}
    report = dict(
        format_version=1,
        ruleset_version=RULESET,
        canonical_version=CANONICAL,
        protocol_version=MCP_PROFILE,
        origin_id=old['origin_id'],
        scope_id=old['scope_id'],
        baseline_digest=old['contract_digest'],
        candidate_digest=new['contract_digest'],
        tool_count=dict(baseline=len(before), candidate=len(after)),
        schema_coverage=coverage,
        schema_relations=relations,
        changes=changes,
        findings=findings,
        summary=summary,
    )
    report['audit_digest'] = digest(report)
    return report
