"""
Regression suite: commands/help.md must describe the ACTUAL command tree.

Audit finding (garden-docs review, 2026-06): help.md described a retired v6
architecture — it advertised `crew` and `delivery` domains that have no
`commands/` directory, and omitted the headline top-level commands `prove`,
`compile`, and the `archetype` domain. Nothing caught the drift because no test
diffed the advertised surface against the real one.

This suite is that test. It parses the domains and top-level commands that
help.md advertises and compares them against the filesystem:

  - FAIL if help advertises a domain (``<name>:`` referenced in the Domains
    table or anywhere as a ``domain:command`` token) that has no
    ``commands/<name>/`` directory.
  - FAIL if a real top-level command (``commands/<name>.md``) is not mentioned
    anywhere in help.md.

Extraction is deliberately tolerant (token-level), so help can phrase prose
freely as long as every advertised domain is real and every real headline
command is mentioned.
"""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
COMMANDS_DIR = REPO / "commands"
HELP_MD = COMMANDS_DIR / "help.md"

# Top-level commands that exist as files but are NOT user-facing entry points
# the operator would look for in help. `help` documents itself; report-issue/
# reset are utility surfaces. Keep this list tight — it only suppresses
# self-reference, not real omissions.
HELP_OPTIONAL_TOPLEVEL = {"help"}

# Match a `domain:command` namespace token (e.g. `engineering:review`,
# `archetype:build`). Domain is the segment before the first colon.
DOMAIN_TOKEN_RE = re.compile(r"\b([a-z][a-z0-9-]*):[a-z][a-z0-9-]+")


def _real_domains() -> set[str]:
    """Domain directories that actually exist under commands/."""
    return {p.name for p in COMMANDS_DIR.iterdir() if p.is_dir()}


def _real_toplevel_commands() -> set[str]:
    """Top-level commands: commands/<name>.md (stem only)."""
    return {p.stem for p in COMMANDS_DIR.glob("*.md")}


def _help_text() -> str:
    return HELP_MD.read_text(encoding="utf-8")


def _advertised_domains(text: str) -> set[str]:
    """
    Domains help.md advertises. We treat the left side of any `domain:command`
    token as an advertised domain. Sibling-plugin namespaces (wicked-brain,
    wicked-testing, wicked-garden, wicked-vault, wicked-loom) are not
    wicked-garden command domains, so they are excluded.
    """
    sibling_namespaces = {
        "wicked-brain",
        "wicked-testing",
        "wicked-garden",
        "wicked-vault",
        "wicked-loom",
    }
    domains = {m.group(1) for m in DOMAIN_TOKEN_RE.finditer(text)}
    return domains - sibling_namespaces


def test_help_advertises_only_real_domains():
    """Every `domain:` namespace help.md advertises must have a commands/ dir."""
    real = _real_domains()
    advertised = _advertised_domains(_help_text())
    phantom = sorted(advertised - real)
    assert not phantom, (
        "commands/help.md advertises domain(s) with no commands/<domain>/ "
        f"directory: {phantom}. Real domains: {sorted(real)}. "
        "Update help.md to match the actual command tree."
    )


def test_help_mentions_every_toplevel_command():
    """Every real commands/<name>.md must be mentioned somewhere in help.md."""
    text = _help_text()
    real_toplevel = _real_toplevel_commands() - HELP_OPTIONAL_TOPLEVEL
    missing = sorted(name for name in real_toplevel if name not in text)
    assert not missing, (
        "commands/help.md omits top-level command(s) that exist on disk: "
        f"{missing}. Each commands/<name>.md must be mentioned in help.md so "
        "operators can discover it."
    )


@pytest.mark.parametrize("domain", sorted(_real_domains()))
def test_every_real_domain_is_advertised(domain: str):
    """Every real commands/<domain>/ must appear in help.md (no silent domains)."""
    advertised = _advertised_domains(_help_text())
    assert domain in advertised, (
        f"commands/help.md does not advertise the real domain '{domain}'. "
        "Add it to the Domains table so operators can discover it."
    )
