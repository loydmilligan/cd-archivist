"""Hand-rolled JSON syntax highlighter for the right-drawer card-detail.

Per the sprint-7 design handoff: `source.json` renders inside a
`<pre class="cda-json">` with `.k` / `.s` / `.n` / `.b` spans for
keys, strings, numbers, and booleans/nulls. The schema is small and
stable — no external highlight library required.

Output is HTML-safe (string contents and keys are escaped). Indentation
uses two spaces per level. Tokens emitted in JSON order.
"""
from __future__ import annotations

import html
from typing import Any

__all__ = ["highlight"]


def highlight(obj: Any) -> str:
    """Render `obj` to a `<pre class="cda-json">…</pre>` HTML string.

    Accepts anything `json.dumps` would accept. Containers (dict, list,
    tuple) are walked recursively; scalars are wrapped in one of four
    `<span class>` flavours: keys=k, strings=s, numbers=n,
    booleans/null=b.
    """
    body = _render(obj, indent=0)
    return f'<pre class="cda-json">{body}</pre>'


def _render(obj: Any, *, indent: int) -> str:
    if isinstance(obj, dict):
        return _render_dict(obj, indent=indent)
    if isinstance(obj, list | tuple):
        return _render_list(list(obj), indent=indent)
    return _render_scalar(obj)


def _render_dict(d: dict, *, indent: int) -> str:
    if not d:
        return "{}"
    inner_pad = "  " * (indent + 1)
    close_pad = "  " * indent
    parts: list[str] = []
    items = list(d.items())
    for i, (k, v) in enumerate(items):
        key_html = (
            f'<span class="k">"{html.escape(str(k))}"</span>'
        )
        value_html = _render(v, indent=indent + 1)
        comma = "," if i < len(items) - 1 else ""
        parts.append(f"{inner_pad}{key_html}: {value_html}{comma}")
    return "{\n" + "\n".join(parts) + f"\n{close_pad}}}"


def _render_list(items: list, *, indent: int) -> str:
    if not items:
        return "[]"
    inner_pad = "  " * (indent + 1)
    close_pad = "  " * indent
    parts: list[str] = []
    for i, v in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        parts.append(f"{inner_pad}{_render(v, indent=indent + 1)}{comma}")
    return "[\n" + "\n".join(parts) + f"\n{close_pad}]"


def _render_scalar(v: Any) -> str:
    if v is None:
        return '<span class="b">null</span>'
    if v is True:
        return '<span class="b">true</span>'
    if v is False:
        return '<span class="b">false</span>'
    if isinstance(v, bool):  # defensive — handled above
        return f'<span class="b">{str(v).lower()}</span>'
    if isinstance(v, int | float):
        return f'<span class="n">{v}</span>'
    return f'<span class="s">"{html.escape(str(v))}"</span>'
