"""garden#1618: a repair may cite fewer statements than the sentence it repairs. A statement it drops that no other
sentence cites stays in its group as a withheld record (so garden#1549's "every Checked statement is in a group"
holds), and ``uncited`` reports the final state. 0 real model calls (scripted writer, checker and repair)."""
import json

from domain import model_calls, prose, run, store


def st(sid, lines, claims):
    f = "app/cbl/R.cbl"
    return dict(id=sid, status="Checked", kind="rule", name="P", anchor=dict(file=f, lines=lines),
                claims=[dict(c, i=k, lines=[f"{f}:{lines[0] + k}"]) for k, c in enumerate(claims)])


STATEMENTS = [
    st("r#0", [10, 12], [dict(type="effect", text="adds `TRAN-AMT` to `ACCT-CURR-BAL`")]),
    st("r#1", [20, 22], [dict(type="effect", text="adds `TRAN-AMT` to `ACCT-CURR-CYC-CREDIT`")]),
]
BOTH = "`TRAN-AMT` is added to `ACCT-CURR-BAL` and to `ACCT-CURR-CYC-CREDIT`."
ONE = "`TRAN-AMT` is added to `ACCT-CURR-CYC-CREDIT`."


def scripted(monkeypatch, groups, flag=(), repairs=()):
    def claude(step, cid, prompt, timeout=1500, role=None):
        if step == "prose":
            return json.dumps({"groups": groups}), 0
        return json.dumps({"repairs": list(repairs)}), 0

    def codex(step, cid, prompt, timeout=1500, role=None):
        ids = [ln[1:ln.index("]")] for ln in prompt.split("\n") if ln.startswith("[g")]
        bad = flag if step == "prose-check" else ()
        return json.dumps({"verdicts": [{"id": i, "verdict": "OVERREACH" if i in bad else "SUPPORTED", "case": "SCOPE",
                                         "reason": "x"} for i in ids]}), 0
    monkeypatch.setattr(model_calls, "claude", claude)
    monkeypatch.setattr(model_calls, "codex", codex)


def group(n, rule, details=()):
    return dict(g=n, title=f"T{n}", area="R", kind="business", rule=dict(text=rule[0], cites=rule[1]),
                details=[dict(text=t, cites=c, kind="business") for t, c in details])


def every_cite(groups):
    return {c for g in groups for x in ([g["rule"]] if g.get("rule") else []) + g["details"] + g["withheld"] for c in x["cites"]}


def test_a_repair_that_drops_a_statements_last_cite_keeps_it_as_a_withheld_record(monkeypatch):
    # The codex-check case on garden#1615: the only sentence citing S1 is repaired to cite S2 alone.
    scripted(monkeypatch, [group(1, ("Posted amounts update the balance and the cycle credit.", ["S2"]), [(BOTH, ["S1", "S2"])])],
             flag=("g1.d1",), repairs=[{"id": "g1.d1", "text": ONE, "cites": ["S2"]}])
    res = prose.prose_all(STATEMENTS, "demo")
    (g,) = res["groups"]
    assert [(d["id"], d["cites"], d["fate"]) for d in g["details"]] == [("g1.d1", ["S2"], "repaired")]
    assert [(w["id"], w["text"], w["cites"], w["reason"]) for w in g["withheld"]] == [
        ("g1.d1~dropped", BOTH, ["S1"], "the repair dropped S1, which no other sentence cites")]
    assert every_cite(res["groups"]) == {"S1", "S2"}
    assert res["uncited"] == [] and res["counts"]["kept_dropped"] == 1


def test_a_repair_that_drops_a_statement_another_sentence_cites_keeps_nothing(monkeypatch):
    scripted(monkeypatch, [group(1, ("Posted amounts update the balance and the cycle credit.", ["S1", "S2"]), [(BOTH, ["S1", "S2"])])],
             flag=("g1.d1",), repairs=[{"id": "g1.d1", "text": ONE, "cites": ["S2"]}])
    res = prose.prose_all(STATEMENTS, "demo")
    (g,) = res["groups"]
    assert g["withheld"] == [] and "kept_dropped" not in res["counts"]
    assert res["uncited"] == []


def test_the_kept_record_carries_the_runs_statement_ids_and_counts_for_its_groups_inputs(monkeypatch):
    # Through run.prose_for: the withheld record's cites become the run's ids (run.py maps withheld cites too), and
    # the group's stored inputs (store._group_ids) include the kept statement, so a later change to it rewrites the group.
    scripted(monkeypatch, [group(1, ("Posted amounts update the balance and the cycle credit.", ["S2"]), [(BOTH, ["S1", "S2"])])],
             flag=("g1.d1",), repairs=[{"id": "g1.d1", "text": ONE, "cites": ["S2"]}])
    groups, meta, reused, counts, uncited = run.prose_for(STATEMENTS, "demo", "demo", {store.GROUP: {}})
    (g,) = groups
    assert g["withheld"][0]["cites"] == ["r#0"] and uncited == []
    assert sorted(store._group_ids(g)) == ["r#0", "r#1"]


def test_uncited_is_the_final_state_and_a_malformed_only_statement_is_written_again_next_run(monkeypatch):
    # cross-model round 1 on garden#1619: S1 is cited only by a group whose shape cannot be checked, and the coverage
    # retry adds nothing. S1 sits in that group's notice, so it is not uncited; stored the way store.rows_for stores
    # it (a whole-withheld group has no inputs, store.py:426-430), the next run writes S1 again instead of leaving it out.
    bad_shape = dict(g=2, title="T2", area="R", kind="other", rule=dict(text="x", cites=["S1"]), details=[])
    scripted(monkeypatch, [group(1, ("Posted amounts update the cycle credit.", ["S2"])), bad_shape])
    groups, meta, reused, counts, uncited = run.prose_for(STATEMENTS, "demo", "demo", {store.GROUP: {}})
    assert uncited == []
    notice = [w for g in groups for w in g["withheld"] if w["layer"] == "group"]
    assert [w["cites"] for w in notice] == [["r#0"]]
    text_of = meta["text_of"]
    whole = lambda g: any(w.get("layer") == "group" for w in g["withheld"])  # noqa: E731
    prior = {store.GROUP: {f"g{g['g']}": dict(group=g, desc="demo", pipeline=store.PROSE,
                                              inputs={} if whole(g) else {i: text_of.get(i) for i in store._group_ids(g)},
                                              uncited={i: text_of.get(i) for i in uncited}) for g in groups}}
    asked = []
    scripted(monkeypatch, [group(1, ("Posted amounts update the balance.", ["S1"]))])
    real = model_calls.claude
    monkeypatch.setattr(model_calls, "claude", lambda step, cid, prompt, timeout=1500, role=None: asked.append((step, prompt)) or real(step, cid, prompt, timeout, role))
    groups2, meta2, reused2, counts2, uncited2 = run.prose_for(STATEMENTS, "demo", "demo", prior)
    prose_prompts = [p for step, p in asked if step == "prose"]
    assert len(prose_prompts) == 1 and "app/cbl/R.cbl:10-12" in prose_prompts[0] and "app/cbl/R.cbl:20-22" not in prose_prompts[0]
    assert uncited2 == []
