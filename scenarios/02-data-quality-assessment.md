---
name: data-quality-assessment
title: Data Quality Assessment and Validation
description: Assess data quality dimensions and validate against expected schemas
type: data
difficulty: intermediate
estimated_minutes: 8
---

# Data Quality Assessment and Validation

Demonstrate comprehensive data quality assessment including schema validation, completeness checks, and constraint validation. This is critical for data pipelines and ETL workflows.

## Setup

Create a dataset with intentional quality issues and an expected schema.

```bash
# Create a messy customer dataset
cat > /tmp/customers.csv << 'EOF'
customer_id,email,signup_date,country,age,lifetime_value,status
C001,john@example.com,2023-06-15,USA,34,1250.50,active
C002,invalid-email,2023-06-16,UK,28,890.00,active
C003,sarah@company.org,2023-06-17,USA,-5,2100.00,active
C004,mike@test.com,2023-06-18,Canada,45,,inactive
C005,lisa@example.com,2023-06-19,USA,150,450.00,active
C006,,2023-06-20,Germany,38,1100.00,active
C007,alex@domain.com,invalid-date,France,29,780.00,pending
C008,emma@test.org,2023-06-22,USA,41,3200.00,active
C009,chris@mail.com,2023-06-23,UK,33,920.00,ACTIVE
C010,pat@example.com,2023-06-24,USA,27,1500.00,active
C011,sam@test.com,2023-06-25,Canada,36,2800.00,active
C012,jordan@mail.org,2023-06-26,USA,44,,active
C001,duplicate@test.com,2023-06-27,USA,55,100.00,inactive
EOF

# Create an expected schema definition
cat > /tmp/customer_schema.json << 'EOF'
{
  "name": "customers",
  "version": "1.0",
  "columns": [
    {
      "name": "customer_id",
      "type": "string",
      "nullable": false,
      "constraints": {
        "unique": true,
        "pattern": "^C\\d{3}$"
      }
    },
    {
      "name": "email",
      "type": "string",
      "nullable": false,
      "constraints": {
        "pattern": "^[^@]+@[^@]+\\.[^@]+$"
      }
    },
    {
      "name": "signup_date",
      "type": "date",
      "nullable": false
    },
    {
      "name": "country",
      "type": "string",
      "nullable": false,
      "constraints": {
        "enum": ["USA", "UK", "Canada", "Germany", "France"]
      }
    },
    {
      "name": "age",
      "type": "integer",
      "nullable": false,
      "constraints": {
        "min": 18,
        "max": 120
      }
    },
    {
      "name": "lifetime_value",
      "type": "decimal",
      "nullable": true
    },
    {
      "name": "status",
      "type": "string",
      "nullable": false,
      "constraints": {
        "enum": ["active", "inactive", "pending"]
      }
    }
  ]
}
EOF
```

## Steps

### 1. Run initial data profiling

Start by understanding what's in the data.

```
/wicked-data:data profile /tmp/customers.csv
```

Expected: Profile shows column types, null rates, and cardinality.

### 2. Assess quality dimensions

Ask for a comprehensive quality assessment.

"Assess the data quality of this customer file across all dimensions"

Expected assessment should cover:
- **Completeness**: email missing 1 row, lifetime_value missing 2 rows
- **Validity**: Invalid email format, invalid date, invalid age values
- **Uniqueness**: customer_id C001 appears twice
- **Consistency**: status values have inconsistent case (ACTIVE vs active)

### 3. Run schema validation

Validate against the expected schema.

```
/wicked-data:data validate --schema /tmp/customer_schema.json --data /tmp/customers.csv
```

Expected violations:
- Row 2: email fails pattern validation
- Row 3: age=-5 below minimum (18)
- Row 5: age=150 above maximum (120)
- Row 6: email is null (not nullable)
- Row 7: signup_date is not a valid date
- Row 9: status='ACTIVE' not in enum
- Row 13: customer_id='C001' uniqueness violation

### 4. Generate quality report

Request a formal quality report.

"Generate a data quality report for this dataset"

Expected report format:
```markdown
## Data Quality Report: customers.csv

### Summary
- Total rows: 13
- Quality score: 65/100
- Critical issues: 7

### Quality Dimensions
| Dimension    | Score | Issues |
|--------------|-------|--------|
| Completeness | 85%   | 3 null values across 2 columns |
| Validity     | 70%   | 4 constraint violations |
| Uniqueness   | 92%   | 1 duplicate primary key |
| Consistency  | 90%   | 1 case inconsistency |

### Critical Issues (P1)
1. Duplicate customer_id: C001 appears twice
2. Invalid ages: -5 and 150 out of valid range

### High Priority (P2)
3. Invalid email format in row 2
4. Invalid date format in row 7
5. Null email in row 6

### Medium Priority (P3)
6. Inconsistent status case: ACTIVE vs active
7. Missing lifetime_value for 2 customers
```

### 5. Get remediation recommendations

Ask for specific fixes.

"How should I fix these data quality issues?"

Expected recommendations:
1. Deduplicate on customer_id (keep most recent or highest value)
2. Validate email format before ingestion
3. Add age range constraints (18-120) at source
4. Standardize status to lowercase
5. Decide on handling nulls: impute, flag, or reject

### 6. Verify fixes would work

Create a cleaned version to test.

"Show me SQL to clean this data"

Expected: System generates DuckDB SQL that:
- Removes duplicates (keep first occurrence)
- Filters invalid records
- Standardizes case
- Handles nulls appropriately

## Expected Outcome

- All quality dimensions are assessed systematically
- Schema validation identifies all constraint violations
- Issues are prioritized (P1/P2/P3) by severity
- Recommendations are specific and actionable
- System can generate remediation SQL

## Success Criteria

- [ ] Profile correctly identifies all column types
- [ ] Null rates calculated accurately (email: 7.7%, lifetime_value: 15.4%)
- [ ] Schema validation catches all 7 violations
- [ ] Duplicate customer_id detected
- [ ] Invalid email pattern detected
- [ ] Out-of-range ages (negative and >120) flagged
- [ ] Case inconsistency in status identified
- [ ] Quality score reflects actual issues
- [ ] Remediation recommendations are actionable

## Value Demonstrated

**The problem**: Data quality issues propagate through systems. An invalid email doesn't just fail validation - it breaks downstream marketing campaigns, corrupts analytics, and erodes trust in data. Teams spend days hunting down quality issues reactively.

**The solution**: wicked-data provides proactive quality assessment:
- Multi-dimensional quality checks (not just null counts)
- Schema validation with custom constraints
- Prioritized issues with business impact context
- Remediation guidance, not just problem identification

**Business impact**:
- Catch issues before they enter the data warehouse
- Reduce data incident response time by 70%
- Build confidence in data-driven decisions
- Create a quality gate for data pipelines

**Real-world example**: A financial services company found that 15% of their customer records had invalid data. Without systematic quality assessment, this went undetected for months, causing $200K in failed marketing campaigns and compliance issues.
