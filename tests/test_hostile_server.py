"""Regressions for declarations shaped by a hostile server, within the documented bounds."""
import time
import unittest
from mcp_auditor.audit import audit
from mcp_auditor.strict_json import artifact_json
from mcp_auditor.snapshot import import_transcript
from test_protocol import transcript, tool


class HostileServerTests(unittest.TestCase):

    def test_many_unknown_annotation_keys_audit_in_linear_time(self):
        # 20 tools x 1000 unknown keys is a 181 KB transcript, far inside the
        # 4 MiB / 50,000 node bounds. Deduplicating findings with a list scan
        # made this take about 8 s; it must stay well under that.
        tools = []
        for index in range(20):
            item = tool('t%d' % index)
            item['annotations'] = {'k%d' % key: 0 for key in range(1000)}
            tools.append(item)
        value = import_transcript(artifact_json(transcript(tools)))
        started = time.monotonic()
        report = audit(value, value)
        elapsed = time.monotonic() - started
        self.assertEqual(report['summary']['severity']['unknown'], 20000)
        self.assertLess(elapsed, 3.0)


if __name__ == '__main__':
    unittest.main()
