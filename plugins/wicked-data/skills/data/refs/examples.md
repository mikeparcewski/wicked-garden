# Data Engineering Examples

Detailed examples for data profiling, schema validation, and quality assessment.

## Profiling Output Example

```json
{
  "file": "sales.csv",
  "rows": 10000,
  "columns": 8,
  "schema": [
    {
      "name": "order_id",
      "type": "string",
      "null_rate": 0.0,
      "cardinality": 10000,
      "sample": ["ORD001", "ORD002", "ORD003"]
    },
    {
      "name": "amount",
      "type": "decimal",
      "null_rate": 0.02,
      "stats": {
        "min": 10.50,
        "max": 9999.99,
        "mean": 523.45,
        "median": 299.00
      }
    },
    {
      "name": "customer_id",
      "type": "integer",
      "null_rate": 0.0,
      "cardinality": 5000
    },
    {
      "name": "order_date",
      "type": "date",
      "null_rate": 0.0,
      "min": "2025-01-01",
      "max": "2025-12-31"
    }
  ],
  "quality_score": 95,
  "issues": [
    "Column 'email' has 2% null values"
  ]
}
```

## Schema Definition Example

```json
{
  "columns": [
    {
      "name": "user_id",
      "type": "integer",
      "nullable": false,
      "constraints": {
        "unique": true,
        "min": 1
      }
    },
    {
      "name": "email",
      "type": "string",
      "nullable": false,
      "constraints": {
        "pattern": "^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$"
      }
    },
    {
      "name": "created_at",
      "type": "datetime",
      "nullable": false
    },
    {
      "name": "status",
      "type": "string",
      "nullable": false,
      "constraints": {
        "enum": ["active", "inactive", "pending"]
      }
    },
    {
      "name": "balance",
      "type": "decimal",
      "nullable": true,
      "constraints": {
        "min": 0,
        "precision": 2
      }
    }
  ]
}
```

## Quality Report Example

```markdown
## Data Quality Report

**Dataset**: sales.csv
**Date**: 2026-01-24
**Rows**: 10,000

### Overall Score: 87/100

### Dimension Scores
| Dimension | Score | Status |
|-----------|-------|--------|
| Completeness | 95 | PASS |
| Uniqueness | 98 | PASS |
| Validity | 85 | WARNING |
| Consistency | 70 | FAIL |

### Critical Issues
1. **Validity**: 15% of 'phone' values don't match pattern
2. **Consistency**: 30% of records have order_date > ship_date

### Issue Details

#### Issue 1: Invalid Phone Format
- **Column**: phone
- **Pattern**: Expected `^\\+?[0-9]{10,14}$`
- **Violations**: 1,500 rows (15%)
- **Samples**: "123-456", "N/A", "(555)123-4567"
- **Root Cause**: No input validation at data entry

#### Issue 2: Date Consistency
- **Rule**: ship_date >= order_date
- **Violations**: 3,000 rows (30%)
- **Impact**: Analytics reports show negative fulfillment times
- **Root Cause**: Timezone mismatch between systems

### Recommendations
1. Add validation for phone format at source
2. Implement business rule: ship_date >= order_date
3. Standardize timezone handling

**Action Required**: Fix consistency issues before using for analytics
```

## Common Workflows

### New Dataset Analysis

1. **Profile** to understand structure
```bash
/wicked-data:data profile new_data.csv
```

2. **Validate** against expected schema (if available)
```bash
/wicked-data:data validate --schema expected.json --data new_data.csv
```

3. **Generate quality report**
```bash
/wicked-data:data quality new_data.csv
```

4. **Document issues** in kanban
```bash
/wicked-kanban:new-task "Data Quality: Fix phone format" --priority P1
```

5. **Recommend remediation** with specific actions

### Schema Migration

1. Profile source data
2. Design target schema based on profile
3. Validate sample data against target
4. Identify transformation requirements:
   - Type conversions
   - Null handling
   - Constraint additions
5. Document migration plan

### Quality Monitoring

1. Profile dataset regularly (daily/weekly)
2. Compare metrics over time
3. Alert on quality degradation:
   - Null rate increase >5%
   - New duplicate patterns
   - Type conformance drops
4. Track improvement initiatives in kanban

## SQL Quality Queries

```sql
-- Completeness check
SELECT
  column_name,
  COUNT(*) as total,
  SUM(CASE WHEN column_name IS NULL THEN 1 ELSE 0 END) as nulls,
  ROUND(100.0 * SUM(CASE WHEN column_name IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as null_pct
FROM data
GROUP BY ALL;

-- Uniqueness check
SELECT
  column_name,
  COUNT(*) as total,
  COUNT(DISTINCT column_name) as distinct_count,
  COUNT(*) - COUNT(DISTINCT column_name) as duplicates
FROM data
GROUP BY ALL;

-- Validity check (pattern matching)
SELECT
  COUNT(*) FILTER (WHERE email NOT LIKE '%@%.%') as invalid_emails
FROM data;

-- Consistency check (cross-field rules)
SELECT
  COUNT(*) FILTER (WHERE ship_date < order_date) as date_violations
FROM data;
```
