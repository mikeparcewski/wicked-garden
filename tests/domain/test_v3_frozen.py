"""The J6 v3 prompts, cards and contract are the proof's frozen files, byte for byte (DES-j6-build G2).

``PROOF`` below and ``scripts/domain/SHA256SUMS`` hold the hashes the proof froze (``proof-v3/FROZEN.sha256`` and its ``frozen/``
tree) and the prose calibration's three prompts (DES-j6-build §6: ``prose_v2`` as ``prose.txt``, check v2, repair). A change to any of these files is a change to the calibrated pipeline, so it changes this list on purpose.
"""
import hashlib
import os

HERE = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "domain")


# The proof's own hashes, copied from its records, never from this repository: ``proof-v3/FROZEN.sha256`` (check_C6,
# confirm_R, facts_cobol_R, cards/cobol.md), ``sha256sum`` over ``proof-v3/frozen/`` (extract, repair, repair_m,
# cards/generic.md, contract.json) and over the prose calibration's ``prose-cal/prompts/`` (prose_v2 as prose.txt,
# prose_check, prose_repair). A file here that drifts from the proof fails, whatever SHA256SUMS says.
PROOF = {
    # garden#1548 (DES-1548, coord-approved): the checker judges a `concern` on its own; the proof froze b11016de9cad.
    "prompts/check_C6.txt": "fd2bddbf5ebeafefec37f49f69c712335bd597380bcc288f4f32b8c4eebf0beb",
    "prompts/confirm_R.txt": "6db2cf9db957219278812367e185e966b57669498f37cf77964ae56e13185603",
    "prompts/facts_cobol_R.txt": "ba4ae3dd8041ef9a3ca9002f157a4c39d7d547edc5ef98f5fae6545367cef36c",
    # garden#1548 (DES-1548, coord-approved): record updates on the M7 line, trap 8 states the branch plus a concern; the proof froze 4523328d4ada.
    "cards/cobol.md": "a29d75f95dc7e50e19e50d05484beb099d9908509da7078bf1c08a17249e44f5",
    # garden#1548 (DES-1548, coord-approved): rules 8, 11 and 12 and the `concerns` output; the proof froze 1a7f851637be.
    "prompts/extract.txt": "49304de375db25116a19a01d8b5fe599288fd262b79ceab39ba498987ae92465",
    "prompts/repair.txt": "645889df305eb27e1fb6286632269bd0907e6de946da12707ea42e9f03dd4234",
    "prompts/repair_m.txt": "62779b9799c402a3c46c0a4858e5637544a7e27060093f145f8cf7cf50cd69b1",
    "cards/generic.md": "f1d2d08d5059d2cc1d1af53460d299f900e5b757aa225bd030a80d1a09e9c763",
    # garden#1548 (DES-1548, coord-approved): the derived kind counts a record update; statements carry concerns; the proof froze 6657f142ea3d.
    "contract.json": "8a2be4460ac7305495d5a8d5f2c9f25a9f2a296e1317ca2f6adbcf23ba3baea4",
    # garden#1599 (DES-1599, coord-approved): each DETAIL carries its own kind, the housekeeping list is spelled out, a business RULE cites only business statements; the proof froze 00ddf9bf9ccb.
    # garden#1545 (DES-1545-t18 B-min, coord-approved): every business sentence cites only business statements, a lookup, a re-read or a write of
    # values set elsewhere that only handles its status is housekeeping, and a mixed DETAIL is split in two (garden#1607); #1599 froze f9514b6ba567.
    "prompts/prose.txt": "03ac68368acc7a6d05f96e65318a0f89b715d7b7cc539908790f7eaa95333f28",
    "prompts/prose_check.txt": "391d74b3a88ca2bbeca6c13f331a088b8eed2e37a4c8ed8354c7ba7a889e8ce2",
    "prompts/prose_repair.txt": "1b2f5d4f5788a263a5d9d29fdad0fc3732446b50aee015de207c79edba06edaa",
}


def test_every_frozen_file_matches_the_proofs_own_hash():
    for rel, digest in PROOF.items():
        with open(os.path.join(HERE, rel), "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == digest, rel
    with open(os.path.join(HERE, "SHA256SUMS")) as fh:
        assert {line.split()[1]: line.split()[0] for line in fh if line.strip()} == PROOF


def test_every_prompt_the_pipeline_reads_is_listed():
    with open(os.path.join(HERE, "SHA256SUMS")) as fh:
        listed = {line.split()[1] for line in fh if line.strip()}
    on_disk = {f"prompts/{f}" for f in os.listdir(os.path.join(HERE, "prompts"))}
    on_disk |= {f"cards/{f}" for f in os.listdir(os.path.join(HERE, "cards"))}
    assert on_disk | {"contract.json"} == listed


# garden#1610: the host's own stating checks, pinned with the store.HOST they were last judged under. A change to one of
# these files fails below until it is re-pinned. The rule: if the change alters what a run states (an M check, what a
# prompt shows, what counts as accounted, the rendered text), bump store.HOST in the same change, so a store the old
# checks stated says it was made by an earlier pipeline version (garden#1601); if it does not, re-pin and leave HOST.
HOST_AT = 0
HOST_PIN = {
    "batches.py": "ef00e51c60fc7d2fbebcfba8795a936417b8ed028e2b83a60b73ef74073e3671",
    "check.py": "21a7f21aa6c2cd47e4180ff9d8ad4ff106124315c5638e5b2ddc3b9006b39487",
    "cobol_ctx.py": "7c7619ffae25d6283a2f73b55916a72e279e32df3e9a0397978d7690a7e01631",
    "cobol_flow.py": "ef4c5c187d5d2e085c6e6b624d87416a51411d69326acce3e2a357ff550f6ac7",
    "defs.py": "f75d02b1a6dbd5e2d4407e41362737be86669ea3b0ca5855dd95c78cfca8a492",
    "extract.py": "279a4fd54fc2f41d0f3510297f785c9fbf16b8dc3c858b669ecb599c31a2c673",
    "graph.py": "160cea90d5b5a9ab12b2c45e9a855b930a1245b4447d5a2275bdee3324b17383",
    "lookup.py": "5e74882951afc4ccdb33a67b91d49231ead539a6f9758efaf159bad2c09742bf",
    "r_stage.py": "f3ab2028650c236e99002fa5a5547eb40cac8105fdae5336c867c2ba8879689b",
    "reach.py": "52861ef241e965193704c9bf9f39674e3c362df937b6a1deb46df7223e8d7ab8",
    "render.py": "17335e132b454b675b55f2ba0630a4da50d1e4f19443cf2d4a02ed924cf7b310",
    "union.py": "c1a4e4efb3d7492868cb55321b0c9d901f7cb3e1fcffc02e8fdb57bbc2a60230",
}


def test_a_changed_host_stating_check_is_judged_for_a_host_bump():
    from domain import store
    assert set(HOST_PIN) == set(store.HOST_FILES)
    assert store.HOST == HOST_AT, "store.HOST moved: set HOST_AT to it and re-pin HOST_PIN in the same change"
    changed = []
    for rel, digest in HOST_PIN.items():
        with open(os.path.join(HERE, rel), "rb") as fh:
            if hashlib.sha256(fh.read()).hexdigest() != digest:
                changed.append(rel)
    assert not changed, (f"host stating checks changed: {changed}. If the change alters what a run states, bump "
                         "store.HOST (garden#1610); either way, re-pin HOST_PIN (and HOST_AT) here")
