"""The decision-report codebook a chat seat reads before it labels a turn (DC-S5, DES-decision-capture §4.3.3).

wicked-crew's chat directive tells every seat to read `skills/mem/refs/decision-report.md` and end its reply with a
fenced `wicked-decisions` JSON block. The recorder runs over (assistant proposal, operator reply) PAIRS, and the
decision text is written from the APPROVED PROPOSAL, not from the reply's words (operator decision, 2026-10-01).

Pinned here: the frontmatter parses strictly (the skills publish's yaml.safe_load), the file stays within 2 KB (it
is read on every labelled turn), the block's field vocabulary is the one crew parses, and no operator corpus text
was copied in (copy guard: no 6-word run of the local laya corpus appears; that half runs where the corpus exists,
WICKED_COPY_GUARD_CORPUS=<dir>, and is skipped elsewhere because the corpus never leaves the machine).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ci"))
from validate import frontmatter_yaml_error  # noqa: E402

CODEBOOK = _REPO_ROOT / "skills" / "mem" / "refs" / "decision-report.md"
TYPES = ["confirmation", "choice", "rule", "correction", "scope", "exception", "none"]
STEERING = ["architecture", "development", "security", "testing", "operations", "compliance", "design-ux"]
FIELDS = ["quote", "decision_text", "type", "codify", "ambiguous", "steering_type", "approves_proposal", "same_as"]


def _text() -> str:
    return CODEBOOK.read_text(encoding="utf-8")


def test_the_codebook_exists_within_two_kilobytes():
    assert CODEBOOK.is_file(), CODEBOOK
    assert len(CODEBOOK.read_bytes()) <= 2048, len(CODEBOOK.read_bytes())


def test_its_frontmatter_parses_strictly():
    text = _text()
    assert text.startswith("---\n")
    assert frontmatter_yaml_error(text) is None
    import yaml
    fm = yaml.safe_load(text.split("---\n", 2)[1])
    assert fm == {"codebook": "decision-report", "version": 1, "block": "wicked-decisions"}


def test_the_block_example_is_valid_json_with_every_field_and_only_known_values():
    m = re.search(r"```wicked-decisions\n(.*?)\n```", _text(), re.DOTALL)
    assert m, "the codebook shows the block"
    block = json.loads(m.group(1))
    assert list(block) == ["items"] and len(block["items"]) == 1
    item = block["items"][0]
    assert list(item) == FIELDS
    assert item["type"] in TYPES and item["steering_type"] in STEERING


def test_it_names_the_whole_vocabulary_and_the_pair_rule():
    text = _text()
    for word in TYPES + STEERING + FIELDS:
        assert f"`{word}`" in text, word
    flat = " ".join(text.split()).lower()
    # The unit is the pair, and the decision is written from the approved proposal, not the reply's words.
    assert "your previous reply" in flat and "from the proposal" in flat
    assert "never from the reply's words" in flat
    # Labels are suggestions: crew decides what is remembered.
    assert "crew decides" in flat


def _shingles(words: list[str], n: int = 6) -> set[str]:
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", s.lower())


@pytest.mark.skipif(not os.environ.get("WICKED_COPY_GUARD_CORPUS"),
                    reason="the operator corpus is local only (set WICKED_COPY_GUARD_CORPUS=<dir> to run the guard)")
def test_no_operator_corpus_text_was_copied_in():
    corpus = Path(os.environ["WICKED_COPY_GUARD_CORPUS"])
    assert corpus.is_dir(), corpus
    files = [p for p in corpus.rglob("*") if p.suffix in (".jsonl", ".json", ".txt") and p.is_file()]
    assert files, "a copy guard over no files proves nothing"
    # The controlled vocabulary (type, steering type and field names) is a schema, not corpus text.
    vocab = set(_words(" ".join(TYPES + STEERING + FIELDS)))
    mine = {sh for sh in _shingles(_words(_text())) if not set(sh.split()) <= vocab}
    hits = set()
    for p in files:
        hits |= mine & _shingles(_words(p.read_text(encoding="utf-8", errors="ignore")))
    assert not hits, sorted(hits)[:10]
