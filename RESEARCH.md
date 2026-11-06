# Design sources

This project compares complete tool-catalog transcripts and reports changes
to declarations. It does not execute tools, authenticate a remote server or
infer that a declaration describes safe behavior.

- [MCP versioning](https://modelcontextprotocol.io/docs/2026-07-28/learn/versioning)
  and [base protocol](https://modelcontextprotocol.io/specification/2026-07-28/basic):
  the supported profile is 2026-07-28, with per-request protocol metadata.
- [MCP schema reference](https://modelcontextprotocol.io/specification/2026-07-28/schema):
  the accepted complete tool-list response includes its result type, lifetime
  and cache scope. These fields do not grant permission to publish a catalog.
- [MCP pagination](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination):
  cursors remain opaque, including an empty string. Missing the final page
  cannot produce a successful snapshot.
- [MCP stdio transport](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio):
  the demonstration exchanges actual bounded UTF-8 messages with its own
  bundled fixture process. It accepts no external server command.
- [JSON Schema 2020-12](https://json-schema.org/draft/2020-12)
  and [object constraints](https://json-schema.org/understanding-json-schema/reference/object):
  schema relations are proved only for the documented flat-object subset.
  Unsupported keywords remain visible data, with an unknown relation.
- [Python Decimal](https://docs.python.org/3.11/library/decimal.html):
  numeric values retain exact decimal precision. Artifact serialization is
  separate from the canonical representation used for hashes.

## Visual reference and assets

[Noomo Labs](https://labs.noomoagency.com/) is the measured reference for the
spatial composition, glass enclosure, hold interaction and scroll motion.
Project geometry and code are original. The presentation does not distribute
Noomo models, textures, logos or commercial fonts. The reference's mobile
scene did not finish loading during inspection, so mobile visual equivalence
has not been established.

[Anton](https://github.com/google/fonts/tree/86aced91de05cd4f96a06838124cca45be337b2b/ofl/anton)
and [Departure Mono 1.350](https://github.com/rektdeckard/departure-mono/tree/c660dd9fae6f14ed94550094138031d4c38399d6)
are OFL font substitutes, not the reference's commercial typography. Their
licenses are included in [Anton OFL](docs/fonts/anton/OFL.txt) and
[Departure Mono OFL](docs/fonts/departure-mono/OFL.txt).

Sources consulted on 2026-11-06. They support design decisions, not a claim of
affiliation, certification or a full protocol/security audit.
