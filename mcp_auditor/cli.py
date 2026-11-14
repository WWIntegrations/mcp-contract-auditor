"""Stateless CLI: compute the entire bounded artifact before writing stdout."""
import argparse
import os
import sys
from .strict_json import read_file, parse_json, artifact_json, AuditError
from .snapshot import import_transcript, validate_snapshot
from .audit import audit
from .receipt import confirm, check_receipt
from .demo import Clock, run_demo
from . import summary

def snapshot_file(path):
    return validate_snapshot(parse_json(read_file(path, limit=8 * 1024 * 1024)))

def emit(value, limit, roundtrip=False):
    encoded = artifact_json(value, limit=limit)
    if roundtrip:
        parse_json(encoded, limit=limit)
    return encoded

def write_file(path, data, force):
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | (os.O_TRUNC if force else os.O_EXCL)
    try:
        fd = os.open(path, flags, 0o644)
    except FileExistsError:
        raise AuditError('output_exists') from None
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)

def main(argv=None):
    parser = argparse.ArgumentParser(prog='mcp-contract-auditor')
    commands = parser.add_subparsers(dest='command', required=True)
    importer = commands.add_parser('import')
    importer.add_argument('transcript')
    comparer = commands.add_parser('compare', help='import two transcripts in memory and diff them; exit 0 unless --strict')
    comparer.add_argument('baseline_transcript')
    comparer.add_argument('candidate_transcript')
    comparer.add_argument('--strict', action='store_true', help='exit 1 when changes need review, like diff')
    for name in ('diff', 'confirm', 'check-receipt'):
        command = commands.add_parser(name)
        command.add_argument('baseline')
        command.add_argument('candidate')
        if name == 'confirm':
            command.add_argument('--expected-digest', required=True)
            command.add_argument('--reviewer', required=True)
        if name == 'check-receipt':
            command.add_argument('receipt')
    commands.add_parser('demo')
    for command in commands.choices.values():
        command.add_argument('--json', action='store_true', help='print the full machine-readable artifact instead of a short summary')
    for name in ('import', 'diff', 'confirm'):
        commands.choices[name].add_argument('--out', help='also write the full JSON artifact to this file')
        commands.choices[name].add_argument('--force', action='store_true', help='overwrite --out if it exists')
    args = parser.parse_args(argv)
    try:
        if args.command == 'import':
            value = import_transcript(read_file(args.transcript, limit=4 * 1024 * 1024))
            code, limit, roundtrip = (0, 8 * 1024 * 1024, True)
            text = summary.import_text(value, args.out)
        elif args.command == 'compare':
            value = audit(import_transcript(read_file(args.baseline_transcript, limit=4 * 1024 * 1024)),
                          import_transcript(read_file(args.candidate_transcript, limit=4 * 1024 * 1024)))
            severities = value['summary']['severity']
            code = 1 if args.strict and (value['baseline_digest'] != value['candidate_digest'] or any(severities[k] for k in ('high', 'review', 'unknown'))) else 0
            limit, roundtrip = (16 * 1024 * 1024, False)
            text = summary.diff_text(value)
        elif args.command == 'demo':
            value = run_demo()
            code, limit, roundtrip = (0, 16 * 1024 * 1024, False)
            text = summary.demo_text(value)
        else:
            # Each input is opened once; confirmation reuses these exact models.
            baseline = snapshot_file(args.baseline)
            candidate = snapshot_file(args.candidate)
            if args.command == 'diff':
                value = audit(baseline, candidate)
                severities = value['summary']['severity']
                identical = value['baseline_digest'] == value['candidate_digest']
                code = 0 if identical and (not any((severities[key] for key in ('high', 'review', 'unknown')))) else 1
                limit, roundtrip = (16 * 1024 * 1024, False)
                text = summary.diff_text(value, hint=True)
            elif args.command == 'confirm':
                value = confirm(baseline, candidate, args.expected_digest, args.reviewer, Clock())
                code, limit, roundtrip = (0, 8 * 1024 * 1024, True)
                text = summary.confirm_text(value, args.out)
            else:
                receipt = parse_json(read_file(args.receipt, limit=8 * 1024 * 1024))
                matches = check_receipt(baseline, candidate, receipt)
                value = {'format_version': 1, 'matches': matches}
                code, limit, roundtrip = (0 if matches else 1, 8 * 1024 * 1024, True)
                text = summary.receipt_text(matches)
        encoded = emit(value, limit, roundtrip)
        if getattr(args, 'out', None):
            write_file(args.out, encoded, args.force)
        data = encoded if args.json else text.encode('utf-8')
        # Write UTF-8 bytes: a legacy console encoding must not turn output into a traceback (exit 1).
        binary = getattr(sys.stdout, 'buffer', None)
        if binary is None:
            sys.stdout.write(data.decode('utf-8'))
        else:
            sys.stdout.flush()
            binary.write(data)
            binary.flush()
        return code
    except AuditError as exc:
        print(exc.code, file=sys.stderr)
    except OSError:
        print('io_error', file=sys.stderr)
    return 2
