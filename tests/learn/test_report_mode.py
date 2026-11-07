"""learn's report mode (the `sourced-report` workflow, DES-CATALOG-002 rev 8 §2.d piece 1): the floor
(scripts/learn/report_check.py) and the skill text the six cards' seats read."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LEARN = REPO / "skills" / "learn"
SCRIPT = REPO / "scripts" / "learn" / "report_check.py"
_spec = importlib.util.spec_from_file_location("learn_report_check", SCRIPT)
rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc)

NOW = datetime(2026, 11, 6, 22, 0, tzinfo=timezone.utc)
QUOTE = "Acceptance is deemed after 10 business days."
URL = "https://example.org/terms"


def records(tmp_path: Path) -> Path:
    d = tmp_path / "records"
    d.mkdir(exist_ok=True)
    (d / "sow.pdf").write_bytes(b"%PDF-1.7 binary")
    (d / "sow.txt").write_text(f"Section 4\n{QUOTE.replace(' after', chr(10) + 'after')}\n", encoding="utf-8")
    (d / "msa.md").write_text("Liability is capped at fees paid in the prior 12 months.\n", encoding="utf-8")
    (d / "MANIFEST.json").write_text("{}", encoding="utf-8")
    return d


def packet(**over) -> dict:
    p = {
        "schema": 1,
        "lens": "due-diligence",
        "question": "Is the SOW complete enough to sign?",
        "documents": ["sow.pdf", "msa.md"],
        "web": {"state": "used"},
        "sources": [
            {"id": "S1", "file": "sow.pdf", "page": 4, "quote": QUOTE},
            {"id": "S2", "file": "msa.md", "quote": "Liability is capped at fees paid in the prior 12 months."},
            {"id": "S3", "url": URL, "title": "Example terms", "observed_at": "2026-11-06T21:40:12Z"},
            {"id": "S4", "source": "support-pg", "tool": "query", "args": {"sql": "select count(*) from tickets"},
             "observed_at": "2026-11-06T21:41:03Z"},
        ],
        "claims": [
            {"id": "C1", "text": "The SOW deems acceptance after 10 business days.", "sources": ["S1"]},
            {"id": "C2", "text": "Liability is capped at a year of fees.", "sources": ["S2", "S3"]},
            {"id": "C3", "text": "Support logged 14 open tickets last quarter.", "sources": ["S4"]},
        ],
        "stopped": None,
        "report": f"Acceptance is deemed [C1]. Capped [C2, C3], see {URL}#terms.\n\n## Sources\n- S1\n",
    }
    p.update(over)
    return p


def rules(out: dict) -> set[str]:
    return {f["rule"] for f in out["findings"]}


@pytest.fixture(autouse=True)
def _records(tmp_path, monkeypatch):
    """Every check runs against a staged documents folder unless a test passes its own."""
    monkeypatch.setattr(sys.modules[__name__], "RECS", records(tmp_path))


RECS: Path | None = None
NO_RECORDS = object()


def run_check(p: dict, recs=None, **kw) -> tuple[int, dict]:
    recs = None if recs is NO_RECORDS else (recs or RECS)
    return rc.check(p, recs, now=NOW, **kw)


# --- preflight: a documents-required card refuses without documents ------------------------------

@pytest.mark.parametrize("lens", ["due-diligence", "analyze"])
def test_a_documents_required_lens_refuses_with_none_staged(tmp_path, lens):
    code, out = rc.preflight(lens, tmp_path / "none")  # no folder at all
    assert code == 3 and not out["ok"] and "needs documents" in out["reason"]
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "MANIFEST.json").write_text("{}", encoding="utf-8")  # the manifest is not a document
    (empty / ".hidden").write_text("x", encoding="utf-8")
    assert rc.preflight(lens, empty)[0] == 3


@pytest.mark.parametrize("lens", ["research", "competitive", "critique", "estimate"])
def test_lenses_that_do_not_require_documents_go_on_without_them(tmp_path, lens):
    code, out = rc.preflight(lens, None)
    assert code == 0 and out["documents"] == []


def test_preflight_counts_a_pdf_and_its_text_derivative_as_one_document(tmp_path):
    code, out = rc.preflight("analyze", records(tmp_path))
    assert code == 0 and out["documents"] == ["msa.md", "sow.pdf"]
    assert rc.preflight("vibes", None)[0] == 2


def test_the_documents_rule_is_r5s_ruling():
    assert {k for k, v in rc.LENSES.items() if v == "required"} == {"due-diligence", "analyze"}
    assert {k for k, v in rc.LENSES.items() if v == "optional"} == {"critique", "estimate"}
    assert {k for k, v in rc.LENSES.items() if v == "not-taken"} == {"research", "competitive"}


# --- check: the floor ----------------------------------------------------------------------------

def test_a_well_formed_packet_passes(tmp_path):
    code, out = run_check(packet(), records(tmp_path))
    assert (code, out["findings"]) == (0, [])
    assert out["counts"] == {"sources": 4, "web": 1, "file": 2, "code": 0, "tool": 1, "claims": 3}


@pytest.mark.parametrize("sources", [[], None, "missing"])
def test_a_claim_without_a_source_fails(sources):
    p = packet()
    if sources == "missing":
        del p["claims"][0]["sources"]
    else:
        p["claims"][0]["sources"] = sources
    code, out = run_check(p)
    assert code == 1 and "claim-unsourced" in rules(out)


def test_a_claim_citing_a_source_the_log_does_not_hold_fails():
    p = packet()
    p["claims"][1]["sources"] = ["S2", "S9"]
    assert "claim-unknown-source" in rules(run_check(p)[1])


@pytest.mark.parametrize("where", ["report", "claim"])
def test_a_cited_url_must_appear_in_the_source_log(where):
    p = packet()
    stray = "https://never-fetched.example.com/page"
    if where == "report":
        p["report"] += f"\nMore at {stray}."
    else:
        p["claims"][2]["text"] += f" ({stray})"
    code, out = run_check(p)
    assert code == 1
    hits = [f for f in out["findings"] if f["rule"] == "url-not-in-log"]
    assert len(hits) == 1 and stray in hits[0]["message"]


def test_a_logged_url_matches_with_a_fragment_or_inside_a_markdown_link():
    p = packet(report=f"[terms]({URL}) and <{URL}#x>, ({URL}). [C1] [C2] [C3]")
    assert run_check(p)[0] == 0


def test_a_trailing_slash_is_a_different_page():
    p = packet(report=f"[C1] [C2] [C3] {URL}/")
    assert "url-not-in-log" in rules(run_check(p)[1])


def test_parentheses_inside_a_url_are_kept():
    wiki = "https://en.wikipedia.org/wiki/Complexity_(computer_science)"
    p = packet(report=f"See [the article]({wiki}) and ({wiki}). [C1] [C2] [C3]")
    p["sources"][2]["url"] = wiki
    assert run_check(p)[0] == 0
    p["report"] = "See https://en.wikipedia.org/wiki/Complexity. [C1] [C2] [C3]"
    assert "url-not-in-log" in rules(run_check(p)[1])


def test_web_sources_when_the_web_was_not_available_fail():
    for state in ("not-picked", "unavailable"):
        p = packet(web={"state": state, "reason": "the job did not pick the web"})
        assert "web-not-available" in rules(run_check(p)[1]), state


def test_a_web_state_other_than_used_needs_its_reason():
    p = packet(web={"state": "unavailable"})
    assert "web-state" in rules(run_check(p)[1])
    assert "web-state" in rules(run_check(packet(web=None))[1])


def test_a_documents_required_lens_reporting_without_documents_fails_but_its_stop_passes(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    web = dict(packet()["sources"][2], id="S1")
    p = packet(documents=[], sources=[web], claims=[{"id": "C1", "text": "Terms.", "sources": ["S1"]}],
               report=f"Terms [C1]. {URL}")
    assert "documents-required" in rules(run_check(p, empty)[1])
    stop = packet(documents=[], sources=[], claims=[], report="",
                  stopped="Due diligence needs documents and none were staged for this job.")
    code, out = run_check(stop, empty)
    assert code == 0 and out["stopped"]


def test_a_stop_is_refused_while_documents_are_staged():
    stop = packet(documents=[], sources=[], claims=[], report="", stopped="the documents could not be read")
    assert rules(run_check(stop)[1]) == {"stopped-with-documents"}


def test_a_stop_delivers_its_reason_not_a_report(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    stop = packet(documents=[], sources=[], claims=[], stopped="No sources",
                  report="The vendor is certified, safe, and costs $10.")
    assert rules(run_check(stop, empty)[1]) == {"stopped-with-report"}


def test_a_stop_carries_no_claims_and_an_empty_report_says_why():
    assert "stopped-with-claims" in rules(run_check(packet(stopped="no sources"))[1])
    out = run_check(packet(claims=[], report=""))[1]
    assert {"report-no-claims", "report-empty"} <= rules(out)


def test_a_quote_that_is_not_in_its_file_fails(tmp_path):
    p = packet()
    p["sources"][1]["quote"] = "Liability is unlimited."
    code, out = run_check(p, records(tmp_path))
    assert code == 1 and rules(out) == {"quote-not-found"}


def test_a_pdf_without_text_is_unchecked_not_failed(tmp_path):
    recs = records(tmp_path)
    (recs / "sow.txt").unlink()
    code, out = run_check(packet(), recs)
    assert code == 0 and [u["file"] for u in out["unchecked"]] == ["sow.pdf"]


def test_file_sources_must_be_staged_and_stay_inside_the_records(tmp_path):
    recs = records(tmp_path)
    p = packet()
    p["sources"][1]["file"] = "other.md"
    assert "file-not-staged" in rules(run_check(p)[1])
    p = packet(documents=["sow.pdf", "msa.md", "gone.md"])
    assert "file-missing" in rules(run_check(p, recs)[1])
    p = packet()
    p["sources"][1]["file"] = "../secrets.md"
    assert "source-file" in rules(run_check(p, recs)[1])


def test_report_citations_are_checked_both_ways():
    out = run_check(packet(report=f"[C1] [C2] [C7] {URL}"))[1]
    assert {"report-unknown-claim", "report-uncited-claim"} <= rules(out)


@pytest.mark.parametrize("at, rule", [("2026-11-07T22:00:00Z", "source-observed-at"),
                                      ("yesterday", "source-observed-at"),
                                      ("2026-11-06T21:00:00", "source-observed-at")])
def test_observed_at_is_a_utc_time_not_in_the_future(at, rule):
    p = packet()
    p["sources"][2]["observed_at"] = at
    assert rule in rules(run_check(p)[1])


@pytest.mark.parametrize("mutate, rule", [
    (lambda p: p["sources"].append({"id": "S1", "url": URL, "title": "t", "observed_at": "2026-11-06T21:00:00Z"}),
     "source-duplicate"),
    (lambda p: p["sources"].append({"id": "S5", "url": URL, "file": "msa.md", "quote": "q"}), "source-kind"),
    (lambda p: p["sources"].append({"id": "x", "url": URL, "title": "t", "observed_at": "2026-11-06T21:00:00Z"}),
     "source-id"),
    (lambda p: p["sources"][2].update(url="ftp://example.org/x"), "source-url"),
    (lambda p: p["sources"][2].update(title=""), "source-title"),
    (lambda p: p["sources"][0].update(quote=""), "source-quote"),
    (lambda p: p["sources"][0].update(page=0), "source-page"),
    (lambda p: p["sources"][3].update(tool=""), "source-tool"),
    (lambda p: p["claims"].append({"id": "C1", "text": "dup", "sources": ["S1"]}), "claim-duplicate"),
    (lambda p: p["claims"][0].update(text=""), "claim-text"),
    (lambda p: p.update(schema=2), "packet-schema"),
    (lambda p: p.update(lens="vibes"), "lens"),
    (lambda p: p.update(documents="sow.pdf"), "documents"),
])
def test_each_shape_rule_refuses(mutate, rule):
    p = copy.deepcopy(packet())
    mutate(p)
    assert rule in rules(run_check(p)[1])


def test_a_pasted_claim_is_quoted_from_the_brief():
    brief_src = {"id": "S1", "file": "brief", "quote": "remote work raises output"}
    p = packet(lens="critique", documents=[], web={"state": "not-picked", "reason": "not picked"},
               brief="Critique this: remote work raises output by 13%.", sources=[brief_src],
               claims=[{"id": "C1", "text": "The claim says remote work raises output.", "sources": ["S1"]}],
               report="It says so [C1].")
    assert run_check(p)[0] == 0
    p["sources"][0]["quote"] = "remote work halves output"
    assert rules(run_check(p)[1]) == {"quote-not-found"}


def test_the_cli_exit_codes(tmp_path):
    recs = records(tmp_path)

    def cli(*args, stdin=None):
        r = subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin, capture_output=True, text=True)
        return r.returncode, r.stdout

    good = packet()
    assert cli("check", "--packet", "-", "--records", str(recs), stdin=json.dumps(good))[0] == 0
    bad = packet()
    bad["claims"][0]["sources"] = []
    code, out = cli("check", "--packet", "-", stdin=json.dumps(bad))
    assert code == 1 and "claim-unsourced" in out
    assert cli("check", "--packet", "-", stdin="not json")[0] == 2
    assert cli("check", "--packet", str(tmp_path / "none.json"))[0] == 2
    code, out = cli("preflight", "--lens", "due-diligence", "--records", str(tmp_path / "nope"))
    assert code == 3 and json.loads(out)["reason"].startswith("Due diligence needs documents")


# --- review folds (codex + pi, r1) ---------------------------------------------------------------

def test_documents_named_without_records_to_check_them_fail():
    p = packet(documents=["never-staged.md"])
    p["sources"][1]["file"] = "never-staged.md"
    p["sources"][1]["quote"] = "Invented text that no document holds."
    p["sources"] = p["sources"][1:]
    assert "records-missing" in rules(run_check(p, NO_RECORDS)[1])
    r = subprocess.run([sys.executable, str(SCRIPT), "check", "--packet", "-"], input=json.dumps(p),
                       capture_output=True, text=True)
    assert r.returncode == 1 and "records-missing" in r.stdout


@pytest.mark.parametrize("derivative", ["sow.txt", "sow.pdf.txt"])
def test_a_pdf_derivative_symlinked_outside_the_records_is_not_read(tmp_path, derivative):
    recs = tmp_path / "recs"
    recs.mkdir()
    (recs / "sow.pdf").write_bytes(b"%PDF")
    outside = tmp_path / "outside.txt"
    outside.write_text(f"{QUOTE}\n", encoding="utf-8")
    (recs / derivative).symlink_to(outside)
    p = packet(documents=["sow.pdf"], sources=[packet()["sources"][0]],
               claims=[{"id": "C1", "text": "Deemed acceptance.", "sources": ["S1"]}], report="Deemed [C1].")
    code, out = run_check(p, recs)
    assert code == 0 and "outside" in out["unchecked"][0]["why"]


def test_a_staged_file_symlinked_outside_the_records_is_refused(tmp_path):
    recs = records(tmp_path)
    outside = tmp_path / "secret.md"
    outside.write_text("Liability is capped at fees paid in the prior 12 months.\n", encoding="utf-8")
    (recs / "msa.md").unlink()
    (recs / "msa.md").symlink_to(outside)
    assert "file-outside-records" in rules(run_check(packet(), recs)[1])


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(lens=[]), lambda p: p.update(lens={}), lambda p: p.update(web={"state": []}),
    lambda p: p["claims"][0].update(id="C" + "1" * 5000), lambda p: p["sources"][0].update(id="S" + "1" * 5000),
    lambda p: p["claims"][0].update(sources=[["S1"], {"a": 1}]), lambda p: p.update(report=["x"]),
    lambda p: p["claims"].append("not an object"), lambda p: p["sources"][3].update(args=None),
])
def test_malformed_packets_give_findings_not_tracebacks(mutate):
    p = packet()
    mutate(p)
    code, out = run_check(p)
    assert code == 1 and out["findings"]


def test_the_cli_reports_an_unreadable_packet_as_json():
    deep = "[" * 100000 + "]" * 100000
    r = subprocess.run([sys.executable, str(SCRIPT), "check", "--packet", "-"], input=deep, capture_output=True, text=True)
    assert r.returncode == 2 and json.loads(r.stdout)["ok"] is False


@pytest.mark.parametrize("quote", ["\u00ad", "\u00ad\u00ad   ", "10 days"])
def test_a_quote_too_short_to_locate_fails(quote):
    p = packet()
    p["sources"][0]["quote"] = quote
    assert "source-quote" in rules(run_check(p)[1])
    brief = packet(lens="critique", documents=[], sources=[{"id": "S1", "file": "brief", "quote": quote}],
                   web={"state": "not-picked", "reason": "r"}, claims=[{"id": "C1", "text": "x", "sources": ["S1"]}],
                   report="x [C1]")
    assert "source-quote" in rules(run_check(brief, NO_RECORDS)[1])


def test_the_web_source_cannot_be_dressed_as_a_tool_and_tools_carry_their_args():
    p = packet(web={"state": "not-picked", "reason": "not picked"})
    p["sources"][2] = {"id": "S3", "source": "web", "tool": "fetch", "args": {"url": URL},
                       "observed_at": "2026-11-06T21:40:12Z"}
    p["report"] = p["report"].replace(f"see {URL}#terms.", "")
    assert rules(run_check(p)[1]) == {"web-as-tool"}
    p = packet()
    del p["sources"][3]["args"]
    assert rules(run_check(p)[1]) == {"source-args"}


def test_a_document_quoted_many_times_is_read_once(monkeypatch):
    calls = []
    real = rc.Texts._read
    monkeypatch.setattr(rc.Texts, "_read", staticmethod(lambda path, root, code=False, budget=rc.TEXT_BUDGET_BYTES: calls.append(path) or real(path, root, code, budget)))
    p = packet()
    p["sources"] += [dict(p["sources"][1], id=f"S{n}") for n in range(5, 50)]
    run_check(p)
    assert len(calls) == len(set(calls)) == 2


def test_a_quote_missing_from_a_pdf_text_is_its_own_rule():
    p = packet()
    p["sources"][0]["quote"] = "Acceptance requires a signed test report."
    assert rules(run_check(p)[1]) == {"quote-not-found-in-pdf-text"}


def test_code_sources_are_checked_in_the_repository(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("def handler():\n    return retry(times=3)\n", encoding="utf-8")
    code_src = {"id": "S5", "path": "src/app.py", "line": 2, "quote": "return retry(times=3)"}
    p = packet()
    p["sources"].append(code_src)
    p["claims"].append({"id": "C4", "text": "The handler retries three times.", "sources": ["S5"]})
    p["report"] += " Retries [C4]."
    assert run_check(p, repo=repo)[0] == 0
    assert "repo-missing" in rules(run_check(p)[1])
    code_src["quote"] = "return retry(times=9)"
    assert "quote-not-found" in rules(run_check(p, repo=repo)[1])
    code_src.update(path="../records/msa.md", quote="Liability is capped")
    assert "source-path" in rules(run_check(p, repo=repo)[1])
    (repo / "link.md").symlink_to(RECS / "msa.md")
    code_src.update(path="link.md")
    assert "path-outside-repo" in rules(run_check(p, repo=repo)[1])


def test_unchecked_files_say_why():
    (RECS / "scan.png").write_bytes(b"\x89PNG")
    (RECS / "blank.md").write_text("   \n", encoding="utf-8")
    p = packet(documents=["sow.pdf", "msa.md", "scan.png", "blank.md"])
    p["sources"] += [{"id": "S5", "file": "scan.png", "quote": "a figure in the scan"},
                     {"id": "S6", "file": "blank.md", "quote": "a line that is not there"}]
    p["claims"][0]["sources"] += ["S5", "S6"]
    code, out = run_check(p)
    assert code == 0
    why = {u["file"]: u["why"] for u in out["unchecked"]}
    assert "not a text format" in why["scan.png"] and "empty" in why["blank.md"]


@pytest.mark.parametrize("at", [None, "2026-11-06T21:40Z", "2026-11-06T21:40:12.Z"])
def test_observed_at_needs_seconds_and_may_not_be_missing(at):
    p = packet()
    if at is None:
        del p["sources"][2]["observed_at"]
    else:
        p["sources"][2]["observed_at"] = at
    assert "source-observed-at" in rules(run_check(p)[1])


# --- review folds (codex + pi, r2) ---------------------------------------------------------------

@pytest.mark.parametrize("cite, unknown", [("[C1000000]", ["C1000000"]), ("[C2, C1000000]", ["C1000000"]),
                                           ("[C9, C1000000000000000000000000]", ["C9", "C1" + "0" * 14])])
def test_a_citation_of_any_length_is_checked(cite, unknown):
    p = packet()
    p["report"] += f" An invented assertion {cite}."
    out = run_check(p)[1]
    got = [f["message"].split("[")[1].split("]")[0] for f in out["findings"] if f["rule"] == "report-unknown-claim"]
    assert got == unknown


def test_a_markdown_destination_is_taken_exactly():
    p = packet(report=f"[details]({URL}!) [C1] [C2] [C3]")
    assert "url-not-in-log" in rules(run_check(p)[1])
    p = packet(report=f"[details]({URL}!) and <{URL}!> [C1] [C2] [C3]")
    p["sources"][2]["url"] = URL + "!"
    assert run_check(p)[0] == 0
    p = packet(report=f"Read it at {URL}! Or _{URL}_ and *{URL}*. [C1] [C2] [C3]")
    assert run_check(p)[0] == 0


def test_a_long_run_of_closing_parentheses_is_linear():
    import time
    p = packet(report=f"[C1] [C2] [C3] {URL}" + ")" * 400000)
    t = time.monotonic()
    code, _ = run_check(p)
    assert code == 0 and time.monotonic() - t < 3


def test_text_read_by_one_check_is_budgeted(monkeypatch):
    monkeypatch.setattr(rc, "TEXT_BUDGET_BYTES", 80)
    code, out = run_check(packet())
    assert code == 0 and any("already read" in u["why"] for u in out["unchecked"])


def test_a_stop_is_judged_on_what_is_readable(tmp_path):
    recs = tmp_path / "zero"
    recs.mkdir()
    (recs / "empty.md").write_text("", encoding="utf-8")
    stop = packet(documents=[], sources=[], claims=[], report="", stopped="the one document is empty")
    assert run_check(stop, recs)[0] == 0
    with_code = dict(stop, sources=[{"id": "S1", "path": "src/a.py", "line": 1, "quote": "x = 1"}])
    assert "stopped-with-documents" in rules(run_check(with_code, recs)[1])
    with_brief = dict(stop, brief="Critique this: remote work raises output by 13%.")
    assert "stopped-with-documents" in rules(run_check(with_brief, recs)[1])


@pytest.mark.parametrize("args, ok", [({}, True), ([], True), (["--since", "2026-07-01"], True), ("q", True),
                                      (None, False), ("  ", False), ("missing", False)])
def test_tool_args_may_be_empty_but_not_missing(args, ok):
    p = packet()
    if args == "missing":
        del p["sources"][3]["args"]
    else:
        p["sources"][3]["args"] = args
    assert (run_check(p)[0] == 0) is ok


@pytest.mark.parametrize("at", ["2026-11-06T21:40:12.1Z", "2026-11-06T21:40:12.123456789Z", "2026-11-06T21:40:12+00:00"])
def test_fractional_seconds_of_any_precision_pass(at):
    p = packet()
    p["sources"][2]["observed_at"] = at
    assert run_check(p)[0] == 0


def test_a_short_code_quote_is_checked_on_its_line(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    p = packet()
    p["sources"].append({"id": "S5", "path": "a.py", "line": 1, "quote": "x = 1"})
    p["claims"].append({"id": "C4", "text": "x starts at one.", "sources": ["S5"]})
    p["report"] += " [C4]"
    assert run_check(p, repo=repo)[0] == 0
    p["sources"][-1]["line"] = 2
    assert "quote-not-found" in rules(run_check(p, repo=repo)[1])
    del p["sources"][-1]["line"]
    assert "source-quote" in rules(run_check(p, repo=repo)[1])


# --- review folds (codex r3) ---------------------------------------------------------------------

def test_nested_markdown_prefixes_are_scanned_once():
    import time
    n = 8000
    p = packet(report="[C1] [C2] [C3] " + "](https://a" * n + ")" * n)
    t = time.monotonic()
    run_check(p)
    assert time.monotonic() - t < 3


def test_a_located_code_quote_reads_its_file_once(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    reads = []
    real = Path.read_text
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: reads.append(self.name) or real(self, *a, **k))
    p = packet()
    for n in range(5, 25):
        p["sources"].append({"id": f"S{n}", "path": "a.py", "line": 1, "quote": "x = 1"})
    p["claims"].append({"id": "C4", "text": "x starts at one.", "sources": [f"S{n}" for n in range(5, 25)]})
    p["report"] += " [C4]"
    assert run_check(p, repo=repo)[0] == 0
    assert reads.count("a.py") == 1


@pytest.mark.parametrize("suffix", ["_", "*"])
def test_an_unopened_trailing_emphasis_mark_is_part_of_the_url(suffix):
    p = packet(report=f"[C1] [C2] [C3] {URL}{suffix} here")
    assert "url-not-in-log" in rules(run_check(p)[1])
    p["sources"][2]["url"] = URL + suffix
    assert run_check(p)[0] == 0


def test_a_stop_sees_a_pdfs_text_derivative(tmp_path):
    recs = tmp_path / "pdf"
    recs.mkdir()
    (recs / "sow.pdf").write_bytes(b"")
    (recs / "sow.txt").write_text("Acceptance is deemed after 10 business days.\n", encoding="utf-8")
    stop = packet(lens="analyze", documents=["sow.pdf"], sources=[], claims=[], report="",
                  stopped="the document is empty")
    assert "stopped-with-documents" in rules(run_check(stop, recs)[1])
    (recs / "sow.txt").write_text("", encoding="utf-8")
    assert run_check(stop, recs)[0] == 0


def test_an_angle_bracket_destination_keeps_its_parentheses():
    p = packet(report=f"[details](<{URL})>) [C1] [C2] [C3]")
    p["sources"][2]["url"] = URL + ")"
    assert run_check(p)[0] == 0


# --- the skill text -----------------------------------------------------------------------------

def _skill() -> str:
    return (LEARN / "SKILL.md").read_text(encoding="utf-8")


def test_every_lens_line_maps_to_its_ref_and_documents_rule():
    rows = re.findall(r"^\| `Lens: ([a-z-]+)\.` \| (refs/report-[a-z-]+\.md) \| ([a-z -]+) \|$", _skill(), re.M)
    assert {lens: rule.strip().replace(" ", "-") for lens, _, rule in rows} == rc.LENSES
    for lens, ref, rule in rows:
        text = (LEARN / ref).read_text(encoding="utf-8")
        assert ref == f"refs/report-{lens}.md"
        assert f"**Brief line:** `Lens: {lens}.`" in text
        assert re.search(r"\*\*Documents:\*\*\s+" + re.escape(rule.strip()), text), ref


def test_report_mode_states_the_web_and_stop_rules():
    s = _skill()
    for needle in ("`not-picked`", "`unavailable`", "Never use curl", "Never answer from memory",
                   "report_check.py preflight", "report_check.py check", "refs/report-check.md"):
        assert needle in s, needle
    check = (LEARN / "refs" / "report-check.md").read_text(encoding="utf-8")
    for needle in ("report_check.py check", "VERDICT: PASS", "VERDICT: FAIL", "did not gather",
                   "Did not hold at the check", "unverified"):
        assert needle in check, needle
    claims = (LEARN / "refs" / "report-claims.md").read_text(encoding="utf-8")
    # The one floor finding a seat may clear by reading the original is named the same everywhere.
    for text in (claims, check, SCRIPT.read_text(encoding="utf-8")):
        assert "quote-not-found-in-pdf-text" in text
    for needle in ("receipt", "`args`", "fetched_at"):
        assert needle in check and needle in claims, needle
