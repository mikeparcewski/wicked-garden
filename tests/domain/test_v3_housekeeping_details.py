"""garden#1599 (DES-1599): a DETAIL the prose writer marks housekeeping leaves its business group for its area's
housekeeping group, shown or withheld; 0 real model calls (scripted writer and checker)."""
import json

from domain import model_calls, prose, run, store


def st(sid, file, lines, text):
    return dict(id=sid, status="Checked", kind="rule", name="P", anchor=dict(file=file, lines=lines),
                claims=[dict(i=0, type="condition", text=text, lines=[f"{file}:{lines[0]}"]),
                        dict(i=1, type="effect", text="move `'Y'` to `WS-DONE`", when=[0], lines=[f"{file}:{lines[1]}"])])


STATEMENTS = [st("a#0", "app/cbl/A.cbl", [10, 12], "`PAY-HOURS > 40`"),
              st("a#1", "app/cbl/A.cbl", [20, 22], "`FILE-STATUS = '00'`"),
              st("a#2", "app/cbl/A.cbl", [30, 32], "`FILE-STATUS = '23'`"),
              st("b#0", "app/cbl/B.cbl", [5, 6], "`AMT > 0`"),
              st("b#1", "app/cbl/B.cbl", [8, 9], "`OPEN-STATUS = '00'`")]


def scripted(monkeypatch, groups, flag=()):
    """The writer answers ``groups``; the checker supports every sentence except the ids in ``flag``, and the repair
    withholds those."""
    def claude(step, cid, prompt, timeout=1500, role=None):
        if step == "prose":
            return json.dumps({"groups": groups}), 0
        return json.dumps({"repairs": [{"id": i, "text": "WITHHOLD", "cites": []} for i in flag]}), 0

    def codex(step, cid, prompt, timeout=1500, role=None):
        ids = [ln[1:ln.index("]")] for ln in prompt.split("\n") if ln.startswith("[g")]
        return json.dumps({"verdicts": [{"id": i, "verdict": "OVERREACH" if i in flag else "SUPPORTED", "case": "SCOPE",
                                         "reason": "x"} for i in ids]}), 0
    monkeypatch.setattr(model_calls, "claude", claude)
    monkeypatch.setattr(model_calls, "codex", codex)


def g(n, area, kind, rule, details):
    return dict(g=n, title=f"T{n}", area=area, kind=kind, rule=dict(text=rule[0], cites=rule[1]),
                details=[dict(text=t, cites=c, **({"kind": k} if k else {})) for t, c, k in details])


def by_g(res):
    return {x["g"]: x for x in res["groups"]}


def test_a_housekeeping_detail_moves_to_its_areas_housekeeping_group(monkeypatch):
    scripted(monkeypatch, [g(1, "A", "business", ("Hours over 40 are overtime.", ["S1"]),
                             [("`PAY-HOURS` over 40", ["S1"], "business"), ("Status `'00'` is accepted", ["S2"], "housekeeping")]),
                           g(2, "A", "housekeeping", ("A's files are checked.", ["S3"]), [])])
    res = prose.prose_all(STATEMENTS[:3], "demo")
    gs = by_g(res)
    assert [d["id"] for d in gs[1]["details"]] == ["g1.d1"]
    assert [(d["id"], d["text"], d["cites"]) for d in gs[2]["details"]] == [("g1.d2", "Status `'00'` is accepted", ["S2"])]
    assert res["uncited"] == [] and res["counts"]["moved_housekeeping"] == 1


def test_an_area_with_no_housekeeping_group_gets_one_after_every_group(monkeypatch):
    scripted(monkeypatch, [g(1, "B", "business", ("Positive amounts post.", ["S1"]),
                             [("`OPEN-STATUS` `'00'` opens the file", ["S2"], "housekeeping")])])
    res = prose.prose_all(STATEMENTS[3:], "demo")
    (b, h) = res["groups"]
    assert (b["g"], b["kind"], b["details"]) == (1, "business", [])
    assert (h["g"], h["kind"], h["area"], h["title"], h["rule"]) == (2, "housekeeping", "B", "B: file and error handling", None)
    assert [d["id"] for d in h["details"]] == ["g1.d1"] and h["withheld"] == []


def test_a_withheld_housekeeping_detail_moves_too_and_its_reason_goes_with_it(monkeypatch):
    scripted(monkeypatch, [g(1, "A", "business", ("Hours over 40 are overtime.", ["S1"]),
                             [("Status `'23'` is accepted", ["S3"], "housekeeping")]),
                           g(2, "A", "housekeeping", ("A's files are checked.", ["S2"]), [])], flag=("g1.d1",))
    gs = by_g(prose.prose_all(STATEMENTS[:3], "demo"))
    assert gs[1]["withheld"] == [] and gs[1]["details"] == []
    (w,) = gs[2]["withheld"]
    assert (w["id"], w["layer"], w["cites"]) == ("g1.d1", "detail", ["S3"]) and w["reason"].startswith("OVERREACH")


def test_a_detail_with_no_kind_or_a_business_kind_stays_and_a_rule_never_moves(monkeypatch):
    scripted(monkeypatch, [g(1, "A", "business", ("Hours over 40 are overtime.", ["S1"]),
                             [("`PAY-HOURS` over 40", ["S1"], None), ("Status `'00'` is accepted", ["S2"], "business")]),
                           g(2, "A", "housekeeping", ("A's files are checked.", ["S3"]),
                             [("Status `'23'` is accepted", ["S3"], "business")])])
    res = prose.prose_all(STATEMENTS[:3], "demo")
    gs = by_g(res)
    assert gs[1]["rule"]["id"] == "g1.r" and [d["id"] for d in gs[1]["details"]] == ["g1.d1", "g1.d2"]
    assert [d["id"] for d in gs[2]["details"]] == ["g2.d1"] and res["counts"]["moved_housekeeping"] == 0


def test_the_run_stores_every_statement_cited_and_the_moved_one_counts_for_its_new_group(monkeypatch):
    scripted(monkeypatch, [g(1, "B", "business", ("Positive amounts post.", ["S1"]),
                             [("`OPEN-STATUS` `'00'` opens the file", ["S2"], "housekeeping")])])
    groups, meta, reused, counts, uncited = run.prose_for(STATEMENTS[3:], "demo", "demo", {store.GROUP: {}})
    assert not reused and uncited == [] and counts["moved_housekeeping"] == 1
    (b, h) = groups
    assert b["rule"]["cites"] == ["b#0"] and h["details"][0]["cites"] == ["b#1"]  # the run's ids, not the prompt's
    assert store._group_ids(b) == ["b#0"] and store._group_ids(h) == ["b#1"]
