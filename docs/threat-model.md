# Threat model

The auditor treats transcripts and declarations as untrusted data. It trusts its own Python installation, source files, OS and the operator's chosen local input paths. It is not a network client for arbitrary MCP servers, a tool-execution broker, an authorization service or an OS sandbox.

## Input and presentation

Duplicate keys and numeric rounding could hide declaration changes. Strict parsing, exact Decimal values, separate artifact serialization and recomputed digests address that boundary. A preflight depth limit protects the recursive parser; bounded bytes, nodes and strings limit retained input. Snapshot and receipt output must satisfy their own parser limits as well as their byte limits.

Descriptions can contain instructions, HTML, terminal escapes or bidi markers. Their contents remain in the digest and structural diff. The JSON artifact escapes controls, bidi characters and invisible format characters such as zero-width and Unicode tag characters, which can carry hidden text. HTML presentation must use textContent or equivalent escaping and visibly mark decoded controls. It must not fetch icons or turn declaration URLs into automatic requests. A high textual-change finding signals a need for review, not a diagnosis that prompt injection has occurred.

Schemas may contain file/HTTPS references, expensive regular expressions or unknown keywords. These are never resolved, opened, compiled or executed. Unsupported schemas remain visible with unknown analysis, even if unchanged.

## Process boundary

The only executable fixture is a supplied local module launched with an absolute interpreter, isolated mode, bytecode disabled and an empty environment. Runtime does not accept commands, server URLs, host configuration or plugin paths. The fixture has no tool handlers, network access code or child-process calls. These are properties of this trusted fixture, not a containment claim about arbitrary code under Python isolated mode.

Capture drains stdout and stderr concurrently, applies message/aggregate/deadline bounds, rejects unfinished or extra output and collects only its own child. Raw stderr and remote error descriptions are not printed. The negative-test harness may launch fixed synthetic fault programs; that seam is not a public CLI option.

## Identity and acknowledgement

Origin and scope are labels supplied by an operator, not authenticated server identity or account credentials. A malicious editor who rewrites a whole file and every hash can create another internally consistent artifact. SHA-256 detects inconsistency; it does not replace a signature, trusted distribution or publisher authentication.

A reviewer string is a local declaration. A receipt binds two contract digests, context, ruleset, exact audit and timestamp. It cannot authorize execution, conceal high/unknown findings or transfer to a different comparison. Checking it recomputes the audit rather than trusting imported compatible labels.

## Analysis limits

Compatibility concerns declared JSON instance sets within the supported profile. It does not test actual tool behavior, side effects, availability, privacy, correctness or access control. Untrusted hints never grant permission. Full JSON Schema validation, reference resolution, output testing and arbitrary MCP discovery are outside scope.

A complete cursor chain is not proof that an external catalog stayed unchanged while its pages were collected. An empty catalog is explicitly flagged and cannot be described as tested tools. TTL and cacheScope are recorded metadata, not permission to publish an imported private transcript. Use only synthetic or otherwise authorized data in shared artifacts.
