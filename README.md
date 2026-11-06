# MCP Contract Auditor

Compare two recorded MCP tool catalogs, explain contract changes, and acknowledge one exact audit digest. The auditor inspects declarations. It never calls a tool, starts an arbitrary server, grants permission or declares a server safe.

Python 3.11+, standard library, no runtime dependencies. The supported MCP profile is **2026-07-28**. Schema analysis uses the deliberately narrow `flat-object-v1` subset of JSON Schema 2020-12. Hashes use `canon-v1`; findings use `audit-v1`.

## Recorded walkthrough

![Contract artwork, recorded tool declarations, changes and digest receipts](docs/showcase.gif)

[Watch the MP4](docs/showcase.mp4). This 40.28-second browser capture shows
actual controls over synthetic artifacts captured from two local fixture
processes. Opening the artwork does not run a tool or acknowledge an audit.
[Recording metadata](docs/recording.json) binds the movie to the exact
published HTML. The animation and inspected data work locally.

## Run

```sh
python3 -m unittest discover -s tests -v
python3 -m mcp_auditor demo
python3 -m mcp_auditor import examples/baseline-transcript.json > baseline.json
python3 -m mcp_auditor import examples/candidate-transcript.json > candidate.json
python3 -m mcp_auditor diff baseline.json candidate.json > report.json
python3 -m mcp_auditor confirm baseline.json candidate.json --expected-digest AUDIT_HASH --reviewer "Local operator" > receipt.json
python3 -m mcp_auditor check-receipt baseline.json candidate.json receipt.json
```

Replace `AUDIT_HASH` with the full `audit_digest` from your report. The `diff` command deliberately exits 1 for the supplied candidate because it contains changes requiring review. Shell redirection is controlled by the caller; the application does not overwrite a baseline or maintain a hidden approval store.

[Interactive demonstration](docs/index.html) presents the same synthetic artifacts. [Design](docs/design.md) and [threat model](docs/threat-model.md) describe the boundaries. `examples/demo.json` contains both transcripts, snapshots, the report, a matching receipt and the result of checking that receipt against a later changed declaration.

## Open the presentation

```sh
python3 tools/serve.py --port 3407
```

Open `http://127.0.0.1:3407/docs/index.html`. This loopback server exposes only
`docs/`. The standalone viewer needs no account, external resources or source
collection. Its exports retain the exact original artifact serializer text;
it does not accept arbitrary imported CLI artifacts.

To rebuild the procedural Three.js presentation, use the pinned build-only
dependencies from the npm lockfile:

```sh
npm ci
npm run build
```

This performs a fresh local fixture capture. Python core use requires none of
those JavaScript dependencies. No server, model or declared tool is contacted.
The measured visual reference is [Noomo Labs](https://labs.noomoagency.com/).
Geometry, lighting and artwork are original. Anton and Departure Mono are OFL
substitutes; motion curves and the mobile composition are adaptations.
[Sources and licenses](RESEARCH.md) document these differences.

## Actual process, synthetic declarations

`demo` starts the supplied fixture twice with an absolute Python executable, `-I -B`, an empty environment and the fixed `baseline` or `candidate` argument. Each case returns two real stdio pages. The first page's cursor is an empty string, which still requires the second page. Every request in the captured transcript is `tools/list`.

The candidate adds `archive_note`, requires an existing `mode` property, changes a description and changes a read-only hint. An unchanged `$ref` remains outside analysis coverage. The fixture has no handlers that execute these declared tools. It uses no network, API keys, models or third-party services. Its isolation flags are not a sandbox for arbitrary code.

The fixed demo produces five findings: three `high`, one `review` and one `unknown`. Its acknowledgement remains visible alongside those findings. A subsequent description change invalidates the old receipt.

## What the result means

| Result | Meaning |
| --- | --- |
| `compatible` | A supported declaration change preserves the analyzed direction of the JSON instance set |
| `breaking` | A supported input narrows, or a supported output widens |
| `unknown` | The schema or combination of changes is outside the supported proof rules |
| `not_declared` | Both versions omit outputSchema; no output compatibility claim |
| `acknowledged` | A named local operator acknowledged the exact comparison digest |

A receipt is not authenticated identity, a digital signature, authorization to execute, or evidence of tool behavior. Tool annotations are untrusted hints. `origin_id` and `scope_id` are operator-supplied context labels. Comparing different contexts fails; there is no force override.

Only flat objects with typed scalar properties, required sets, scalar enums, additionalProperties and a single supported constraint change receive a set relation. New property names, multiple changed constraints, nested objects, arrays, references, patterns and custom keywords yield `unknown`. They remain in the full structural diff and digest. References and icons are never fetched; patterns are never compiled.

## Exact artifacts and bounds

Numbers retain an exact Decimal value and an input lexeme. Canonical hash bytes expand decimal exponents without using the Decimal context precision. The separate artifact writer emits legal, unquoted numeric tokens and preserves exact values, including `123e308` and long coefficients. It never converts Decimal to float or string-valued JSON. Different numeric spellings can have the same digest.

The parser rejects duplicate keys, invalid UTF-8, BOM, nonfinite numbers, lone surrogates, trailing data, excessive depth/nodes and out-of-profile numeric tokens. Ordinary input files are opened once with size bounds; symlinks, devices and FIFOs are refused. Artifact JSON visibly escapes control and bidi characters without changing their decoded value or canonical digest.

| Boundary | Limit |
| --- | --- |
| Transcript / captured stdout | 4 MiB |
| One stdout message, including LF | 1 MiB |
| Captured stderr | 64 KiB, never printed raw |
| Pages / tools | 8 / 256 |
| Canonical Tool | 64 KiB |
| Snapshot or receipt read/write | 8 MiB |
| Report or demo output | 16 MiB |
| JSON depth / nodes / string | 32 / 50,000 / 16,384 code points |
| Numeric token / explicit exponent | 64 characters / absolute value at most 308 |
| Response / capture window | 3 seconds / 15 seconds, monotonic |

After the final page the client closes stdin, drains both streams, requires exit 0 and rejects extra messages. Cleanup grace is at most one second before terminating the owned process. These limits do not promise a hard deadline for parsing, diffing or formatting.

`import` and `confirm` return 0 on success, 2 on error. `diff` returns 0 only for an identical contract without high/review/unknown findings, 1 for a change or review requirement, 2 for an input/integrity error. `check-receipt` returns 0 for an exact match, 1 for a mismatch, 2 for invalid input or an operational error. Output is fully built and checked before stdout emission; errors use diagnostic codes on stderr.

Tests exercise real child processes, incomplete pagination, output bounds, unexpected messages, timeout cleanup, exact numeric roundtrips at Decimal precision 6 and 28, schema relations, receipt invalidation and CLI exit codes. They do not test real MCP tool execution or arbitrary server safety. Complete pagination describes the supplied transcript, not an atomic view of a changing external server.

MIT license for the original code and synthetic fixtures.
