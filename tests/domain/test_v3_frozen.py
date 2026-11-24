"""The J6 v3 prompts, cards and contract are the proof's frozen files, byte for byte (DES-j6-build G2).

``scripts/domain/SHA256SUMS`` holds the hashes the proof froze (``proof-v3/FROZEN.sha256`` and its ``frozen/``
tree) and the prose calibration's three prompts (DES-j6-build §6: ``prose_v2`` as ``prose.txt``, check v2, repair). A change to any of these files is a change to the calibrated pipeline, so it changes this list on purpose.
"""
import hashlib
import os

HERE = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "domain")


def test_every_frozen_file_matches_its_recorded_hash():
    with open(os.path.join(HERE, "SHA256SUMS")) as fh:
        rows = [line.split() for line in fh if line.strip()]
    assert len(rows) == 12
    for digest, rel in rows:
        with open(os.path.join(HERE, rel), "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == digest, rel


def test_every_prompt_the_pipeline_reads_is_listed():
    with open(os.path.join(HERE, "SHA256SUMS")) as fh:
        listed = {line.split()[1] for line in fh if line.strip()}
    on_disk = {f"prompts/{f}" for f in os.listdir(os.path.join(HERE, "prompts"))}
    on_disk |= {f"cards/{f}" for f in os.listdir(os.path.join(HERE, "cards"))}
    assert on_disk | {"contract.json"} == listed
