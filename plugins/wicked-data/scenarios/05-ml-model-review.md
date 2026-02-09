---
name: ml-model-review
title: ML Model Architecture Review
description: Review machine learning model code for best practices and deployment readiness
type: analysis
difficulty: advanced
estimated_minutes: 12
---

# ML Model Architecture Review

Demonstrate the ML engineering skill by reviewing a machine learning model for architecture quality, data handling, evaluation practices, and production readiness. This helps teams avoid common ML pitfalls before deployment.

## Setup

Create a typical ML model codebase with intentional issues to discover.

```bash
mkdir -p /tmp/ml_models/churn_predictor

# Create the main model file
cat > /tmp/ml_models/churn_predictor/model.py << 'EOF'
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import pickle

# Load data
df = pd.read_csv("customer_data.csv")

# Feature engineering
df['tenure_months'] = (pd.Timestamp.now() - pd.to_datetime(df['signup_date'])).dt.days / 30
df['avg_order_value'] = df['total_revenue'] / df['order_count']
df['days_since_last_order'] = (pd.Timestamp.now() - pd.to_datetime(df['last_order_date'])).dt.days

# Handle missing values
df = df.fillna(0)

# Prepare features
feature_cols = ['tenure_months', 'order_count', 'total_revenue', 'avg_order_value',
                'days_since_last_order', 'support_tickets', 'email_opens']
X = df[feature_cols]
y = df['churned']

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# Train model
model = RandomForestClassifier(n_estimators=100, max_depth=10)
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
print(f"Accuracy: {accuracy_score(y_test, y_pred):.2f}")

# Save model
with open("churn_model.pkl", "wb") as f:
    pickle.dump(model, f)

print("Model saved!")
EOF

# Create a prediction script
cat > /tmp/ml_models/churn_predictor/predict.py << 'EOF'
import pandas as pd
import pickle

# Load model
with open("churn_model.pkl", "rb") as f:
    model = pickle.load(f)

def predict_churn(customer_data):
    """Predict churn probability for a customer."""
    # Prepare features (same as training)
    features = pd.DataFrame([{
        'tenure_months': customer_data['tenure_months'],
        'order_count': customer_data['order_count'],
        'total_revenue': customer_data['total_revenue'],
        'avg_order_value': customer_data['total_revenue'] / customer_data['order_count'],
        'days_since_last_order': customer_data['days_since_last_order'],
        'support_tickets': customer_data['support_tickets'],
        'email_opens': customer_data['email_opens']
    }])

    return model.predict_proba(features)[0][1]

# Example usage
if __name__ == "__main__":
    customer = {
        'tenure_months': 12,
        'order_count': 5,
        'total_revenue': 500,
        'days_since_last_order': 45,
        'support_tickets': 2,
        'email_opens': 10
    }
    prob = predict_churn(customer)
    print(f"Churn probability: {prob:.2%}")
EOF

# Create a config file
cat > /tmp/ml_models/churn_predictor/config.yaml << 'EOF'
model:
  type: RandomForest
  n_estimators: 100
  max_depth: 10

features:
  - tenure_months
  - order_count
  - total_revenue
  - avg_order_value
  - days_since_last_order
  - support_tickets
  - email_opens

training:
  test_size: 0.2
EOF
```

## Steps

### 1. Review the ML model architecture

Request a comprehensive review.

```
/wicked-data:ml review /tmp/ml_models/churn_predictor/
```

Expected review to identify issues across categories:

### 2. Data Handling Issues

"What data handling issues do you see?"

Expected findings:

**Critical (P1)**:
1. **Data leakage**: `tenure_months` and `days_since_last_order` use `pd.Timestamp.now()` - this will differ between training and inference, and leaks future information
2. **No feature scaling**: Random Forest is robust, but if switching models, unscaled features will cause issues
3. **Naive null handling**: `fillna(0)` treats all nulls the same - zeros may be meaningful in some columns

**High Priority (P2)**:
4. **No train/test date split**: Should split by time for churn prediction to avoid future leakage
5. **Calculated features differ**: `avg_order_value` calculated differently in training vs inference (potential division by zero in predict.py)

### 3. Evaluation Issues

"What's wrong with the evaluation approach?"

Expected findings:

**Critical (P1)**:
1. **Only accuracy reported**: For churn (typically imbalanced), accuracy is misleading. Need precision, recall, F1, AUC
2. **No class imbalance handling**: Churn is typically 5-15% - model may just predict "no churn" always
3. **No cross-validation**: Single train/test split is not robust

**High Priority (P2)**:
4. **No baseline comparison**: What does a simple rule achieve? (e.g., "predict churn if no order in 60 days")
5. **No threshold analysis**: Using default 0.5 threshold - should optimize for business metric

### 4. Feature Engineering Issues

"Review the feature engineering approach"

Expected findings:

1. **Inconsistent feature calculation**: Training and inference calculate `avg_order_value` differently
2. **No feature importance analysis**: Which features actually matter?
3. **Missing potentially valuable features**:
   - Customer segment
   - Order frequency trend (increasing/decreasing)
   - Product category preferences
4. **No feature documentation**: What does each feature represent?

### 5. Production Readiness Issues

"Is this model ready for production?"

Expected findings:

**Not Production Ready** - Critical gaps:

1. **No model versioning**: Pickle file with no version tracking
2. **No input validation**: predict.py doesn't validate input schema
3. **No monitoring hooks**: No way to track predictions, drift, or errors
4. **Hardcoded paths**: "customer_data.csv" and "churn_model.pkl" are hardcoded
5. **No error handling**: Division by zero possible in predict.py
6. **No latency consideration**: Loading pickle on every prediction is slow
7. **No A/B test infrastructure**: Can't compare model versions

### 6. Get remediation recommendations

"How should I fix the data leakage issue?"

Expected recommendations:

```python
# WRONG: Uses current time (leaks future info)
df['tenure_months'] = (pd.Timestamp.now() - pd.to_datetime(df['signup_date'])).dt.days / 30

# RIGHT: Use a fixed reference date (the date each record was created)
# Option 1: Use a snapshot date column
df['tenure_months'] = (df['snapshot_date'] - df['signup_date']).dt.days / 30

# Option 2: For inference, pass the reference date explicitly
def calculate_features(customer_data, reference_date):
    tenure_months = (reference_date - customer_data['signup_date']).days / 30
    # ... other features
```

Key principle: Any feature that uses "now" is a red flag. Features must be calculable the same way in training and inference.

### 7. Request a model card

"Generate a model card for documentation"

Expected model card:

```markdown
# Model Card: Customer Churn Predictor

## Model Details
- **Model Type**: Random Forest Classifier
- **Version**: 1.0 (unversioned - needs improvement)
- **Training Date**: Unknown (not tracked)
- **Author**: Unknown

## Intended Use
- **Primary Use**: Predict which customers are likely to churn in next 30 days
- **Users**: Marketing team for retention campaigns
- **Out of Scope**: Not suitable for real-time decisioning (latency not optimized)

## Training Data
- **Source**: customer_data.csv
- **Size**: Unknown (not documented)
- **Time Period**: Unknown
- **Features**: 7 features (tenure, orders, revenue, recency, support, email)

## Performance
- **Reported Accuracy**: Unknown (not saved)
- **Missing Metrics**: Precision, Recall, F1, AUC
- **Class Balance**: Unknown

## Limitations
1. Data leakage in feature calculation
2. No time-based train/test split
3. No handling of class imbalance
4. Inconsistent feature calculation between train/inference

## Ethical Considerations
- Model may perpetuate biases in historical churn patterns
- High-risk customers may receive more aggressive marketing

## Recommendations Before Deployment
1. Fix data leakage issues
2. Implement proper evaluation metrics
3. Add model versioning and monitoring
4. Create feature store for consistent calculation
```

## Expected Outcome

- All major ML issues identified and categorized by severity
- Data leakage clearly explained with fix
- Evaluation gaps highlighted with correct metrics
- Production readiness checklist provided
- Model card generated for documentation
- Actionable remediation steps for each issue

## Success Criteria

- [ ] Data leakage in time-based features identified
- [ ] Accuracy-only evaluation flagged as insufficient
- [ ] Class imbalance issue raised
- [ ] Feature calculation inconsistency found
- [ ] Production gaps enumerated (versioning, monitoring, validation)
- [ ] Division by zero risk in predict.py caught
- [ ] Proper fix for data leakage provided
- [ ] Model card includes limitations section
- [ ] Recommendations are prioritized and actionable

## Value Demonstrated

**The problem**: ML models that work in notebooks fail in production. Common issues:
- Data leakage inflates training metrics
- Wrong evaluation metrics hide poor performance
- Training/inference skew causes silent failures
- No monitoring means drift goes undetected

These issues often aren't discovered until the model has been in production for months, causing business damage.

**The solution**: wicked-data provides senior ML engineering review:
- Systematic check of data handling, evaluation, and deployment readiness
- Data leakage detection (one of the most common and costly mistakes)
- Production readiness checklist
- Model card generation for documentation

**Business impact**:
- Catch critical issues before production deployment
- Reduce ML project failures from 85% to <30%
- Save 2-3 months of rework when issues found late
- Build organizational ML best practices

**Real-world example**: A retail company deployed a churn model that showed 92% accuracy in testing. After 3 months in production, they discovered it had data leakage and was actually performing at random chance level. wicked-data review would have caught this before deployment, saving $500K in misdirected retention spend.
