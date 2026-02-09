# wicked-data Test Scenarios

This directory contains real-world test scenarios demonstrating wicked-data functionality. Each scenario is designed to prove actual value for data engineering and analysis workflows.

## Scenario Overview

| Scenario | Type | Difficulty | Time | Focus |
|----------|------|------------|------|-------|
| [csv-profiling-analysis](./01-csv-profiling-analysis.md) | Data | Basic | 5 min | Dataset profiling and exploration |
| [data-quality-assessment](./02-data-quality-assessment.md) | Data | Intermediate | 8 min | Quality dimensions and schema validation |
| [pipeline-design-review](./03-pipeline-design-review.md) | Pipeline | Intermediate | 10 min | ETL pipeline review and design |
| [exploratory-analysis-insights](./04-exploratory-analysis-insights.md) | Analysis | Intermediate | 12 min | EDA with business recommendations |
| [ml-model-review](./05-ml-model-review.md) | Analysis | Advanced | 12 min | ML architecture and deployment readiness |
| [large-file-sql-analysis](./06-large-file-sql-analysis.md) | Data | Basic | 6 min | DuckDB SQL for large files |

## Quick Start

### Run a Basic Scenario

```bash
cd /path/to/wicked-data
# Follow the steps in any scenario markdown file
```

### What Each Scenario Proves

**csv-profiling-analysis**
- Instant dataset profiling without manual exploration
- Schema inference for CSV files
- Natural language to SQL translation
- Data quality issue detection
- Real-world use: Initial data exploration

**data-quality-assessment**
- Multi-dimensional quality assessment (completeness, validity, uniqueness, consistency)
- Schema validation with constraints
- Prioritized issue reporting (P1/P2/P3)
- Remediation recommendations
- Real-world use: Data pipeline validation, data governance

**pipeline-design-review**
- Security issue detection (credentials, secrets)
- Best practice compliance checking
- Production readiness assessment
- New pipeline architecture design
- Real-world use: Code review for data engineers

**exploratory-analysis-insights**
- Structured exploration workflow
- Pattern and anomaly discovery
- Insight-to-action framework
- Business recommendations with impact estimates
- Real-world use: Business intelligence, analytics

**ml-model-review**
- Data leakage detection
- Evaluation methodology review
- Production readiness checklist
- Model card generation
- Real-world use: ML engineering review, MLOps

**large-file-sql-analysis**
- Out-of-core processing for large files
- SQL querying without database setup
- Efficient aggregations and joins
- Export capabilities
- Real-world use: Ad-hoc analysis of production data

## Learning Path

**New to data analysis?** Start here:
1. [csv-profiling-analysis](./01-csv-profiling-analysis.md) - See basic profiling in action
2. [large-file-sql-analysis](./06-large-file-sql-analysis.md) - Learn SQL-based exploration
3. [exploratory-analysis-insights](./04-exploratory-analysis-insights.md) - Generate business insights

**Data engineering focus?** Follow this path:
1. [data-quality-assessment](./02-data-quality-assessment.md) - Quality and validation
2. [pipeline-design-review](./03-pipeline-design-review.md) - Pipeline best practices
3. [csv-profiling-analysis](./01-csv-profiling-analysis.md) - Data profiling tools

**ML engineering focus?**
1. [ml-model-review](./05-ml-model-review.md) - Model architecture review
2. [data-quality-assessment](./02-data-quality-assessment.md) - Training data quality
3. [exploratory-analysis-insights](./04-exploratory-analysis-insights.md) - Feature exploration

## Scenario Format

Each scenario follows this structure:

```markdown
---
name: scenario-name
title: Human Readable Title
description: One-line description
type: data|analysis|pipeline
difficulty: basic|intermediate|advanced
estimated_minutes: N
---

# Title

Brief explanation of what this proves.

## Setup
Concrete steps to create test data.

## Steps
Numbered, executable steps with code blocks.

## Expected Outcome
What you should see.

## Success Criteria
- [ ] Checkboxes for verification

## Value Demonstrated
WHY this matters in real-world usage.
```

## Personas Covered

These scenarios demonstrate value for different data roles:

| Persona | Scenarios | Key Value |
|---------|-----------|-----------|
| **Data Analyst** | 01, 04, 06 | Faster exploration, better insights |
| **Data Engineer** | 02, 03, 06 | Quality gates, pipeline best practices |
| **ML Engineer** | 05, 02, 04 | Model review, data quality for ML |
| **Analytics Engineer** | 02, 03, 04 | Schema validation, insight generation |

## Testing Philosophy

These scenarios are **functional tests**, not unit tests:

- **Real data patterns**: Actual CSV files with realistic issues
- **Real workflows**: End-to-end analysis and review processes
- **Real value**: Time savings, quality improvements, risk reduction
- **Real problems**: Data leakage, quality issues, production readiness

Each scenario answers: "Would I actually use this feature in production?"

## Integration Points

wicked-data scenarios demonstrate integration with:

- **wicked-data:numbers**: Large file SQL analysis (scenario 06)
- **wicked-cache**: Caching profiling results (mentioned in scenarios)
- **wicked-kanban**: Documenting issues as tasks (scenarios 02, 03, 05)
- **wicked-mem**: Storing analysis patterns (mentioned in scenarios)
- **wicked-search**: Finding existing pipeline code (scenario 03)

## Contributing New Scenarios

When adding scenarios, ensure:

1. **Real-world use case** - Not a toy example
2. **Complete setup** - Reproducible test data creation
3. **Realistic complexity** - Issues that actually occur in practice
4. **Clear value** - Articulates time saved or problems prevented
5. **Verifiable criteria** - Checkboxes that can be tested

See existing scenarios as templates.

## Scenario Maintenance

- Test scenarios after each release
- Update if API or skill interfaces change
- Add scenarios for new capabilities
- Keep setup scripts working on latest Python/DuckDB versions
