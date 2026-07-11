#!/usr/bin/env python3
"""pre_push.py — the claim sentinel's local pre-push gate (layer 1 of 3).

Reads git's pre-push stdin ("<local_ref> <local_sha> <remote_ref> <remote_sha>"
per line) and BLOCKS (exit 1) when a *publish-shaped* ref — the remote default
branch or any tag — is being pushed with no re-derived verdict covering the
pushed sha on the sentinel ledger. Feature-branch pushes always pass: the claim
moment is publishing "done", not sharing work-in-progress.

Layers (see scripts/sentinel/invariants.py):
  1. this hook            — local, fires for ANY tool that pushes through git
  2. required CI check    — server-side, catches gh-pr-merge/web/API paths
  3. harness ref-watch    — detects + records what slipped past both

Override: `git push --no-verify` (git's own explicit skip — visible, and the
server layer still gates). Fail-open on machinery errors: a broken sentinel
must never brick pushes; only a *present ledger with no verdict* blocks.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from invariants import log_sentinel_event, repo_toplevel, verdict_for  # noqa: E402

_ZERO_SHA = "0" * 40
_DEFAULT_BRANCH_REFS = ("refs/heads/main", "refs/heads/master")


def _publish_shaped(remote_ref: str) -> bool:
    return remote_ref in _DEFAULT_BRANCH_REFS or remote_ref.startswith("refs/tags/")


def main() -> int:
    try:
        repo = repo_toplevel()
        if repo is None:
            return 0  # not a repo — nothing to gate
        blocked = []
        for line in sys.stdin.read().splitlines():
            parts = line.split()
            if len(parts) != 4:
                continue
            _local_ref, local_sha, remote_ref, _remote_sha = parts
            if local_sha == _ZERO_SHA:  # deletion — not a done-claim
                continue
            if not _publish_shaped(remote_ref):
                continue
            if verdict_for(repo, local_sha) is None:
                blocked.append((remote_ref, local_sha))
        if not blocked:
            return 0
        for remote_ref, sha in blocked:
            print(
                f"[Sentinel:done-claim-verdict] pushing {remote_ref} @ {sha[:9]} "
                "with no re-derived verdict on record.\n"
                "→ Invoke the `wicked-garden-prove` skill (stamps the ledger via the gate), "
                "or override deliberately with `git push --no-verify` — the server "
                "gate still applies.",
                file=sys.stderr,
            )
            log_sentinel_event(repo, "prepush_blocked",
                               {"ref": remote_ref, "sha": sha,
                                "invariant": "done-claim-verdict"})
        return 1
    except Exception:  # noqa: BLE001 — machinery failure must not brick pushes
        return 0


if __name__ == "__main__":
    sys.exit(main())
