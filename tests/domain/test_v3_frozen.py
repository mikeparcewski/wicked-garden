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
    "prompts/prose.txt": "00ddf9bf9ccb5d81bcb5ba8a7ec41e5fbd616a1823454b510a87a81105ad9e2d",
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
