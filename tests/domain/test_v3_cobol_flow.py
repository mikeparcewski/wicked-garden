"""The fail-closed R gate (DES-j6-build G2; DES-j6-v3 §2, coord delta checks F1-F4 and C-G1). Text only, 0 model calls.

Ported from the J6 v3 proof's ``cal/test_cobol_flow.py``. The synthetic programs are written to a scratch tree
(``app/cbl`` and ``app/cpy``); the CardDemo checks run when ``CARDDEMO_ROOT`` names a CardDemo checkout, and are
skipped otherwise. Two proof checks stay in the proof's lane, since they need its recorded R runs and its pre-fix
parser; the lane re-decides every recorded R unit through this port instead (131 units, 0 differences).
"""
import os

import pytest

from domain import cobol_ctx as cx
from domain import cobol_flow as g
from domain import defs


def A(t):
    return "       " + t


def B(t):
    return "           " + t


@pytest.fixture
def prog(tmp_path):
    (tmp_path / "app/cbl").mkdir(parents=True)
    (tmp_path / "app/cpy").mkdir()
    defs.set_root(str(tmp_path))

    def make(name, body, copybooks=None):
        lines = [A("IDENTIFICATION DIVISION."), A(f"PROGRAM-ID. {name[:8]}."), A("DATA DIVISION."),
                 A("WORKING-STORAGE SECTION."), A("01 WS-X PIC X."), A("01 WS-RETURN-MSG PIC X(10)."),
                 A("PROCEDURE DIVISION.")] + body
        for k, v in (copybooks or {}).items():
            (tmp_path / f"app/cpy/{k}.cpy").write_text("\n".join(v) + "\n")
        f = f"app/cbl/{name}.cbl"
        (tmp_path / f).write_text("\n".join(lines) + "\n")
        defs.set_root(str(tmp_path))
        return f
    return make


def line_of(f, head):
    return next(i for i, s in enumerate(defs.flines(f), 1) if s.strip().startswith(head))


def ok(f, head):
    return g.path_complete(f, line_of(f, head))[0]


REFUSED = {
    "THRU one line, interior anchor":
        ([A("MAIN-PARA."), B("PERFORM PA THRU PC."), B("GOBACK."), A("PA."), B("DISPLAY 'A'."), A("PB."), B("DISPLAY 'B'."),
          A("PC."), B("EXIT.")], "PB.", None),
    "THRU on the next line, interior anchor":
        ([A("MAIN-PARA."), B("PERFORM PA"), B("   THRU PC."), B("GOBACK."), A("PA."), B("DISPLAY 'A'."), A("PB."),
          B("DISPLAY 'B'."), A("PC."), B("EXIT.")], "PB.", None),
    "THROUGH, interior anchor":
        ([A("MAIN-PARA."), B("PERFORM PA THROUGH PC."), B("GOBACK."), A("PA."), B("DISPLAY 'A'."), A("PB."), B("DISPLAY 'B'."),
          A("PC."), B("EXIT.")], "PB.", None),
    "PERFORM of a SECTION":
        ([A("MAIN-PARA."), B("PERFORM WORK-SEC."), B("GOBACK."), A("WORK-SEC SECTION."), A("W1."), B("DISPLAY 'A'."), A("W2."),
          B("DISPLAY 'B'.")], "W2.", None),
    "GO TO ... DEPENDING":
        ([A("MAIN-PARA."), B("GO TO P1 P2 P3 DEPENDING ON WS-X."), A("P1."), B("GOBACK."), A("P2."), B("GOBACK."), A("P3."),
          B("GOBACK.")], "P2.", None),
    "ALTER":
        ([A("MAIN-PARA."), B("ALTER SW TO PROCEED TO P2."), B("GO TO SW."), A("SW."), B("GO TO P1."), A("P1."), B("GOBACK."),
          A("P2."), B("GOBACK.")], "P2.", None),
    "fall-through chain entry -> MID -> TARGET":
        ([A("MAIN-PARA."), B("DISPLAY 'X'."), A("MID."), B("DISPLAY 'Y'."), A("TARGET."), B("DISPLAY 'Z'."), B("GOBACK."),
          A("OTHER-P."), B("PERFORM TARGET.")], "TARGET.", None),
    "entry ends in a conditional GO TO":
        ([A("MAIN-PARA."), B("IF WS-X = 'Z' GO TO DONE-P."), A("TARGET."), B("DISPLAY 'T'."), A("DONE-P."), B("GOBACK.")],
         "TARGET.", None),
    "entry ends in MOVE ... TO WS-RETURN-MSG (RETURN in a data name)":
        ([A("MAIN-PARA."), B("MOVE SPACES TO WS-RETURN-MSG."), A("TARGET."), B("GOBACK.")], "TARGET.", None),
    "PERFORM with the name on the next line":
        ([A("MAIN-PARA."), B("PERFORM"), B("    TARGET."), B("GOBACK."), A("TARGET."), B("DISPLAY 'T'.")], "TARGET.", None),
    "Area-B procedure COPY whose copybook does GO TO":
        ([A("MAIN-PARA."), B("PERFORM TARGET."), B("GOBACK."), A("SETUP-P."), B("COPY JUMPCP."), A("TARGET."), B("DISPLAY 'T'."),
          A("WORK."), B("GOBACK.")], "TARGET.", {"JUMPCP": [B("GO TO WORK.")]}),
    "GO TO out of a performed range makes the next paragraph enterable":
        ([A("MAIN-PARA."), B("PERFORM P1."), B("GOBACK."), A("P1."), B("GO TO P2-EXIT."), A("P2-EXIT."), B("EXIT."),
          A("TARGET."), B("DISPLAY 'T'."), A("OTHER-P."), B("PERFORM TARGET.")], "TARGET.", None),
    "control: unnamed main falls into the first paragraph":
        ([B("DISPLAY 'M'."), A("TARGET."), B("GOBACK.")], "TARGET.", None),
}

COMPLETE = {
    "control: plain PERFORM from a main that ends in GOBACK":
        ([A("MAIN-PARA."), B("PERFORM TARGET."), B("GOBACK."), A("TARGET."), B("DISPLAY 'T'.")], "TARGET."),
    "control: header with its period on the next line":
        ([A("MAIN-PARA."), B("PERFORM TARGET."), B("GOBACK."), A("TARGET"), B("."), B("DISPLAY 'T'.")], "TARGET"),
    "control: EXEC CICS RETURN ends the entry":
        ([A("MAIN-PARA."), B("PERFORM TARGET."), B("EXEC CICS RETURN"), B("END-EXEC."), A("TARGET."), B("DISPLAY 'T'.")],
         "TARGET."),
    "control: X / X-EXIT idiom with GO TO X-EXIT":
        ([A("MAIN-PARA."), B("PERFORM TARGET THRU TARGET-EXIT."), B("GOBACK."), A("TARGET."),
          B("IF WS-X = 'A' GO TO TARGET-EXIT END-IF."), B("DISPLAY 'T'."), A("TARGET-EXIT."), B("EXIT.")], "TARGET."),
}


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_a_control_flow_form_the_walk_cannot_follow_is_refused(prog, name):
    body, head, cpy = REFUSED[name]
    assert ok(prog("T" + str(sorted(REFUSED).index(name)), body, cpy), head) is False


@pytest.mark.parametrize("name", sorted(COMPLETE))
def test_a_walk_the_gate_can_follow_is_complete(prog, name):
    body, head = COMPLETE[name]
    assert ok(prog("C" + str(sorted(COMPLETE).index(name)), body), head) is True


def test_special_names_are_the_platform_written_ones():
    assert g.special_names("SQLSTATE EIBAID EIBCALEN WS-X") == ["EIBAID", "SQLSTATE"]


CARDDEMO = os.environ.get("CARDDEMO_ROOT")
carddemo = pytest.mark.skipif(not CARDDEMO, reason="CARDDEMO_ROOT names no CardDemo checkout")


@pytest.fixture
def cd():
    defs.set_root(CARDDEMO)


@carddemo
def test_carddemo_a_paragraph_reached_only_via_alter_is_refused(cd):
    assert g.path_complete("app/cbl/CBSTM03A.CBL", 765)[0] is False


@carddemo
@pytest.mark.parametrize("f,nm,ln", [("app/cbl/COUSR00C.cbl", "CDEMO-CU00-PAGE-NUM", 367),
                                     ("app/cbl/COACTUPC.cbl", "CDEMO-ACCT-ID", 983),
                                     ("app/cbl/COACTUPC.cbl", "WS-COMMAREA", 868),
                                     ("app/cbl/COADM01C.cbl", "WS-IDX", 121),
                                     ("app/cbl/COADM01C.cbl", "WS-IDX", 231)])
def test_carddemo_writers_are_listed(cd, f, nm, ln):
    S, _ = g.closure_plus(f, nm)
    assert ln in g.write_lines(f, S)


@carddemo
def test_carddemo_an_entry_with_an_unknown_perform_is_refused(cd):
    assert g.required_lines("app/app-transaction-type-db2/cbl/COTRTLIC.cbl", 1383, [])[0] is False


@carddemo
def test_carddemo_implicit_and_platform_writers_refuse_a_clear(cd):
    ok_, why, _ = g.writers_complete("app/cbl/CBACT04C.cbl", ["XREFFILE-STATUS"])
    assert (ok_, "FILE STATUS" in why) == (False, True)
    S, _ = g.closure_plus("app/cbl/CBACT04C.cbl", "XREFFILE-STATUS")
    assert 543 in g.write_lines("app/cbl/CBACT04C.cbl", S)
    ok_, why, _ = g.writers_complete("app/cbl/COCRDUPC.cbl", ["CCARD-AID-PFK05"])
    assert (ok_, "406" in why) == (False, True)
    assert g.writers_complete("app/cbl/COCRDUPC.cbl", ["SQLCODE"])[0] is False
    assert g.required_lines("app/cbl/CBACT04C.cbl", 543, ["XREFFILE-STATUS"])[0] is False
    ok_, why, w = g.writers_complete("app/cbl/COUSR00C.cbl", ["WS-ERR-FLG"])
    assert len(w["WS-ERR-FLG"]) > 0 and ok_ is True


@carddemo
def test_carddemo_a_cics_handle_label_is_an_implicit_entry(cd):
    f = "app/cbl/COACTVWC.cbl"
    assert sorted(cx.paragraphs(f)[k][0] for k in g.handle_labels(f)) == ["ABEND-ROUTINE"]
