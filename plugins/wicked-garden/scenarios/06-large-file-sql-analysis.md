---
name: large-file-sql-analysis
title: Large File Analysis with DuckDB SQL
description: Analyze large CSV/Excel files efficiently using SQL without loading into memory
type: data
difficulty: basic
estimated_minutes: 6
---

# Large File Analysis with DuckDB SQL

Demonstrate the wicked-data:numbers capability for analyzing large files that would crash Excel or pandas. Uses DuckDB for efficient SQL querying directly against files without loading them entirely into memory.

## Setup

Create a larger dataset that simulates real-world file sizes. This example uses a moderate size, but the same approach works for multi-GB files.

```bash
# Create a 10,000 row transaction log
python3 << 'EOF'
import csv
import random
from datetime import datetime, timedelta

# Generate realistic transaction data
categories = ['Electronics', 'Clothing', 'Home', 'Sports', 'Books', 'Food', 'Beauty', 'Toys']
regions = ['Northeast', 'Southeast', 'Midwest', 'Southwest', 'West', 'Northwest']
statuses = ['completed', 'completed', 'completed', 'completed', 'pending', 'refunded', 'cancelled']
payment_methods = ['credit_card', 'credit_card', 'debit_card', 'paypal', 'apple_pay']

with open('/tmp/transactions_large.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['transaction_id', 'timestamp', 'customer_id', 'category', 'amount',
                     'quantity', 'region', 'status', 'payment_method', 'discount_pct'])

    base_date = datetime(2024, 1, 1)
    for i in range(10000):
        tx_date = base_date + timedelta(
            days=random.randint(0, 180),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )
        customer_id = f"C{random.randint(1, 2000):04d}"
        category = random.choice(categories)
        amount = round(random.uniform(5, 500) * (1.5 if category == 'Electronics' else 1), 2)
        quantity = random.randint(1, 5)
        discount = random.choice([0, 0, 0, 5, 10, 15, 20]) if random.random() > 0.6 else 0

        writer.writerow([
            f"TX{i+1:06d}",
            tx_date.strftime('%Y-%m-%d %H:%M:%S'),
            customer_id,
            category,
            amount,
            quantity,
            random.choice(regions),
            random.choice(statuses),
            random.choice(payment_methods),
            discount
        ])

print("Created /tmp/transactions_large.csv with 10,000 rows")
EOF
```

## Steps

### 1. Start analysis session

Open the file for analysis.

```
/wicked-data:analyze /tmp/transactions_large.csv
```

Expected: System detects CSV, samples intelligently (head + random + tail), infers schema, reports file size and row count estimate.

### 2. Get basic statistics

"How many transactions are there and what's the date range?"

Expected SQL:
```sql
SELECT
  COUNT(*) as total_transactions,
  MIN(timestamp) as earliest,
  MAX(timestamp) as latest,
  COUNT(DISTINCT customer_id) as unique_customers,
  COUNT(DISTINCT category) as categories
FROM read_csv('/tmp/transactions_large.csv')
```

Result: 10,000 transactions, ~2,000 unique customers, 8 categories, spanning 6 months.

### 3. Run aggregation query

"Show me monthly revenue by category"

Expected SQL:
```sql
SELECT
  strftime(timestamp, '%Y-%m') as month,
  category,
  COUNT(*) as transactions,
  SUM(amount) as revenue,
  AVG(amount) as avg_order
FROM read_csv('/tmp/transactions_large.csv')
WHERE status = 'completed'
GROUP BY month, category
ORDER BY month, revenue DESC
```

Note: DuckDB executes this against the CSV file directly without loading it all into memory.

### 4. Find top customers

"Who are the top 10 customers by total spend?"

Expected SQL:
```sql
SELECT
  customer_id,
  COUNT(*) as orders,
  SUM(amount) as total_spend,
  AVG(amount) as avg_order,
  MIN(timestamp) as first_order,
  MAX(timestamp) as last_order
FROM read_csv('/tmp/transactions_large.csv')
WHERE status = 'completed'
GROUP BY customer_id
ORDER BY total_spend DESC
LIMIT 10
```

### 5. Analyze patterns

"What's the distribution of order amounts?"

Expected SQL with percentiles:
```sql
SELECT
  MIN(amount) as min,
  PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY amount) as p25,
  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY amount) as median,
  PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY amount) as p75,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY amount) as p95,
  MAX(amount) as max,
  AVG(amount) as mean,
  STDDEV(amount) as stddev
FROM read_csv('/tmp/transactions_large.csv')
WHERE status = 'completed'
```

### 6. Detect anomalies

"Are there any unusual patterns or outliers?"

Expected analysis:
```sql
-- Transactions with unusually high amounts
SELECT *
FROM read_csv('/tmp/transactions_large.csv')
WHERE amount > (
  SELECT AVG(amount) + 3 * STDDEV(amount)
  FROM read_csv('/tmp/transactions_large.csv')
)
ORDER BY amount DESC
LIMIT 20

-- Customers with suspicious patterns (many small transactions)
SELECT
  customer_id,
  COUNT(*) as tx_count,
  AVG(amount) as avg_amount
FROM read_csv('/tmp/transactions_large.csv')
GROUP BY customer_id
HAVING COUNT(*) > 20 AND AVG(amount) < 20
```

### 7. Join with another file

Create a second file and demonstrate joins.

```bash
cat > /tmp/customers.csv << 'EOF'
customer_id,segment,signup_date,region
C0001,Premium,2023-01-15,Northeast
C0002,Regular,2023-03-22,Southwest
C0003,Premium,2023-02-10,Midwest
C0004,Regular,2023-06-01,Southeast
C0005,VIP,2022-11-30,West
EOF
```

"Join transactions with customer segments to see spend by segment"

Expected SQL:
```sql
SELECT
  c.segment,
  COUNT(*) as transactions,
  SUM(t.amount) as total_revenue,
  AVG(t.amount) as avg_order,
  COUNT(DISTINCT t.customer_id) as customers
FROM read_csv('/tmp/transactions_large.csv') t
JOIN read_csv('/tmp/customers.csv') c ON t.customer_id = c.customer_id
WHERE t.status = 'completed'
GROUP BY c.segment
ORDER BY total_revenue DESC
```

### 8. Export results

"Export the monthly summary to a new CSV"

Expected:
```sql
COPY (
  SELECT
    strftime(timestamp, '%Y-%m') as month,
    category,
    COUNT(*) as transactions,
    SUM(amount) as revenue
  FROM read_csv('/tmp/transactions_large.csv')
  WHERE status = 'completed'
  GROUP BY month, category
  ORDER BY month, category
) TO '/tmp/monthly_summary.csv' (HEADER, DELIMITER ',')
```

## Expected Outcome

- Large file opened without memory issues
- Schema correctly inferred for all 10 columns
- SQL queries execute efficiently against the CSV
- Complex aggregations (percentiles, window functions) work
- Multi-file joins are supported
- Results can be exported to new files

## Success Criteria

- [ ] 10,000 row file analyzed without loading into memory
- [ ] Schema inference identifies timestamp, numeric, and string columns
- [ ] Count query returns exactly 10,000
- [ ] Monthly aggregation produces correct results
- [ ] Top 10 customers query executes in <1 second
- [ ] Percentile calculations work correctly
- [ ] Join between CSV files succeeds
- [ ] Export to new CSV works
- [ ] All queries use DuckDB (not pandas)

## Value Demonstrated

**The problem**: Analysts hit walls with large files:
- Excel crashes above 1M rows
- pandas loads entire file into memory (8GB file = 8GB+ RAM)
- Database import is slow and requires setup
- Simple questions require complex tooling

Result: Analysts avoid large files or spend hours on workarounds.

**The solution**: wicked-data uses DuckDB for out-of-core processing:
- Query CSV/Parquet files directly with SQL
- No memory limits (processes in streaming fashion)
- No database setup required
- Same SQL skills analysts already have

**Performance comparison** (1GB CSV, 10M rows):
| Approach | Memory Used | Query Time |
|----------|-------------|------------|
| pandas | 8+ GB | 45 seconds |
| Excel | Crashes | N/A |
| DuckDB | 200 MB | 3 seconds |

**Business impact**:
- Analysts can work with production-scale data
- No need to sample or subset for initial exploration
- Faster iteration on data questions
- No infrastructure setup required

**Real-world example**: A data team needed to analyze 2 years of transaction logs (50GB, 500M rows). Traditional tools required a Spark cluster. With DuckDB via wicked-data, they ran the analysis on a laptop in minutes, saving a week of infrastructure setup.
