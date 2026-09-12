"""A tiny DOM for the draft self-checks — stdlib ``html.parser`` only.

The checks need three things from a self-contained HTML deliverable: the element tree (with
attributes), the ``<style>`` text in document order, and "which elements carry visible text".
That is all this module does; it is deliberately not a browser. Void elements are closed
immediately; unbalanced closing tags are tolerated (the nearest open ancestor with that tag is
closed), so a slightly malformed draft still yields a usable tree instead of an exception.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Iterator

VOID_TAGS = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)
# Elements whose text is never rendered to the reader.
NON_RENDERED_TAGS = frozenset("script style template noscript title head meta link".split())
_WS = re.compile(r"\s+")


@dataclass(eq=False)  # identity semantics — a structural __eq__ would recurse through children
class Node:
    tag: str  # "" for the document root, "#text" for text, "#comment" for comments
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)
    parent: "Node | None" = None
    text: str = ""  # #text / #comment payload

    # ── tree helpers ────────────────────────────────────────────────────────────────────────
    def ancestors(self) -> Iterator["Node"]:
        node = self.parent
        while node is not None and node.tag != "":
            yield node
            node = node.parent

    def element_children(self) -> list["Node"]:
        return [c for c in self.children if not c.tag.startswith("#")]

    def classes(self) -> list[str]:
        return self.attrs.get("class", "").split()

    def direct_text(self) -> str:
        """The element's own text (not descendants'), whitespace-collapsed."""
        parts = [c.text for c in self.children if c.tag == "#text"]
        return _WS.sub(" ", "".join(parts)).strip()

    def all_text(self) -> str:
        """The visible text of this element and its descendants, whitespace-collapsed."""
        out: list[str] = []
        for node in self.walk():
            if node.tag == "#text":
                out.append(node.text)
        return _WS.sub(" ", " ".join(out)).strip()

    def walk(self) -> Iterator["Node"]:
        yield self
        for child in self.children:
            yield from child.walk()

    def path(self) -> str:
        """A readable locator: ``section.page.page-1 > div.fact-strip > span``."""
        chain: list[str] = []
        node: Node | None = self
        while node is not None and node.tag != "":
            if node.tag.startswith("#"):
                node = node.parent
                continue
            label = node.tag
            if "id" in node.attrs and node.attrs["id"]:
                label += "#" + node.attrs["id"]
            label += "".join("." + c for c in node.classes()[:3])
            chain.append(label)
            node = node.parent
        return " > ".join(reversed(chain))

    def preceding_comments(self) -> list[str]:
        """Comments immediately before this element among its siblings (whitespace between
        is fine) — where a draft tends to hide an "illustrative" label."""
        if self.parent is None:
            return []
        out: list[str] = []
        siblings = self.parent.children
        idx = siblings.index(self)
        for sib in reversed(siblings[:idx]):
            if sib.tag == "#comment":
                out.append(sib.text)
            elif sib.tag == "#text" and not sib.text.strip():
                continue
            else:
                break
        return out


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node(tag="")
        self.cursor = self.root
        self.styles: list[str] = []
        self._in_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        node = Node(tag=tag, attrs={k.lower(): (v or "") for k, v in attrs}, parent=self.cursor)
        self.cursor.children.append(node)
        if tag in VOID_TAGS:
            return
        self.cursor = node
        self._in_style = tag == "style"

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        node = Node(tag=tag, attrs={k.lower(): (v or "") for k, v in attrs}, parent=self.cursor)
        self.cursor.children.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in VOID_TAGS:
            return
        node: Node | None = self.cursor
        while node is not None and node.tag != "":
            if node.tag == tag:
                self.cursor = node.parent or self.root
                self._in_style = False
                return
            node = node.parent
        # stray closing tag — ignore

    def handle_data(self, data: str) -> None:
        if self.cursor.tag == "style":
            self.styles.append(data)
        self.cursor.children.append(Node(tag="#text", text=data, parent=self.cursor))

    def handle_comment(self, data: str) -> None:
        self.cursor.children.append(Node(tag="#comment", text=data, parent=self.cursor))


@dataclass
class Document:
    root: Node
    styles: list[str]

    def elements(self) -> Iterator[Node]:
        for node in self.root.walk():
            if node.tag and not node.tag.startswith("#"):
                yield node

    def find_all(self, tag: str) -> list[Node]:
        return [n for n in self.elements() if n.tag == tag]

    def inline_style_text(self) -> str:
        return "\n".join(self.styles)


def parse(html: str) -> Document:
    builder = _Builder()
    builder.feed(html)
    builder.close()
    return Document(root=builder.root, styles=builder.styles)


def is_rendered(node: Node) -> bool:
    """False when the element or an ancestor is never shown to the reader (head/script/style,
    the ``hidden`` attribute, ``aria-hidden`` is NOT enough — sighted readers still see it)."""
    chain = [node, *node.ancestors()]
    for n in chain:
        if n.tag in NON_RENDERED_TAGS:
            return False
        if "hidden" in n.attrs:
            return False
    return True


def text_elements(doc: Document) -> Iterator[Node]:
    """Rendered elements carrying their OWN non-blank text (the unit a contrast or claims check
    judges — a ``<span>`` inside a ``<p>`` is its own element with its own colour)."""
    for node in doc.elements():
        if node.tag == "br":
            continue
        if not node.direct_text():
            continue
        if not is_rendered(node):
            continue
        yield node
