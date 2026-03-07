# Data Lens

Additional questions for the five lenses when the work involves data pipelines,
schemas, analytics, or data quality.

## Lens 1 Additions: Is This Real?

- Is the data actually wrong, or is the expectation wrong?
- Is this a data quality issue or a schema/contract issue?
- Is the "missing data" actually filtered out by a rule that's working correctly?
- Are we measuring the right thing, or is the metric definition flawed?

## Lens 2 Additions: What's Actually Going On?

- Is the issue at ingestion, transformation, or presentation?
- Is a schema change upstream silently breaking downstream consumers?
- Is this a timing issue? (data not yet available vs. actually missing)
- Is the pipeline idempotent? Could reruns have introduced duplicates?

## Lens 3 Additions: What Else Can We Fix?

- Are other pipelines consuming the same source with the same vulnerability?
- Is there missing data validation at ingestion boundaries?
- Are schema contracts documented and enforced, or assumed?
- Can we add data quality checks that catch this class of issue automatically?

## Lens 4 Additions: Should We Rethink?

- Should this be a streaming pipeline instead of batch (or vice versa)?
- Would schema evolution tooling prevent breaking changes?
- Should the data ownership boundary move? (who produces vs. consumes)
- Would a data contract between producer and consumer prevent this?

## Lens 5 Additions: Better Way?

- Can we fix the source instead of patching the consumer?
- Can we add a dead-letter queue instead of failing silently?
- Can we use schema registry to catch incompatibilities before deploy?
- Can we solve this with monitoring/alerting instead of code changes?
