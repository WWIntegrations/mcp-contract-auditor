# Design

## Values, not executable declarations

`strict_json.py` performs string-aware depth and node-budget preflights before the recursive JSON parser, then repeats the node check alongside an iterative string check. JSON numbers become immutable `Number` values holding Decimal and their original lexeme. Equality and hashing ignore that lexeme. Integer fields accept mathematically integral JSON numbers; booleans remain a separate type. Numeric request ID `1` and string request ID `"1"` are different identities.

`canon-v1` sorts object keys by code point, preserves array order and Unicode text, and writes exact decimal digits from `Decimal.as_tuple()`. It never uses context-sensitive normalization or arithmetic. `artifact-json-v1` is separate: it chooses a legal compact numeric token, falling back to the original valid lexeme when necessary. For example, `123e308` cannot become `1.23e310` under this profile. The artifact writer escapes bidi, control and invisible format characters (a fixed list, including the Unicode tag block) for display; decoding restores the same value and hash.

The generic serializer checks actual UTF-8 byte length including its final LF. Public snapshot/receipt operations also roundtrip through parser limits. Report output is not an accepted trusted input API.

## Import and identity

`protocol.py` validates the exact transcript envelope, per-request metadata, response IDs, bounded tools and cursor chain. An empty cursor is data, not termination. A response without nextCursor must be the final exchange. JSON-RPC errors, truncated chains or duplicate names produce no snapshot.

`snapshot.py` sorts tools by name and hashes the complete declarations, including descriptions, unknown fields, icons, annotations and schema. Wire ordering, page IDs, cursors and TTL/cache-scope metadata belong to the separate transcript digest. A snapshot re-import checks its shape and recomputes its contract digest. Without the original transcript, its transcript digest is an unverified reference.

## Limited schema proof

`schema_diff.py` recognizes flat-object-v1 and builds a semantic projection. Comments/defaults do not constrain instance sets but remain in the declaration digest and textual findings. Required and enum arrays act as sets only for semantic comparison. Boolean and null domains are finite, so an explicit full enum can be equivalent to an omitted enum.

Equivalent projections are proved equivalent. Otherwise exactly one supported constraint may differ. Required-set, enum-set and additionalProperties changes have explicit directions. Integer/number changes are supported only without enums. New property names, incomparable sets, multiple changed constraints or any unsupported fragment yield unknown. The implementation does not combine local heuristics into an unsupported global proof.

`audit.py` separately computes every structural change using escaped JSON Pointers, schema coverage, input/output compatibility and versioned findings. Arrays are reported as complete changed subtrees. Renames are removal plus addition. Findings are deterministic and explain their rule through fixed reason codes; there is no scalar safety score.

## Receipts

`receipt.py` recomputes the audit from validated snapshots. `confirm` compares the expected audit digest before producing a timestamped acknowledgement. The CLI reads each input file once and reuses the in-memory models throughout this operation.

Receipt checking revalidates all bindings and its own digest. Moving both snapshots to a different matching context invalidates an earlier receipt with exit 1. Comparing snapshots whose contexts disagree is an input error with exit 2. A changed ruleset also invalidates acknowledgement. High and unknown findings remain after acknowledgement.

## Bounded stdio

`demo.py` is the only production subprocess path. Its public collector accepts only baseline/candidate, constructs an absolute command internally and passes an empty environment. Nonblocking stdin/stdout/stderr and selectors prevent a full stderr pipe blocking progress. Per-response deadlines and the whole capture window use a monotonic clock. Receipt time uses an independent UTC clock.

The private process-injection seam exists for negative tests and is not exposed as a command-line server path. `fixture_server.py` is self-contained, uses only stdlib JSON and stdio, and contains synthetic declarations without executable handlers. The fixture rejects other methods rather than forwarding them.

## Primary references

The versioned profile follows the [MCP 2026-07-28 base protocol](https://modelcontextprotocol.io/specification/2026-07-28/basic), [schema reference](https://modelcontextprotocol.io/specification/2026-07-28/schema), [pagination](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination) and [stdio transport](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio). Instance-set rules are informed by [JSON Schema 2020-12 validation](https://json-schema.org/draft/2020-12/json-schema-validation). Limits, canonical encoding, finding classes and receipts are project policy, not claims of full MCP or JSON Schema validator compliance.
