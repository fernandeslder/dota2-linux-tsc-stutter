"""Valve KeyValues (VDF) reader and *surgical* editor.

Steam's ``localconfig.vdf`` is a text KeyValues file.  We must read one key out
of it (a per-app ``LaunchOptions`` string) and write it back without disturbing
anything else in a 90 KB file that Steam also owns.  So this module does **not**
re-serialise the whole tree: it parses the file into an ordered tree that also
records the byte/char span of every key and value, then edits only the bytes that
belong to the key being changed.  Everything else in the file is left
byte-identical.

Grammar (the subset Steam emits)::

    document := pair*
    pair     := string ( node | string )
    node     := '{' pair* '}'

with ``//`` line comments and ``\\`` / ``\\"`` / ``\\n`` / ``\\t`` escapes inside
quoted strings.  Binary VDF (files that start with a NUL byte) is detected and
rejected with a clear error rather than being parsed as garbage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union

Value = Union[str, "VdfNode"]


class VdfError(Exception):
    """Malformed text VDF."""


class VdfBinaryError(VdfError):
    """The file is binary VDF (starts with a NUL byte); not supported here."""


_ESCAPE_OUT = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r"}
_ESCAPE_IN = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"'}


def quote(s: str) -> str:
    """Render a Python string as a quoted VDF token."""
    out = ['"']
    for ch in str(s):
        out.append(_ESCAPE_OUT.get(ch, ch))
    out.append('"')
    return "".join(out)


@dataclass
class VdfNode:
    """One ``{...}`` node: an ordered list of ``(key, value)`` pairs plus spans.

    ``spans[key]`` is ``(key_start, key_end, val_start, val_end)`` in *character*
    offsets into the source text, so an editor can rewrite just the value token.
    """

    items: List[Tuple[str, Value]] = field(default_factory=list)
    brace_open: Optional[int] = None
    brace_close: Optional[int] = None
    spans: dict = field(default_factory=dict)
    parent_key: str = ""

    # -- read --------------------------------------------------------------
    def keys(self) -> List[str]:
        return [k for k, _ in self.items]

    def get(self, key: str, default=None):
        for k, v in self.items:
            if k == key:
                return v
        return default

    def get_node(self, key: str) -> Optional["VdfNode"]:
        v = self.get(key)
        return v if isinstance(v, VdfNode) else None

    def as_dict(self) -> dict:
        """Plain nested dict (later duplicate keys win); for tests/inspection."""
        d = {}
        for k, v in self.items:
            d[k] = v.as_dict() if isinstance(v, VdfNode) else v
        return d

    # -- write -------------------------------------------------------------
    def set(self, key: str, value: Value) -> None:
        """In-memory set used when building a tree from scratch (no spans)."""
        for i, (k, _) in enumerate(self.items):
            if k == key:
                self.items[i] = (key, value)
                return
        self.items.append((key, value))

    def __contains__(self, key: str) -> bool:
        return any(k == key for k, _ in self.items)


def _tokenize(text: str):
    """Yield ``(kind, value, start, end)``; kind in {'str','open','close'}."""
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n\f\v":
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if c == "{":
            yield ("open", "", i, i + 1)
            i += 1
            continue
        if c == "}":
            yield ("close", "", i, i + 1)
            i += 1
            continue
        if c == '"':
            j = i + 1
            buf = []
            while j < n:
                d = text[j]
                if d == "\\" and j + 1 < n:
                    e = text[j + 1]
                    buf.append(_ESCAPE_IN.get(e, e))
                    j += 2
                    continue
                if d == '"':
                    break
                buf.append(d)
                j += 1
            else:
                raise VdfError(f"unterminated string starting at {i}")
            yield ("str", "".join(buf), i, j + 1)
            i = j + 1
            continue
        raise VdfError(f"unexpected character {c!r} at offset {i}")


class _Parser:
    def __init__(self, tokens: List[tuple]):
        self.toks = tokens
        self.i = 0

    def _peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def parse_body(self, brace_open: Optional[int] = None,
                   parent_key: str = "") -> VdfNode:
        items: List[Tuple[str, Value]] = []
        spans: dict = {}
        while True:
            t = self._peek()
            if t is None:
                if brace_open is not None:
                    raise VdfError("unexpected end of file inside a node")
                return VdfNode(items, brace_open, None, spans, parent_key)
            if t[0] == "close":
                if brace_open is None:
                    raise VdfError("unexpected '}' at top level")
                self.i += 1
                return VdfNode(items, brace_open, t[2], spans, parent_key)
            if t[0] != "str":
                raise VdfError(f"expected a key at offset {t[2]}, got {t[0]!r}")
            key_tok = t
            self.i += 1
            nxt = self._peek()
            if nxt is None:
                raise VdfError(f"key {key_tok[1]!r} has no value")
            if nxt[0] == "open":
                self.i += 1
                child = self.parse_body(nxt[2], key_tok[1])
                val: Value = child
                val_start, val_end = nxt[2], (child.brace_close + 1
                                              if child.brace_close is not None else nxt[3])
            elif nxt[0] == "str":
                self.i += 1
                val = nxt[1]
                val_start, val_end = nxt[2], nxt[3]
            else:
                raise VdfError(f"expected a value for {key_tok[1]!r} at offset {nxt[2]}")
            items.append((key_tok[1], val))
            spans[key_tok[1]] = (key_tok[2], key_tok[3], val_start, val_end)


class VdfDocument:
    """A loaded VDF file that supports targeted, non-destructive edits."""

    def __init__(self, text: str):
        self.text = text
        self.root = _Parser(list(_tokenize(text))).parse_body(None)

    # -- loading -----------------------------------------------------------
    @classmethod
    def loads(cls, data: Union[str, bytes]) -> "VdfDocument":
        if isinstance(data, bytes):
            if data[:1] == b"\x00":
                raise VdfBinaryError("binary VDF is not supported (file starts with NUL)")
            text = data.decode("utf-8", "surrogateescape")
        else:
            if data[:1] == "\x00":
                raise VdfBinaryError("binary VDF is not supported (file starts with NUL)")
            text = data
        return cls(text)

    @classmethod
    def load(cls, path: str) -> "VdfDocument":
        with open(path, "rb") as fh:
            return cls.loads(fh.read())

    def dumps(self) -> bytes:
        return self.text.encode("utf-8", "surrogateescape")

    def save(self, path: str) -> None:
        with open(path, "wb") as fh:
            fh.write(self.dumps())

    def _reparse(self) -> None:
        self.root = _Parser(list(_tokenize(self.text))).parse_body(None)

    # -- traversal ---------------------------------------------------------
    def node(self, keys: List[str]) -> Optional[VdfNode]:
        cur = self.root
        for k in keys:
            nxt = cur.get_node(k)
            if nxt is None:
                return None
            cur = nxt
        return cur

    def iter_nodes(self, _node: Optional[VdfNode] = None, _path: tuple = ()):
        """Yield ``(path_tuple, node)`` for every node, depth-first, in file order."""
        node = self.root if _node is None else _node
        for k, v in node.items:
            if isinstance(v, VdfNode):
                p = _path + (k,)
                yield p, v
                yield from self.iter_nodes(v, p)

    def find_path_by_suffix(self, suffix: List[str]) -> Optional[tuple]:
        """First node path whose last ``len(suffix)`` components equal *suffix*.

        localconfig.vdf is wrapped in ``"UserLocalConfigStore"``, but that wrapper
        is not guaranteed; matching on a path *suffix* (e.g.
        ``["Software","Valve","Steam","apps","570"]``) is robust to it.
        """
        suffix = tuple(suffix)
        if not suffix:
            return ()
        for path, _ in self.iter_nodes():
            if len(path) >= len(suffix) and path[-len(suffix):] == suffix:
                return path
        return None

    def get_suffix(self, suffix: List[str]) -> Optional[str]:
        """Value of a string key addressed by a path *suffix* (root wrapper agnostic)."""
        if not suffix:
            return None
        path = self.find_path_by_suffix(suffix[:-1])
        if path is None:
            return None
        node = self.node(list(path))
        v = node.get(suffix[-1]) if node else None
        return v if isinstance(v, str) else None

    def set_suffix(self, suffix: List[str], value: str) -> None:
        """Set a string key addressed by a path *suffix*; inserts the key if absent."""
        if not suffix:
            raise VdfError("empty key path")
        path = self.find_path_by_suffix(suffix[:-1])
        if path is None:
            raise VdfError("node not found for " + "/".join(suffix[:-1]))
        self.set(list(path) + [suffix[-1]], value)

    def delete_suffix(self, suffix: List[str]) -> bool:
        if not suffix:
            return False
        path = self.find_path_by_suffix(suffix[:-1])
        if path is None:
            return False
        return self.delete(list(path) + [suffix[-1]])

    def get(self, keys: List[str]) -> Optional[str]:
        """Value of ``keys[-1]`` under the node ``keys[:-1]``; None if absent."""
        if not keys:
            return None
        node = self.node(keys[:-1])
        if node is None:
            return None
        v = node.get(keys[-1])
        return v if isinstance(v, str) else None

    # -- editing -----------------------------------------------------------
    def set(self, keys: List[str], value: str) -> None:
        """Set ``keys[-1]`` to *value*, rewriting only the affected token.

        If the key exists its value token is replaced in place; otherwise a new
        ``"key"<tab><tab>"value"`` line is inserted just before the parent's
        closing brace, indented one level deeper than that brace.
        """
        if not keys:
            raise VdfError("cannot set an empty key path")
        node = self.node(keys[:-1])
        if node is None:
            raise VdfError("parent node not found for " + "/".join(keys))
        if node.brace_close is None:
            raise VdfError("is the file root actually a node? " + "/".join(keys[:-1]))
        key = keys[-1]
        new_tok = quote(value)
        if key in node.spans:
            _ks, _ke, vs, ve = node.spans[key]
            self.text = self.text[:vs] + new_tok + self.text[ve:]
        else:
            close = node.brace_close
            indent = _child_indent(self.text, close)
            ins = f"\n{indent}{quote(key)}\t\t{new_tok}"
            self.text = self.text[:close] + ins + self.text[close:]
        self._reparse()

    def delete(self, keys: List[str]) -> bool:
        """Delete a string-valued key together with its whole line. Returns False if absent."""
        if not keys:
            return False
        node = self.node(keys[:-1])
        if node is None or keys[-1] not in node.spans:
            return False
        _ks, _ke, _vs, ve = node.spans[keys[-1]]
        ls = self.text.rfind("\n", 0, node.spans[keys[-1]][0]) + 1
        le = self.text.find("\n", ve)
        le = len(self.text) if le < 0 else le + 1
        self.text = self.text[:ls] + self.text[le:]
        self._reparse()
        return True

    def render(self) -> str:
        """Canonical re-serialisation (tabs, one pair per line) -- for tests/inspection."""
        out: List[str] = []

        def emit(node: VdfNode, depth: int) -> None:
            ind = "\t" * depth
            for k, v in node.items:
                if isinstance(v, VdfNode):
                    out.append(f"{ind}{quote(k)}")
                    out.append(f"{ind}{{")
                    emit(v, depth + 1)
                    out.append(f"{ind}}}")
                else:
                    out.append(f"{ind}{quote(k)}\t\t{quote(v)}")

        emit(self.root, 0)
        return "\n".join(out) + "\n"


def _child_indent(text: str, close_offset: int) -> str:
    """Indentation for a child of the node whose closing brace is at ``close_offset``.

    Children sit one tab deeper than the closing brace, matching Steam's style.
    """
    ls = text.rfind("\n", 0, close_offset) + 1
    close_indent = text[ls:close_offset]
    if close_indent.strip():
        # '}' is not alone on its line (unusual); fall back to two tabs.
        return "\t\t"
    return close_indent + "\t"
