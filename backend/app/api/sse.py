"""SSE frame construction — the single place a `data:` field is built.

DEF127. Every streamed surface (Room `agent_token`, Brief Your Agent, 1-on-1)
puts model- and error-derived text on the wire inside an `event:`/`data:` pair.
An SSE event ends at the first blank line and a `data:` field ends at the first
newline, so *any* raw newline reaching a `data:` field silently reframes the
stream: at best the client loses everything after the first line, at worst the
remainder is parsed as further events the server never sent.

That was live, not hypothetical — the three error senders interpolated
`str(e)[:300]` straight into the frame, and a message containing
`"\\n\\nevent: verdict\\ndata: {...}"` put a **forged verdict event** on the wire
byte-identical to a genuine one.

The fix is a choke point rather than an escape call at each sender, because the
recurring failure in this codebase is the *allowlist instead of invariant* shape
(CR104 r1-2, DEF120 r1-2): patching the four senders you know about leaves the
fifth one wrong. `test_def127_sse_framing_invariant.py` asserts that no module
under `app/` frames an SSE event any other way, so a new sender cannot be added
without coming through here.

Two framers, because the two payload kinds need opposite treatment:

- `sse_text` escapes, and is the inverse of the client's `unescapeSseText`
  (`mobile/lib/services/api/api_client.dart`). The escape chain is byte-for-byte
  the one already on the wire, so this is not a format change.
- `sse_json` does **not** escape — `json.dumps` already renders newlines as the
  two characters `\\n`, and running the text chain over it would double-escape
  every backslash and corrupt the payload. It asserts instead.
"""

from __future__ import annotations


class SseFramingError(ValueError):
    """A payload that would break out of its own `data:` field.

    Raised rather than silently repaired: a JSON payload with a raw newline in
    it means the serializer changed under us, and per CR040 that must be loud.
    """


def escape_sse_text(text: str) -> str:
    """Escape a **complete** value for a single-line `data:` field.

    Complete is the load-bearing word. The client decodes each event's data
    independently, so an escape sequence must never span two events; callers
    pass a whole chunk, never a partial one.

    DEF140: only a raw LF is escaped, a raw CR is not — despite the W3C SSE
    spec also terminating a line on a lone CR, which makes a raw CR here the
    same framing hole DEF127 closed for LF. It is not escaped to a literal
    backslash-r because the shipped `0.1.0+56` Flutter decoder only inverts
    a backslash-n and a doubled backslash; an escaped CR would render as
    two literal characters in the field instead of being decoded back.
    `sse_text` below refuses a raw CR outright instead — the loud
    DEF127/CR040 shape — rather than silently normalising it to LF, since
    normalising would change delivered text a producer never asked to
    change.
    """
    return text.replace("\\", "\\\\").replace("\n", "\\n")


def sse_text(event: str, text: str) -> str:
    """Frame one SSE event whose payload is bare (non-JSON) text."""
    if "\r" in text:
        raise SseFramingError(
            f"SSE text payload for event {event!r} contains a raw carriage "
            f"return; a lone CR ends an SSE line per the W3C spec just like "
            f"a raw LF, and it cannot be escaped without the shipped client "
            f"decoder rendering the escape literally (see escape_sse_text)"
        )
    return f"event: {event}\ndata: {escape_sse_text(text)}\n\n"


def sse_json(event: str, payload: str) -> str:
    """Frame one SSE event whose payload is an already-serialized JSON string.

    `payload` comes from `json.dumps(...)` or pydantic's `model_dump_json()`,
    both of which escape newlines themselves. Escaping again would corrupt it,
    so this asserts the property instead of imposing it.
    """
    if "\n" in payload or "\r" in payload:
        raise SseFramingError(
            f"SSE payload for event {event!r} contains a raw newline; it would "
            f"terminate the data field early and reframe the stream"
        )
    return f"event: {event}\ndata: {payload}\n\n"
