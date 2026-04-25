# s4 Split Validation — 50-file / 3-service Change

## The Bug

Old s4: "Does this change touch **4-20 files or 1-2 services**?" weight=1

A 50-file PR across 3 services answers NO (it's >20 files AND >2 services).
Result: 0 pts from s4 alone (if s1/s2/s3 also NO) → HIGH reading.
Same score as a 1-file typo fix. Silent underscoring.

## The Fix

Split into two monotonic questions where YES unambiguously increases risk:

| ID   | Question                                                              | Weight |
|------|-----------------------------------------------------------------------|--------|
| s4a  | Does this work touch more than 5 files?                               | 1      |
| s4b  | Does this work touch more than 20 files OR more than one service?     | 2      |

Both s4a and s4b can only increase the score when answered YES.
A 50-file / 3-service change answers YES to both → +3 pts.

## Scoring Comparison

| Scenario                      | Old s4 pts | Old reading (s1/s2/s3=NO) | New s4a+s4b pts | New reading |
|-------------------------------|-----------|--------------------------|-----------------|-------------|
| 1-file typo fix               | 0         | HIGH                     | 0               | HIGH        |
| 8-file single-service change  | 1 (YES)   | MEDIUM                   | 1 (s4a=YES)     | MEDIUM      |
| 50-file 3-service change      | 0 (NO!)   | HIGH (bug)               | 3 (both YES)    | MEDIUM      |
| 50-file + s1=YES              | 0 (NO!)   | LOW (from s1 only)       | 6               | LOW         |

## Threshold Recalibration

Old max points: s1(3)+s2(3)+s3(2)+s4(1) = 9
New max points: s1(3)+s2(3)+s3(2)+s4a(1)+s4b(2) = 11

Thresholds `medium_threshold=1` and `low_threshold=5` are unchanged.
The 50-file / 3-service scenario (s4a+s4b only = 3 pts) yields MEDIUM, not LOW,
because s1(>20 files) and s2(3+ services) are stronger signals — answering
those YES would push to LOW territory. This is correct: s4a/s4b are graduated
stepping stones, not the ceiling.

## Cluster-A Integration Test (AC-5)

Cluster-A description: "~10-20 files across 5 domains, single repo, single team"

Old answers: s4=True (4-20 files range matched) → 1 pt → MEDIUM
New answers: s4a=True (>5 files, YES) + s4b=False (not >20, not multi-service) → 1 pt → MEDIUM

Reading unchanged: MEDIUM. Test still passes.
