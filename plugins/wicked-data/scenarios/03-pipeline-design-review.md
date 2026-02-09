---
name: pipeline-design-review
title: ETL Pipeline Design and Review
description: Design a new data pipeline and review existing pipeline architecture
type: pipeline
difficulty: intermediate
estimated_minutes: 10
---

# ETL Pipeline Design and Review

Demonstrate the pipeline engineering capability by designing a new ETL pipeline and reviewing an existing one for best practices, performance, and reliability.

## Setup

Create a mock existing pipeline structure to review.

```bash
mkdir -p /tmp/pipelines/sales_etl

# Create a basic pipeline script
cat > /tmp/pipelines/sales_etl/extract.py << 'EOF'
import psycopg2
import pandas as pd

def extract_sales():
    conn = psycopg2.connect("postgresql://user:pass@localhost:5432/sales")
    df = pd.read_sql("SELECT * FROM orders", conn)
    df.to_csv("/tmp/sales_extract.csv", index=False)
    conn.close()
    return len(df)

if __name__ == "__main__":
    count = extract_sales()
    print(f"Extracted {count} rows")
EOF

# Create transform script
cat > /tmp/pipelines/sales_etl/transform.py << 'EOF'
import pandas as pd

def transform_sales():
    df = pd.read_csv("/tmp/sales_extract.csv")

    # Add calculated fields
    df['total_amount'] = df['quantity'] * df['unit_price']
    df['order_month'] = pd.to_datetime(df['order_date']).dt.to_period('M')

    # Remove nulls
    df = df.dropna()

    df.to_parquet("/tmp/sales_transformed.parquet")
    return len(df)

if __name__ == "__main__":
    count = transform_sales()
    print(f"Transformed {count} rows")
EOF

# Create load script
cat > /tmp/pipelines/sales_etl/load.py << 'EOF'
import pandas as pd
from google.cloud import bigquery

def load_to_bigquery():
    df = pd.read_parquet("/tmp/sales_transformed.parquet")

    client = bigquery.Client()
    table_id = "project.dataset.sales_fact"

    job = client.load_table_from_dataframe(df, table_id)
    job.result()

    return len(df)

if __name__ == "__main__":
    count = load_to_bigquery()
    print(f"Loaded {count} rows")
EOF

# Create a basic orchestration config
cat > /tmp/pipelines/sales_etl/pipeline.yaml << 'EOF'
name: sales_etl
schedule: "0 2 * * *"  # 2 AM daily
steps:
  - name: extract
    script: extract.py
  - name: transform
    script: transform.py
  - name: load
    script: load.py
EOF
```

## Steps

### 1. Review the existing pipeline

Ask for a pipeline review.

```
/wicked-data:pipeline review /tmp/pipelines/sales_etl/
```

Expected review should identify:

**Critical Issues (P1)**:
- Hardcoded credentials in extract.py
- No error handling or retries
- Full table extract (no incremental)
- No data validation between stages

**High Priority (P2)**:
- No logging or metrics
- Intermediate files not cleaned up
- No idempotency (rerun would duplicate)
- dropna() silently removes data

**Medium Priority (P3)**:
- No schema versioning
- Missing documentation
- No tests
- Single-threaded processing

### 2. Get specific recommendations

Ask for detailed fixes for the critical issues.

"How should I fix the credential management issue?"

Expected recommendations:
1. Use environment variables: `os.environ['DB_CONNECTION_STRING']`
2. Use a secrets manager (AWS Secrets Manager, HashiCorp Vault)
3. Never commit credentials to version control
4. Example code with secure pattern

### 3. Design a new pipeline

Request a pipeline design for a new use case.

"Design a data pipeline to load customer events from Kafka into Snowflake with hourly aggregations"

Expected design document:

```markdown
## Pipeline Design: Customer Events to Snowflake

### Architecture
- **Pattern**: Streaming ingestion with batch aggregation
- **Orchestration**: Airflow (recommended) or Dagster
- **Processing**: Spark Structured Streaming or Kafka Connect + dbt

### Data Flow
1. **Source**: Kafka topic `customer_events`
   - Format: JSON
   - Throughput: ~10K events/minute

2. **Ingestion**: Kafka Connect with Snowflake Sink
   - Micro-batch every 5 minutes
   - Landing table: `raw.customer_events`

3. **Transform**: dbt models
   - Staging: Parse JSON, add metadata
   - Intermediate: Sessionization, deduplication
   - Mart: Hourly aggregations

4. **Load**: Snowflake tables
   - `analytics.customer_events_hourly`
   - Partitioned by event_date

### Quality Gates
- **Ingestion**: Schema validation, null checks
- **Transform**: Row count assertions, freshness checks
- **Output**: Business rule validation

### Monitoring
- Kafka consumer lag
- Processing latency (target: <15 min)
- Row counts per batch
- Error rate by event type

### Estimated Costs
- Kafka: $500/month (managed)
- Snowflake: $800/month (XS warehouse)
- Total: ~$1,300/month for 10K events/min
```

### 4. Review the design for risks

"What are the risks with this design?"

Expected risk assessment:
1. **Kafka lag accumulation** - If consumer falls behind, backlog grows
2. **Snowflake costs** - Continuous loading can be expensive
3. **Late arriving data** - Events may arrive out of order
4. **Schema evolution** - Kafka schema changes break pipeline

### 5. Get incremental processing guidance

"How do I implement incremental loading for the original sales pipeline?"

Expected guidance:
```python
# Incremental extract pattern
def extract_sales_incremental(last_watermark):
    """Extract only new/changed records since last run."""
    query = """
        SELECT * FROM orders
        WHERE updated_at > %s
        ORDER BY updated_at
    """
    df = pd.read_sql(query, conn, params=[last_watermark])

    # Store new watermark
    new_watermark = df['updated_at'].max()
    save_watermark(new_watermark)

    return df
```

Plus recommendations:
- Add `updated_at` column if not present
- Use MERGE/UPSERT for idempotent loads
- Track watermarks in metadata table
- Handle deletes with soft delete or CDC

### 6. Request a pipeline checklist

"Give me a checklist for production-ready pipelines"

Expected checklist covering:
- [ ] No hardcoded credentials
- [ ] Error handling with retries
- [ ] Logging at each stage
- [ ] Data validation gates
- [ ] Idempotent operations
- [ ] Incremental processing
- [ ] Monitoring and alerting
- [ ] Documentation
- [ ] Tests (unit + integration)
- [ ] Backfill procedure documented

## Expected Outcome

- Existing pipeline thoroughly reviewed with prioritized findings
- Security issues prominently flagged
- New pipeline design follows best practices
- Risk assessment provides actionable mitigations
- Incremental patterns explained with code examples
- Production readiness checklist is comprehensive

## Success Criteria

- [ ] All security issues identified (credentials, no auth)
- [ ] Missing error handling flagged
- [ ] Lack of idempotency noted
- [ ] Silent data loss (dropna) caught
- [ ] New design includes all major components
- [ ] Cost estimates are reasonable
- [ ] Risk assessment covers operational concerns
- [ ] Incremental pattern code is correct
- [ ] Checklist covers critical production requirements

## Value Demonstrated

**The problem**: Data pipelines are deceptively simple to build but hard to run reliably. Most pipeline failures come from:
- Silent data quality issues
- Poor error handling
- Non-idempotent operations
- Missing monitoring

Teams discover these issues at 3 AM when the pipeline fails in production.

**The solution**: wicked-data provides experienced data engineering guidance:
- Security-first review catches credential issues
- Best practice checklist ensures nothing is missed
- Design patterns prevent common mistakes
- Risk assessment surfaces problems before production

**Business impact**:
- Reduce pipeline incidents by 60%
- Catch security issues before they become breaches
- Build reliable data infrastructure from day one
- Transfer senior engineering knowledge to the team

**Real-world example**: A retail company's "working" pipeline silently dropped 15% of orders due to null handling. wicked-data's review caught this pattern and similar issues, saving an estimated $50K in lost order data.
