# ML Engineering Rubric — review / pipeline

Apply this inline. Caller has pre-gathered model files (for review) or
captured task-type (for pipeline design).

## review

```markdown
## ML Engineering Assessment

**Model**: {name}
**Type**: {classification|regression|ranking|other}
**Status**: {Development|Staging|Production}

### Summary
{2-3 sentence overview}

### Architecture Review
- **Problem Type**: {clear definition}
- **Model Type**: {algorithm/architecture}
- **Justification**: {why this approach}
- **Alternatives Considered**: {other options}

### Data & Features
- **Training Size**: {rows}
- **Feature Count**: {count}
- **Quality**: {assessment}

| Check | Status | Notes |
|-------|--------|-------|
| No data leakage (target in features) | {pass/fail} | |
| Label quality | {pass/fail} | |
| Class imbalance handled | {pass/fail} | |
| Missing values handled | {pass/fail} | |
| Categorical encoding defined | {pass/fail} | |
| Feature importance tracked | {pass/fail} | |

### Evaluation Strategy
- **Metrics**: {precision, recall, RMSE, etc.}
- **Validation**: {holdout / k-fold / time-based}
- **Success Criteria**: {minimum acceptable performance}

### Deployment Readiness
- [ ] Inference latency acceptable
- [ ] Model size appropriate for deployment target
- [ ] Feature pipeline reproducible in production
- [ ] Graceful fallback if model fails
- [ ] A/B testing framework ready
- [ ] Monitoring and logging instrumented
- [ ] Rollback plan documented

### Recommendations
| Priority | Recommendation | Impact | Effort |
|----------|----------------|--------|--------|
| P1 | {critical item} | HIGH | {S/M/L} |

**Recommendation**: {APPROVE|CONDITIONAL|NEEDS REWORK}
**Confidence**: {HIGH|MEDIUM|LOW}
```

## pipeline (training pipeline design)

Problem setup → data/feature stages → model arch → evaluation → tuning → deployment → monitoring.

```markdown
## Training Pipeline: {model_name}

### Problem Statement
- **Type**: {Classification|Regression|Ranking|Other}
- **Target**: {what is being predicted}
- **Business Metric**: {how success is measured}
- **Baseline**: {minimum viable baseline established?}

### Data Flow
1. **Source**: {where data comes from}
2. **Sampling**: {train/val/test split strategy — e.g. 70/15/15}
3. **Features**: {transformation pipeline, feature store integration}
4. **Training**: {model training config, hyperparameter search}
5. **Validation**: {holdout / cross-validation approach}
6. **Registry**: {versioning scheme, metadata, promotion criteria}

### Configuration (sample)
```yaml
data:
  source: {path}
  train_split: 0.7  val_split: 0.15  test_split: 0.15
features:
  categorical: [col1, col2]
  numerical: [col3, col4]
  target: label
model:
  type: {algorithm}
  key_params: {}
evaluation:
  metric: {f1_score|rmse|ndcg}
  threshold: {value}
```

### Monitoring Plan
- **Drift detection**: {feature/target drift strategy}
- **Performance tracking**: {metrics logged}
- **Retraining trigger**: {when to retrain}

### MLOps Principles
- **Reproducible**: version data, code, and models.
- **Monitored**: track performance continuously.
- **Automated**: CI/CD for ML pipelines.
- **Tested**: unit tests for features, integration tests for pipeline.
- **Documented**: model cards for transparency.
```

## Common pitfalls

- Training on future data (leakage).
- Overfitting to validation set.
- Ignoring class imbalance.
- Not testing inference performance.
- Deploying without monitoring.
