#!/usr/bin/env python3
"""_pack_registry.py — discovery + registration of third-party skill packs.

The extension contract (SKILL-RATIONALIZATION §5, gaps 1/2/4/6): a third
party ships a **pack** — a directory with a ``wicked-pack.json`` manifest and
a ``skills/`` tree following the catalog naming rules
(``{vendor}-{domain}`` router + ``{vendor}-{domain}-{role}`` fork workers).
Garden's runtime discovers installed packs WITHOUT a garden PR: no edit to
components.json / specialist.json is ever required for a pack to register.

Discovery sources, in priority order (first occurrence of a pack name wins):

  1. ``WICKED_PACK_PATH`` env — ``os.pathsep``-separated dirs; each entry is
     either a pack root (contains wicked-pack.json) or a directory of pack
     roots. Explicit operator intent — highest priority.
  2. The registered-pack file (``pack register`` / wicked-installer writes
     it): ``~/.something-wicked/wicked-garden/packs/registered.json``
     (override with ``WICKED_PACK_REGISTRY``). This is how npm-installed
     packs surface — the installer registers the resolved package dir.
  3. Claude Code plugin dirs: ``~/.claude/plugins/<name>/`` (direct
     installs) and ``~/.claude/plugins/cache/<marketplace>/<plugin>/``
     (marketplace cache) that contain a wicked-pack.json.
  4. Project-local packs: ``<cwd>/.wicked/packs/<name>/``.

Provenance (gap 4, minimal + honest): registration records the declared
``provenance`` block plus a sha256 of the manifest and a content hash of the
skills tree. There is NO signing — the hashes detect post-registration drift,
they do not prove authorship. See docs/extending.md "Trust model".

Peer floors (gap 6, fail-open): a pack may declare ``peers`` —
``{"wicked-garden": ">=12.29.0", "wicked-vault": ">=0.5.0"}``.
``check_peer_floors()`` compares floors against what is actually installed
and returns violations as data. It NEVER raises and never blocks: an
unprobeable peer reports status "unknown", not a violation.

stdlib-only — importable from hooks. Fail-open everywhere: a malformed pack
is skipped (collected under ``errors``), never a crash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_NAME = "wicked-pack.json"
SPEC_VERSION = 1

# ``wicked`` is the reserved first-party vendor prefix — third-party packs
# must never claim it (ruling naming rule #3).
RESERVED_VENDOR_PREFIXES = ("wicked",)

_KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_MAX_NAME_LEN = 64
# Accepted peer-floor range shapes. Both are treated as an inclusive
# MAJOR.MINOR.PATCH floor (documented in docs/extending.md).
_FLOOR_RE = re.compile(r"^(>=|\^)\s*(\d+)\.(\d+)\.(\d+)$")
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")

_DEFAULT_REGISTRY = (
    Path.home() / ".something-wicked" / "wicked-garden" / "packs" / "registered.json"
)

_PROBE_TIMEOUT_S = 5  # bound for optional peer --version subprocess probes


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class Pack:
    """A discovered, structurally-valid pack."""

    name: str
    vendor: str
    version: str
    root: Path
    source: str                       # env | registered | plugin-dir | project
    skills_dir: Path
    description: str = ""
    domains: list = field(default_factory=list)   # manifest "domains" entries
    peers: dict = field(default_factory=dict)     # {package: floor-range}
    provenance: dict = field(default_factory=dict)
    manifest_sha256: str = ""

    def domain_names(self) -> list:
        return [d.get("name") for d in self.domains if isinstance(d, dict) and d.get("name")]

    def specialist_domain(self, domain: str) -> str:
        """The crew-facing specialist domain name: ``{vendor}-{domain}``."""
        return f"{self.vendor}-{domain}"


# ---------------------------------------------------------------------------
# Manifest loading + structural validation (the discovery-time light check;
# scripts/pack/check.py is the full conformance gate)
# ---------------------------------------------------------------------------

def load_manifest(root: Path) -> tuple:
    """Return ``(manifest_dict | None, [error strings])`` for a pack root."""
    manifest_path = Path(root) / MANIFEST_NAME
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [f"{manifest_path}: unreadable ({exc})"]
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"{manifest_path}: invalid JSON ({exc})"]
    if not isinstance(manifest, dict):
        return None, [f"{manifest_path}: manifest must be a JSON object"]
    return manifest, []


def structural_errors(manifest: dict, root: Path) -> list:
    """The minimum a pack must get right to be *discovered* at all."""
    errors: list = []

    spec = manifest.get("spec")
    if spec != SPEC_VERSION:
        errors.append(f"spec must be {SPEC_VERSION} (got {spec!r})")

    name = manifest.get("name")
    vendor = manifest.get("vendor")
    version = manifest.get("version")

    for label, value in (("name", name), ("vendor", vendor)):
        if not isinstance(value, str) or not _KEBAB_RE.match(value or ""):
            errors.append(f"{label} must be kebab-case (got {value!r})")
        elif len(value) > _MAX_NAME_LEN:
            errors.append(f"{label} exceeds {_MAX_NAME_LEN} chars: {value!r}")

    if isinstance(vendor, str):
        for reserved in RESERVED_VENDOR_PREFIXES:
            if vendor == reserved or vendor.startswith(reserved + "-"):
                errors.append(
                    f"vendor {vendor!r} uses the reserved prefix {reserved!r} "
                    "(wicked-* names belong to the first-party catalog)"
                )
    if isinstance(name, str) and isinstance(vendor, str) and _KEBAB_RE.match(vendor or ""):
        if name != vendor and not name.startswith(vendor + "-"):
            errors.append(f"name {name!r} must start with vendor prefix {vendor!r}")

    if not isinstance(version, str) or not _SEMVER_RE.match(version or ""):
        errors.append(f"version must be semver (got {version!r})")

    skills_rel = manifest.get("skills_dir", "skills")
    if not isinstance(skills_rel, str) or ".." in skills_rel.replace("\\", "/").split("/"):
        errors.append(f"skills_dir must be a relative path inside the pack (got {skills_rel!r})")
    else:
        skills_dir = Path(root) / skills_rel
        if not skills_dir.is_dir():
            errors.append(f"skills dir not found: {skills_dir}")

    domains = manifest.get("domains")
    if not isinstance(domains, list) or not domains:
        errors.append("domains must be a non-empty array")

    return errors


def _pack_from_manifest(manifest: dict, root: Path, source: str) -> Pack:
    skills_rel = manifest.get("skills_dir", "skills")
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode("utf-8")
    return Pack(
        name=manifest["name"],
        vendor=manifest["vendor"],
        version=manifest["version"],
        root=Path(root).resolve(),
        source=source,
        skills_dir=(Path(root) / skills_rel).resolve(),
        description=str(manifest.get("description", "")),
        domains=[d for d in manifest.get("domains", []) if isinstance(d, dict)],
        peers=manifest.get("peers", {}) if isinstance(manifest.get("peers"), dict) else {},
        provenance=manifest.get("provenance", {}) if isinstance(manifest.get("provenance"), dict) else {},
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def registry_path() -> Path:
    override = os.environ.get("WICKED_PACK_REGISTRY")
    return Path(override) if override else _DEFAULT_REGISTRY


def _read_registry_file() -> dict:
    try:
        data = json.loads(registry_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _candidate_roots(cwd: Path) -> list:
    """Yield ``(root, source)`` candidates in priority order (may repeat)."""
    candidates: list = []

    # 1. WICKED_PACK_PATH — pack roots or directories of pack roots.
    for entry in filter(None, os.environ.get("WICKED_PACK_PATH", "").split(os.pathsep)):
        p = Path(entry).expanduser()
        if (p / MANIFEST_NAME).is_file():
            candidates.append((p, "env"))
        elif p.is_dir():
            try:
                for child in sorted(p.iterdir()):
                    if (child / MANIFEST_NAME).is_file():
                        candidates.append((child, "env"))
            except OSError:
                pass

    # 2. Registered packs (pack register / wicked-installer).
    for record in _read_registry_file().get("packs", []):
        if isinstance(record, dict) and record.get("path"):
            p = Path(record["path"]).expanduser()
            if (p / MANIFEST_NAME).is_file():
                candidates.append((p, "registered"))

    # 3. Claude Code plugin dirs (direct installs + marketplace cache).
    plugins_root = Path.home() / ".claude" / "plugins"
    scan_dirs = [plugins_root]
    cache_root = plugins_root / "cache"
    try:
        if cache_root.is_dir():
            scan_dirs.extend(sorted(d for d in cache_root.iterdir() if d.is_dir()))
    except OSError:
        pass
    for base in scan_dirs:
        try:
            if not base.is_dir():
                continue
            for child in sorted(base.iterdir()):
                if (child / MANIFEST_NAME).is_file():
                    candidates.append((child, "plugin-dir"))
        except OSError:
            continue

    # 4. Project-local packs.
    local = cwd / ".wicked" / "packs"
    try:
        if local.is_dir():
            for child in sorted(local.iterdir()):
                if (child / MANIFEST_NAME).is_file():
                    candidates.append((child, "project"))
    except OSError:
        pass

    return candidates


def discover_packs(cwd: "Path | None" = None) -> tuple:
    """Return ``(packs, errors)`` — structurally-valid packs, deduped by name.

    Never raises. A candidate with structural errors is skipped and its
    errors reported; a later duplicate of an already-seen pack name is
    silently ignored (priority order above is the tiebreak).
    """
    cwd = Path(cwd) if cwd else Path(os.environ.get("CLAUDE_CWD", os.getcwd()))
    packs: list = []
    errors: list = []
    seen: set = set()

    try:
        candidates = _candidate_roots(cwd)
    except Exception as exc:  # noqa: BLE001 — discovery is strictly fail-open
        return [], [f"pack discovery failed: {exc}"]

    for root, source in candidates:
        try:
            resolved = Path(root).resolve()
            manifest, load_errs = load_manifest(resolved)
            if load_errs or manifest is None:
                errors.extend(load_errs)
                continue
            struct_errs = structural_errors(manifest, resolved)
            if struct_errs:
                errors.extend(f"{resolved}: {e}" for e in struct_errs)
                continue
            if manifest["name"] in seen:
                continue
            seen.add(manifest["name"])
            packs.append(_pack_from_manifest(manifest, resolved, source))
        except Exception as exc:  # noqa: BLE001 — skip broken candidates
            errors.append(f"{root}: {exc}")

    return packs, errors


# ---------------------------------------------------------------------------
# Registration (gap 1 install seam + gap 4 provenance record)
# ---------------------------------------------------------------------------

def _tree_sha256(skills_dir: Path) -> str:
    """Content hash over the skills tree (sorted relpath + bytes)."""
    digest = hashlib.sha256()
    try:
        for path in sorted(skills_dir.rglob("*")):
            if path.is_file():
                digest.update(str(path.relative_to(skills_dir)).replace("\\", "/").encode())
                digest.update(path.read_bytes())
    except OSError:
        return ""
    return digest.hexdigest()


def register_pack(path: Path, source_url: "str | None" = None,
                  *, force: bool = False) -> dict:
    """Run the full conformance gate, then record the pack in registered.json.

    Returns the written record. Raises ValueError on a non-conformant pack
    (registration is the one deliberately fail-CLOSED door: installing a
    broken pack should fail loudly, not half-register). ``force=True``
    downgrades conformance errors to a skipped gate — structural validity
    is still required.
    """
    root = Path(path).expanduser().resolve()
    manifest, errs = load_manifest(root)
    if manifest is None:
        raise ValueError("; ".join(errs))
    errs = structural_errors(manifest, root)
    if errs:
        raise ValueError(f"pack at {root} failed structural validation: " + "; ".join(errs))

    if not force:
        try:
            from pack.check import check_pack  # lazy — avoids a module cycle
            conformance_errors = [f for f in check_pack(root) if f.level == "error"]
        except Exception as exc:  # noqa: BLE001 — registration is fail-closed
            raise ValueError(
                f"conformance gate could not run ({exc}); refusing to register "
                f"unverified pack (use --force to override)"
            ) from exc
        if conformance_errors:
            rendered = "; ".join(f.render() for f in conformance_errors[:10])
            raise ValueError(
                f"pack at {root} failed conformance ({len(conformance_errors)} "
                f"errors — run `pack check` for the full list; --force to "
                f"register anyway): {rendered}"
            )

    pack = _pack_from_manifest(manifest, root, "registered")
    record = {
        "name": pack.name,
        "vendor": pack.vendor,
        "version": pack.version,
        "path": str(root),
        "source_url": source_url or pack.provenance.get("source", ""),
        "publisher": pack.provenance.get("publisher", ""),
        "manifest_sha256": pack.manifest_sha256,
        "skills_tree_sha256": _tree_sha256(pack.skills_dir),
        "registered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    reg_file = registry_path()
    data = _read_registry_file()
    packs = [p for p in data.get("packs", []) if isinstance(p, dict) and p.get("name") != pack.name]
    packs.append(record)
    reg_file.parent.mkdir(parents=True, exist_ok=True)
    reg_file.write_text(
        json.dumps({"spec": SPEC_VERSION, "packs": packs}, indent=2) + "\n",
        encoding="utf-8",
    )
    return record


def unregister_pack(name: str) -> bool:
    """Remove ``name`` from registered.json. True if it was present."""
    data = _read_registry_file()
    packs = data.get("packs", [])
    kept = [p for p in packs if not (isinstance(p, dict) and p.get("name") == name)]
    if len(kept) == len(packs):
        return False
    reg_file = registry_path()
    reg_file.parent.mkdir(parents=True, exist_ok=True)
    reg_file.write_text(
        json.dumps({"spec": SPEC_VERSION, "packs": kept}, indent=2) + "\n",
        encoding="utf-8",
    )
    return True


def registered_records() -> list:
    return [p for p in _read_registry_file().get("packs", []) if isinstance(p, dict)]


# ---------------------------------------------------------------------------
# Crew-routing + steering views (gaps 2 and 5)
# ---------------------------------------------------------------------------

def specialist_entries(packs: "list | None" = None) -> list:
    """specialist.json-shaped entries contributed by packs.

    Each pack domain that declares a ``specialist`` block yields
    ``{name: "{vendor}-{domain}", role, description, enhances, pack}``.
    Merged by consumers AFTER garden's own specialist.json (first-party
    entries always win a name collision).
    """
    if packs is None:
        packs, _ = discover_packs()
    entries: list = []
    for pack in packs:
        for domain in pack.domains:
            spec = domain.get("specialist")
            if not isinstance(spec, dict):
                continue
            name = pack.specialist_domain(domain.get("name", ""))
            entries.append({
                "name": name,
                "role": spec.get("role", domain.get("name", "")),
                "description": spec.get("description", pack.description),
                "enhances": spec.get("enhances", []),
                "pack": pack.name,
            })
    return entries


def specialist_domains(packs: "list | None" = None) -> list:
    """The crew-facing specialist domain names contributed by packs."""
    return [e["name"] for e in specialist_entries(packs)]


def pack_produces(packs: "list | None" = None) -> list:
    """Produces-contract declarations contributed by packs (gap 5 data layer).

    Shape: ``{pack, domain, archetype, produces: [ids], gate}`` per entry.
    The loom gate consumes a produces id directly (``loom.gate.run_gate``);
    steering attach is the documented seam (docs/extending.md §produces).
    """
    if packs is None:
        packs, _ = discover_packs()
    out: list = []
    for pack in packs:
        for domain in pack.domains:
            for contract in domain.get("produces", []) or []:
                if not isinstance(contract, dict):
                    continue
                out.append({
                    "pack": pack.name,
                    "domain": pack.specialist_domain(domain.get("name", "")),
                    "archetype": contract.get("archetype", ""),
                    "produces": list(contract.get("produces", []) or []),
                    "gate": contract.get("gate", "vault"),
                })
    return out


# ---------------------------------------------------------------------------
# Peer version floors (gap 6 — fail-open probe)
# ---------------------------------------------------------------------------

def _parse_floor(range_str: str) -> "tuple | None":
    m = _FLOOR_RE.match((range_str or "").strip())
    if not m:
        return None
    return int(m.group(2)), int(m.group(3)), int(m.group(4))


def _parse_version(version_str: str) -> "tuple | None":
    m = _SEMVER_RE.match((version_str or "").strip().lstrip("v"))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _garden_version(plugin_root: "Path | None") -> "str | None":
    roots = []
    if plugin_root:
        roots.append(Path(plugin_root))
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        roots.append(Path(env_root))
    roots.append(Path(__file__).resolve().parents[1])
    for root in roots:
        try:
            data = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
            if data.get("version"):
                return str(data["version"])
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    return None


def _probe_binary_version(binary: str) -> "str | None":
    """``<binary> --version`` with a tight timeout. None = unknown."""
    resolved = shutil.which(binary)
    if not resolved:
        return None
    try:
        out = subprocess.run(
            [resolved, "--version"], capture_output=True, text=True,
            timeout=_PROBE_TIMEOUT_S, check=False,
        )
        text = (out.stdout or "") + (out.stderr or "")
        m = re.search(r"(\d+\.\d+\.\d+)", text)
        return m.group(1) if m else None
    except (OSError, subprocess.SubprocessError):
        return None


def check_peer_floors(packs: "list | None" = None, *,
                      plugin_root: "Path | None" = None,
                      probe: bool = True) -> list:
    """Compare each pack's declared peer floors to installed versions.

    Returns a list of finding dicts:
      {pack, peer, floor, installed, status}
    status ∈ ok | below-floor | unknown | bad-range.

    Fail-open by design: only ``below-floor`` (and ``bad-range``) are
    actionable; ``unknown`` means the peer could not be probed and MUST be
    treated as informational, never a block. With ``probe=False`` only the
    zero-subprocess checks run (garden's own version) — the cheap mode for
    SessionStart.
    """
    if packs is None:
        packs, _ = discover_packs()
    findings: list = []

    garden_version = _garden_version(plugin_root)
    probed: dict = {}

    for pack in packs:
        for peer, range_str in sorted((pack.peers or {}).items()):
            floor = _parse_floor(str(range_str))
            if floor is None:
                findings.append({"pack": pack.name, "peer": peer, "floor": str(range_str),
                                 "installed": None, "status": "bad-range"})
                continue

            installed: "str | None"
            if peer == "wicked-garden":
                installed = garden_version
            elif probe:
                if peer not in probed:
                    probed[peer] = _probe_binary_version(peer)
                installed = probed[peer]
            else:
                installed = None

            if installed is None:
                findings.append({"pack": pack.name, "peer": peer, "floor": str(range_str),
                                 "installed": None, "status": "unknown"})
                continue

            parsed = _parse_version(installed)
            status = "unknown" if parsed is None else ("ok" if parsed >= floor else "below-floor")
            findings.append({"pack": pack.name, "peer": peer, "floor": str(range_str),
                             "installed": installed, "status": status})

    return findings


# ---------------------------------------------------------------------------
# CLI — the catalog surface (`pack list`) + registration verbs
# ---------------------------------------------------------------------------

def _cmd_list(as_json: bool) -> int:
    packs, errors = discover_packs()
    if as_json:
        payload = {
            "packs": [{
                "name": p.name, "vendor": p.vendor, "version": p.version,
                "root": str(p.root), "source": p.source,
                "description": p.description,
                "domains": p.domain_names(),
                "specialists": specialist_domains([p]),
                "produces": pack_produces([p]),
                "peers": p.peers,
                "provenance": p.provenance,
                "manifest_sha256": p.manifest_sha256,
            } for p in packs],
            "errors": errors,
            "registered": registered_records(),
        }
        print(json.dumps(payload, indent=2))
        return 0
    if not packs:
        print("no packs discovered")
    for p in packs:
        print(f"{p.name} v{p.version}  [{p.source}]  {p.root}")
        print(f"  domains: {', '.join(p.domain_names())}")
        specs = specialist_domains([p])
        if specs:
            print(f"  crew specialists: {', '.join(specs)}")
        if p.provenance:
            print(f"  provenance: {p.provenance.get('publisher', '?')} "
                  f"<{p.provenance.get('source', 'no source url')}>")
    for err in errors:
        print(f"WARN: {err}", file=sys.stderr)
    return 0


def _cmd_floors(as_json: bool) -> int:
    findings = check_peer_floors()
    if as_json:
        print(json.dumps({"findings": findings}, indent=2))
    else:
        if not findings:
            print("no pack peer floors declared")
        for f in findings:
            print(f"{f['pack']}: {f['peer']} {f['floor']} — installed "
                  f"{f['installed'] or '?'} [{f['status']}]")
    # Fail-open: floors never fail the command; violations are data.
    return 0


def main(argv: "list | None" = None) -> int:
    parser = argparse.ArgumentParser(prog="wicked-garden pack",
                                     description="Third-party pack registry")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="discovered packs (the catalog view)")
    p_list.add_argument("--json", action="store_true")

    p_reg = sub.add_parser("register", help="register a pack directory")
    p_reg.add_argument("path")
    p_reg.add_argument("--source", default=None, help="origin URL (npm/git) for provenance")
    p_reg.add_argument("--force", action="store_true",
                       help="register even when the conformance gate fails (structural validity still required)")

    p_unreg = sub.add_parser("unregister", help="remove a registered pack")
    p_unreg.add_argument("name")

    p_floors = sub.add_parser("floors", help="check declared peer version floors")
    p_floors.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "list":
        return _cmd_list(args.json)
    if args.cmd == "register":
        try:
            record = register_pack(Path(args.path), source_url=args.source,
                                   force=args.force)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(record, indent=2))
        return 0
    if args.cmd == "unregister":
        removed = unregister_pack(args.name)
        print(f"{args.name}: {'unregistered' if removed else 'not registered'}")
        return 0 if removed else 1
    if args.cmd == "floors":
        return _cmd_floors(args.json)
    return 2


if __name__ == "__main__":
    sys.exit(main())
