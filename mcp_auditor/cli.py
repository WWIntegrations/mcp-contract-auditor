"""Stateless CLI: compute the entire bounded artifact before writing stdout."""
import argparse
import sys
from .strict_json import read_file, parse_json, artifact_json, AuditError
from .snapshot import import_transcript, validate_snapshot
from .audit import audit
from .receipt import confirm, check_receipt
from .demo import Clock, run_demo

def snapshot_file(path):
    return validate_snapshot(parse_json(read_file(path, limit=8 * 1024 * 1024)))

def emit(value, limit, roundtrip=False):
    encoded = artifact_json(value, limit=limit)
    if roundtrip:
        parse_json(encoded, limit=limit)
    return encoded

def main(argv=None):
    parser = argparse.ArgumentParser(prog='mcp-contract-auditor')
    commands = parser.add_subparsers(dest='command', required=True)
    importer = commands.add_parser('import')
    importer.add_argument('transcript')
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
    args = parser.parse_args(argv)
    try:
        if args.command == 'import':
            value = import_transcript(read_file(args.transcript, limit=4 * 1024 * 1024))
            code, limit, roundtrip = (0, 8 * 1024 * 1024, True)
        elif args.command == 'demo':
            value = run_demo()
            code, limit, roundtrip = (0, 16 * 1024 * 1024, False)
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
            elif args.command == 'confirm':
                value = confirm(baseline, candidate, args.expected_digest, args.reviewer, Clock())
                code, limit, roundtrip = (0, 8 * 1024 * 1024, True)
            else:
                receipt = parse_json(read_file(args.receipt, limit=8 * 1024 * 1024))
                matches = check_receipt(baseline, candidate, receipt)
                value = {'format_version': 1, 'matches': matches}
                code, limit, roundtrip = (0 if matches else 1, 8 * 1024 * 1024, True)
        encoded = emit(value, limit, roundtrip)
        sys.stdout.write(encoded.decode('utf-8'))
        return code
    except AuditError as exc:
        print(exc.code, file=sys.stderr)
    except OSError:
        print('io_error', file=sys.stderr)
    return 2
