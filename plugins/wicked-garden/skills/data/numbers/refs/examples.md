# Examples and SQL Patterns

Detailed examples and SQL query patterns for data analysis.

## SQL Querying

Uses DuckDB to query files directly:

```sql
-- Single file
SELECT * FROM 'sales.csv' LIMIT 10

-- Aggregation
SELECT product, SUM(amount) as total
FROM 'sales.csv'
GROUP BY product

-- Join files
SELECT s.*, c.name
FROM 'sales.csv' s
JOIN 'customers.csv' c ON s.customer_id = c.id
```

## Example Workflows

### Basic Analysis

```
User: /wicked-garden:data-numbers ./sales_2024.csv

Claude: [Displays schema, hints, sample data]

User: What's the total revenue by product category?

Claude: [Generates SQL, executes, shows results table]
```

### Multi-File Join

```
User: /wicked-garden:data-numbers ./orders.csv
User: /wicked-garden:data-numbers ./customers.csv

User: Show me total orders per customer with their names

Claude: [Joins the two files, aggregates, shows results]
```

### Data Quality Check

```
User: /wicked-garden:data-numbers ./data.csv

Claude: [Shows hints about null values, duplicates]

User: Are there any duplicate order IDs?

Claude: [Runs COUNT(*) GROUP BY HAVING COUNT(*) > 1]
```

## Common Query Patterns

### Aggregations
```sql
-- Group by with counts
SELECT category, COUNT(*) as count, AVG(price) as avg_price
FROM 'products.csv'
GROUP BY category
ORDER BY count DESC

-- Time-based aggregation
SELECT DATE_TRUNC('month', order_date) as month, SUM(total) as revenue
FROM 'orders.csv'
GROUP BY 1
ORDER BY 1
```

### Data Quality
```sql
-- Find nulls
SELECT column_name, COUNT(*) - COUNT(column_name) as null_count
FROM 'data.csv'

-- Find duplicates
SELECT id, COUNT(*) as occurrences
FROM 'data.csv'
GROUP BY id
HAVING COUNT(*) > 1
```

### Joins
```sql
-- Inner join
SELECT o.*, c.name, c.email
FROM 'orders.csv' o
JOIN 'customers.csv' c ON o.customer_id = c.id

-- Left join with nulls
SELECT c.*, COUNT(o.id) as order_count
FROM 'customers.csv' c
LEFT JOIN 'orders.csv' o ON c.id = o.customer_id
GROUP BY c.id
```
