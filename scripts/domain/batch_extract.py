#!/usr/bin/env python3
"""Bulk rule extraction via the Anthropic Message Batches API (batch rates, 50% off).

Same evidence contract as extract_loop.py — the model boundary changes shape
(one async batch instead of N serial calls), but every returned rule passes the
SAME validate_rule gate and lands through the SAME write path (validated
requirement + business_rule annotation, or RISK floor). Nodes absent from the
results stay unaccounted; the coverage authority re-derives them next pass.

Modes (stdlib only, no SDK):
    prepare  — frame every unaccounted node from the live store, chunk into
               batch requests, write requests JSONL + a manifest with token/cost
               estimates. No key needed.
    submit   — POST the prepared requests as one batch (needs ANTHROPIC_API_KEY).
    poll     — report batch status (request_counts) until ended.
    ingest   — download results, validate every rule, write to the store via the
               harness's write path; print a yield report.

Typical run:
    python3 batch_extract.py prepare --db .codegraph/estate.db --workdir .wicked-batch
    python3 batch_extract.py submit --workdir .wicked-batch
    python3 batch_extract.py poll --workdir .wicked-batch
    python3 batch_extract.py ingest --db .codegraph/estate.db --workdir .wicked-batch
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from domain import _clients, _rule_extractor, extract_loop  # noqa: E402

_API = "https://api.anthropic.com/v1/messages/batches"
_MODEL = os.environ.get("WICKED_RULE_MODEL_API_MODEL", "claude-haiku-4-5-20251001")
_UNITS_PER_REQUEST = 16
# Batch-rate pricing for haiku 4.5 (USD per MTok, 50% of standard).
_BATCH_IN, _BATCH_OUT = 0.50, 2.50


def _headers(key: str) -> dict:
    return {"content-type": "application/json", "x-api-key": key,
            "anthropic-version": "2023-06-01"}


def _api(method: str, url: str, key: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers=_headers(key))
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from e


def _require_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        sys.exit("ANTHROPIC_API_KEY is not set")
    return key


def prepare(db: str, workdir: Path) -> int:
    workdir.mkdir(parents=True, exist_ok=True)
    store = extract_loop._DirectStore(db)
    core = _clients.core_client()
    cov = core.coverage(db, str(workdir / "coverage_snapshot.json"))
    worklist = cov.get("unaccounted_nodes") or []
    if not worklist:
        print("nothing unaccounted — store is fully covered")
        return 0

    # Cluster-order the whole worklist (same structural idea as the loop) so each
    # request holds RELATED symbols.
    node_community = {}
    try:
        clusters = _clients.estate_client(db=db).read_clusters()
        node_community = _clients.total_node_community(clusters, worklist)
    except Exception:
        pass
    worklist.sort(key=lambda n: node_community.get(n["symbol_id"], "~"))

    requests, chars = [], 0
    for i in range(0, len(worklist), _UNITS_PER_REQUEST):
        chunk = worklist[i:i + _UNITS_PER_REQUEST]
        framed = []
        for n in chunk:
            sid = n["symbol_id"]
            framed.append(_rule_extractor.frame_context(
                n, store.source_slice(sid),
                cluster_label=node_community.get(sid),
                neighbor_names=store.blast_neighbors(sid)))
        prompt = _rule_extractor._build_prompt(framed)
        cut = prompt.find("\n--- UNIT 1 ---\n")
        system_part, user_part = (prompt[:cut], prompt[cut:]) if cut > 0 else ("", prompt)
        chars += len(prompt)
        params: dict = {"model": _MODEL, "max_tokens": 8192,
                        "messages": [{"role": "user", "content": user_part}]}
        if system_part:
            params["system"] = [{"type": "text", "text": system_part,
                                 "cache_control": {"type": "ephemeral"}}]
        requests.append({"custom_id": f"req-{i // _UNITS_PER_REQUEST:05d}",
                         "params": params,
                         "_symbol_ids": [n["symbol_id"] for n in chunk]})

    with open(workdir / "requests.jsonl", "w") as f:
        for r in requests:
            f.write(json.dumps(r) + "\n")
    in_tok = chars // 4  # coarse chars→tokens
    out_tok = len(worklist) * 90
    manifest = {
        "db": db, "model": _MODEL, "nodes": len(worklist),
        "requests": len(requests), "units_per_request": _UNITS_PER_REQUEST,
        "est_input_tokens": in_tok, "est_output_tokens": out_tok,
        "est_cost_usd_batch_rates": round(in_tok / 1e6 * _BATCH_IN + out_tok / 1e6 * _BATCH_OUT, 2),
    }
    (workdir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
    return 0


def submit(workdir: Path) -> int:
    key = _require_key()
    reqs = []
    for line in (workdir / "requests.jsonl").read_text().splitlines():
        r = json.loads(line)
        reqs.append({"custom_id": r["custom_id"], "params": r["params"]})
    batch = _api("POST", _API, key, {"requests": reqs})
    (workdir / "batch.json").write_text(json.dumps(batch, indent=2))
    print(f"batch submitted: {batch['id']} status={batch['processing_status']} "
          f"({len(reqs)} requests)")
    return 0


def poll(workdir: Path) -> int:
    key = _require_key()
    bid = json.loads((workdir / "batch.json").read_text())["id"]
    batch = _api("GET", f"{_API}/{bid}", key)
    (workdir / "batch.json").write_text(json.dumps(batch, indent=2))
    print(json.dumps({"id": bid, "status": batch["processing_status"],
                      "counts": batch.get("request_counts")}, indent=2))
    return 0 if batch["processing_status"] == "ended" else 3


def ingest(db: str, workdir: Path) -> int:
    key = _require_key()
    batch = json.loads((workdir / "batch.json").read_text())
    if batch["processing_status"] != "ended":
        sys.exit(f"batch not ended (status={batch['processing_status']}) — poll first")
    url = batch["results_url"]
    req = urllib.request.Request(url, headers=_headers(key))
    with urllib.request.urlopen(req, timeout=600) as resp:
        results_text = resp.read().decode()
    (workdir / "results.jsonl").write_text(results_text)

    ids_by_custom = {}
    for line in (workdir / "requests.jsonl").read_text().splitlines():
        r = json.loads(line)
        ids_by_custom[r["custom_id"]] = set(r["_symbol_ids"])

    estate = _clients.estate_client(db=db)
    store = extract_loop._DirectStore(db)
    ok = floored = kept = errored = 0
    for line in results_text.splitlines():
        res = json.loads(line)
        cid = res["custom_id"]
        batch_ids = ids_by_custom.get(cid, set())
        result = res.get("result") or {}
        if result.get("type") != "succeeded":
            errored += len(batch_ids)  # untouched — stays unaccounted for a retry pass
            continue
        msg = result["message"]
        text = "".join(b.get("text", "") for b in msg.get("content", [])
                       if isinstance(b, dict) and b.get("type") == "text")
        try:
            rules = _rule_extractor._extract_json_array(text)
        except Exception:
            errored += len(batch_ids)
            continue
        by_id = {r["symbol_id"]: r for r in rules
                 if isinstance(r, dict) and r.get("symbol_id") in batch_ids}
        for sid in batch_ids:
            rule = by_id.get(sid)
            valid, reason = (_rule_extractor.validate_rule(rule, batch_ids) if rule
                             else (False, "no rule returned for this node"))
            name = sid.rsplit("/", 1)[-1]
            if valid and float(rule["confidence"]) >= extract_loop.RESOLVE_THRESHOLD:
                extract_loop._write_node(estate, sid, name, rule, True, "")
                ok += 1
            elif rule and (rule.get("statement") or "").strip():
                extract_loop._write_node(estate, sid, name, rule, False,
                                         reason if not valid else "below confidence threshold")
                floored += 1
            elif extract_loop._has_statement(store, sid):
                kept += 1  # statement-less miss over existing content — keep it (monotonic)
            else:
                extract_loop._write_node(estate, sid, name, rule, False, reason)
                floored += 1
    print(json.dumps({"validated": ok, "risk_floored": floored, "kept_existing": kept,
                      "errored_left_unaccounted": errored}, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=["prepare", "submit", "poll", "ingest"])
    ap.add_argument("--db", default=os.environ.get("WICKED_ESTATE_DB"))
    ap.add_argument("--workdir", default=".wicked-batch")
    args = ap.parse_args()
    wd = Path(args.workdir)
    if args.mode == "prepare":
        return prepare(args.db, wd)
    if args.mode == "submit":
        return submit(wd)
    if args.mode == "poll":
        return poll(wd)
    return ingest(args.db, wd)


if __name__ == "__main__":
    sys.exit(main())
