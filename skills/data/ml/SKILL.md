---
name: ml
description: |
  Machine learning model guidance: architecture review, training pipeline design, feature engineering, deployment.
  Use when developing ML models, reviewing model code, or designing ML systems.

  Use when:
  - "review this ML model"
  - "design ML training pipeline"
  - "how should I deploy this model"
  - "feature engineering advice"
  - "ML architecture guidance"
---

# ML Engineering Skill

Guide machine learning model development, training, and deployment.

## Quick Start

### Review Model Architecture

```bash
/wicked-garden:data:ml review path/to/model/
```

Reviews: Model choice, training data quality, evaluation strategy, deployment readiness.

### Design Training Pipeline

```bash
/wicked-garden:data:ml pipeline --type classification
```

Generates: Data loading, feature engineering, training config, evaluation framework.

## ML Development Workflow

### 1. Problem Definition

- [ ] Problem type clear (classification/regression/ranking)
- [ ] Success metric defined
- [ ] Baseline established
- [ ] Data availability confirmed
- [ ] Inference requirements understood (latency/throughput)

### 2. Data Assessment

- [ ] Sufficient volume (>1000x features)
- [ ] Labels accurate and consistent
- [ ] Features available at inference time
- [ ] No data leakage from target
- [ ] Class balance acceptable

### 3. Feature Engineering

**Good features are**: Predictive, Available at inference, Clean (no leakage), Interpretable.

**Common transformations**:
- Numeric: Scaling, log transform
- Categorical: One-hot, target encoding
- Time: Extract components, cyclical encoding
- Aggregations: Rolling windows, user stats

### 4. Model Selection

| Data Size | Structured | Recommendation |
|-----------|------------|----------------|
| <10K rows | Yes | Linear/Simple tree |
| 10K-1M | Yes | GradientBoosting (XGBoost/LightGBM) |
| >1M | Yes | Deep learning possible |
| Any | Images/Text | Deep learning |

### 5. Training & Evaluation

**Split strategy**: Random (if i.i.d.), Time-based (if time series), Cross-validation (robust).

**Key metrics**:
- **Classification**: Accuracy, Precision, Recall, F1, AUC
- **Regression**: RMSE, MAE, R²

### 6. Hyperparameter Tuning

- **Grid search**: Exhaustive, slow
- **Random search**: More efficient
- **Bayesian optimization**: Most efficient

### 7. Deployment

**Patterns**: Batch scoring, REST API, Streaming

**Checklist**:
- [ ] Inference latency acceptable
- [ ] Model size appropriate
- [ ] Feature pipeline reproducible
- [ ] Monitoring instrumented
- [ ] Rollback plan documented

## ML Monitoring

**Model Performance**: Prediction accuracy, distribution shifts, error rate by segment.

**Data Quality**: Feature distributions, missing rates, cardinality changes.

**System Health**: Latency (p50, p95, p99), throughput, memory.

## Integration

- **wicked-search**: Find model code with `/wicked-garden:search:code "model|classifier"`
- **wicked-kanban**: Track experiments as tasks
- **wicked-garden:data:numbers**: Analyze training data

## Best Practices

- **Always baseline**: Start simple, measure improvement, justify complexity
- **Avoid leakage**: Use only past data, split before processing
- **Monitor production**: Track predictions, detect drift, plan retraining
- **Document everything**: Architecture, features, training data, results

## Reference

For detailed techniques:
- [Output Templates](refs/templates.md) - Model review report, model card
