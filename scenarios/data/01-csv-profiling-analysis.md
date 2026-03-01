---
name: csv-profiling-analysis
title: CSV Data Profiling and Analysis
description: Profile a CSV dataset to understand structure, quality, and generate initial insights
type: data
difficulty: basic
estimated_minutes: 5
---

# CSV Data Profiling and Analysis

Demonstrate the core data profiling capability using a realistic sales dataset. This is the most common entry point for data analysis work.

## Setup

Create a sample sales CSV file with realistic data patterns and quality issues.

```bash
cat > /tmp/sales_data.csv << 'EOF'
order_id,customer_id,product_name,category,quantity,unit_price,order_date,region,status
1001,C001,Widget Pro,Electronics,2,49.99,2024-01-15,Northeast,completed
1002,C002,Basic Widget,Electronics,1,29.99,2024-01-16,Southwest,completed
1003,C001,Premium Cable,Accessories,3,12.99,2024-01-16,Northeast,completed
1004,C003,Widget Pro,Electronics,1,49.99,2024-01-17,Midwest,pending
1005,C004,Basic Widget,Electronics,5,29.99,2024-01-18,Southeast,completed
1006,C002,Widget Pro,Electronics,1,49.99,2024-01-19,Southwest,cancelled
1007,C005,Super Widget,Electronics,2,79.99,2024-01-20,Northeast,completed
1008,C001,Premium Cable,Accessories,,12.99,2024-01-21,Northeast,completed
1009,C006,Basic Widget,Electronics,3,29.99,2024-01-22,West,completed
1010,C007,Widget Pro,Electronics,1,49.99,2024-01-23,,pending
1011,C008,Economy Pack,Bundles,2,99.99,2024-01-24,Southeast,completed
1012,C003,Super Widget,Electronics,1,79.99,2024-01-25,Midwest,completed
1013,C009,Premium Cable,Accessories,4,12.99,2024-01-26,Northeast,completed
1014,C010,Widget Pro,Electronics,2,49.99,2024-01-27,Southwest,completed
1015,C001,Basic Widget,Electronics,1,29.99,2024-01-28,Northeast,completed
EOF
```

## Steps

### 1. Start data analysis session

Use the analyze command to profile the CSV file.

```
/wicked-data:analyze /tmp/sales_data.csv
```

Expected: System detects the file, samples rows, infers schema, and displays initial analysis.

### 2. Review the schema inference

Verify the system correctly identifies:
- `order_id`: integer (unique identifier candidate)
- `customer_id`: string
- `product_name`: string (categorical)
- `category`: string (categorical, low cardinality)
- `quantity`: integer (with one null value)
- `unit_price`: decimal
- `order_date`: date
- `region`: string (categorical, one null)
- `status`: string (categorical: completed, pending, cancelled)

### 3. Ask about data quality

Ask natural language questions about the data quality.

"What data quality issues are in this file?"

Expected: System identifies:
- Row 8 has null quantity
- Row 10 has null region
- Overall null rate is low (<1%)

### 4. Generate basic statistics

Ask for summary statistics.

"Show me the sales summary by category"

Expected: System generates SQL like:
```sql
SELECT
  category,
  COUNT(*) as order_count,
  SUM(quantity * unit_price) as total_revenue,
  AVG(unit_price) as avg_price
FROM read_csv('/tmp/sales_data.csv')
WHERE quantity IS NOT NULL
GROUP BY category
ORDER BY total_revenue DESC
```

### 5. Explore patterns

Ask questions to explore the data.

"Which customer has the most orders?"

Expected: System identifies C001 as the top customer with 4 orders.

### 6. Check date distribution

"What's the date range and are there any gaps?"

Expected: System reports:
- Date range: 2024-01-15 to 2024-01-28
- Continuous daily orders (no gaps in this sample)

## Expected Outcome

- File is detected and profiled without loading entirely into memory
- Schema is correctly inferred for all columns
- Data quality issues (nulls) are identified
- Natural language questions are translated to SQL
- Aggregations and groupings work correctly
- System provides actionable insights, not just raw numbers

## Success Criteria

- [ ] File type detected as CSV
- [ ] All 9 columns identified with correct types
- [ ] Null values in quantity and region columns flagged
- [ ] Categorical columns identified (category, status, region)
- [ ] Unique identifier candidate (order_id) suggested
- [ ] SQL queries execute successfully via DuckDB
- [ ] Summary statistics are accurate
- [ ] No memory issues with file loading

## Value Demonstrated

**The problem**: Data analysts spend 30-40% of their time just understanding and cleaning data before they can do actual analysis. For every new dataset, they manually:
- Open in Excel/pandas to see structure
- Write repetitive profiling code
- Hunt for quality issues
- Guess at data types

**The solution**: wicked-data automates the exploration phase:
- Instant schema detection
- Automatic quality assessment
- Natural language to SQL for exploration
- DuckDB for efficient large file handling

**Time savings**: What takes 30 minutes manually takes 5 minutes with wicked-data. For teams working with 10+ datasets per week, this adds up to hours saved.
