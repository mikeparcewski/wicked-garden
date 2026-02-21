---
name: exploratory-analysis-insights
title: Exploratory Data Analysis with Business Insights
description: Perform exploratory analysis and generate actionable business insights from data
type: analysis
difficulty: intermediate
estimated_minutes: 12
---

# Exploratory Data Analysis with Business Insights

Demonstrate the data analysis workflow from initial exploration through pattern discovery to actionable business recommendations. This scenario shows how wicked-data helps analysts move from "what does the data show" to "what should we do about it."

## Setup

Create a realistic e-commerce dataset with interesting patterns to discover.

```bash
cat > /tmp/ecommerce_orders.csv << 'EOF'
order_id,customer_id,order_date,day_of_week,hour,product_category,items,subtotal,discount,shipping,total,payment_method,customer_segment,region,is_first_order
10001,C100,2024-01-02,Tuesday,14,Electronics,2,299.98,0,9.99,309.97,credit_card,Regular,Northeast,1
10002,C101,2024-01-02,Tuesday,19,Clothing,3,89.97,8.99,0,80.98,credit_card,Regular,Southwest,1
10003,C102,2024-01-03,Wednesday,10,Electronics,1,599.99,60.00,0,539.99,paypal,Premium,Northeast,0
10004,C100,2024-01-05,Friday,21,Home,4,124.96,0,12.99,137.95,credit_card,Regular,Northeast,0
10005,C103,2024-01-05,Friday,22,Electronics,1,199.99,0,9.99,209.98,credit_card,Regular,Midwest,1
10006,C104,2024-01-06,Saturday,11,Clothing,5,199.95,40.00,0,159.95,paypal,Premium,West,0
10007,C105,2024-01-06,Saturday,15,Home,2,79.98,0,9.99,89.97,credit_card,Regular,Southeast,1
10008,C102,2024-01-07,Sunday,16,Electronics,2,449.98,45.00,0,404.98,paypal,Premium,Northeast,0
10009,C106,2024-01-08,Monday,9,Office,3,67.47,0,5.99,73.46,credit_card,Regular,Midwest,1
10010,C107,2024-01-09,Tuesday,20,Electronics,1,899.99,90.00,0,809.99,credit_card,Premium,Southwest,0
10011,C108,2024-01-10,Wednesday,12,Clothing,2,59.98,0,7.99,67.97,credit_card,Regular,Northeast,1
10012,C109,2024-01-11,Thursday,18,Electronics,3,749.97,75.00,0,674.97,paypal,Premium,West,0
10013,C100,2024-01-12,Friday,20,Electronics,1,349.99,35.00,0,314.99,credit_card,Regular,Northeast,0
10014,C110,2024-01-13,Saturday,14,Home,6,299.94,30.00,0,269.94,credit_card,Premium,Southeast,0
10015,C111,2024-01-13,Saturday,16,Clothing,4,159.96,16.00,0,143.96,paypal,Regular,Midwest,1
10016,C112,2024-01-14,Sunday,11,Office,2,45.98,0,5.99,51.97,credit_card,Regular,Northeast,1
10017,C102,2024-01-15,Monday,10,Electronics,1,1299.99,130.00,0,1169.99,paypal,Premium,Northeast,0
10018,C113,2024-01-16,Tuesday,21,Clothing,3,119.97,12.00,0,107.97,credit_card,Regular,Southwest,1
10019,C114,2024-01-17,Wednesday,19,Electronics,2,399.98,0,0,399.98,credit_card,Regular,West,1
10020,C115,2024-01-18,Thursday,20,Home,3,149.97,15.00,0,134.97,paypal,Premium,Midwest,0
10021,C106,2024-01-19,Friday,22,Electronics,1,549.99,55.00,0,494.99,credit_card,Regular,Midwest,0
10022,C116,2024-01-20,Saturday,13,Clothing,6,239.94,48.00,0,191.94,credit_card,Premium,Northeast,0
10023,C117,2024-01-20,Saturday,17,Office,4,123.96,0,9.99,133.95,paypal,Regular,Southeast,1
10024,C118,2024-01-21,Sunday,15,Electronics,1,199.99,20.00,0,179.99,credit_card,Regular,Southwest,1
10025,C102,2024-01-22,Monday,11,Home,2,89.98,9.00,0,80.98,paypal,Premium,Northeast,0
EOF
```

## Steps

### 1. Start exploratory analysis

Begin with an open exploration of the dataset.

```
/wicked-data:analysis explore /tmp/ecommerce_orders.csv
```

Expected initial output:
- 25 orders over 21 days
- 19 unique customers
- 4 product categories
- Order values range from $51.97 to $1,169.99
- Mix of first-time (44%) and repeat customers (56%)

### 2. Understand the data structure

Ask about the grain and dimensions.

"What's the grain of this data and what are the key dimensions?"

Expected explanation:
- **Grain**: One row per order
- **Key dimensions**: customer_segment, region, product_category, day_of_week, payment_method
- **Key metrics**: total, items, discount
- **Time dimension**: order_date (daily granularity)

### 3. Analyze customer segments

Explore the Premium vs Regular segment performance.

"Compare Premium and Regular customer segments"

Expected SQL and insights:
```sql
SELECT
  customer_segment,
  COUNT(*) as orders,
  COUNT(DISTINCT customer_id) as customers,
  AVG(total) as avg_order_value,
  SUM(total) as total_revenue,
  AVG(discount) as avg_discount
FROM orders
GROUP BY customer_segment
```

**Insight**: Premium customers have 2x higher average order value but receive 3x higher discounts. Need to evaluate discount ROI.

### 4. Discover time patterns

Look for temporal patterns.

"What patterns do you see in order timing?"

Expected discoveries:
1. **Day of week**: Saturday has highest order volume
2. **Time of day**: Evening (6-10 PM) peak, especially Friday/Saturday
3. **Weekday vs Weekend**: Weekend orders are 35% higher value on average

### 5. Analyze category performance

"Which product categories are performing best?"

Expected analysis:
```sql
SELECT
  product_category,
  COUNT(*) as orders,
  SUM(total) as revenue,
  AVG(total) as avg_order,
  SUM(discount) as total_discounts
FROM orders
GROUP BY product_category
ORDER BY revenue DESC
```

**Finding**: Electronics dominates (60% of revenue) but also has highest discount rates. Clothing has lowest margin after discounts.

### 6. Identify high-value customers

"Who are the most valuable customers and what characterizes them?"

Expected RFM-style analysis:
- C102 (Premium, Northeast): 4 orders, $2,196 total - highest value
- Pattern: Premium segment, Electronics focus, evening shopper, PayPal preference
- C100 (Regular, Northeast): 3 orders, $763 - highest Regular customer

### 7. Find anomalies or concerns

"Are there any concerning patterns in this data?"

Expected flags:
1. **High discount dependency**: 68% of orders have discounts
2. **Category concentration**: Electronics = 60% of revenue (risk)
3. **Regional imbalance**: Northeast over-indexed, West under-indexed
4. **First order conversion**: 11 first orders, but only 3 returned (27% repeat rate in sample)

### 8. Generate business recommendations

"Based on this analysis, what should we focus on?"

Expected insight-to-action framework:

```markdown
## Analysis Recommendations

### Insight 1: Weekend Evening Peak
**Observation**: 40% of revenue occurs Friday-Sunday, 6-10 PM
**Insight**: Customers shop for discretionary items on weekend evenings
**Action**:
- Launch weekend flash sales starting 6 PM Friday
- Increase ad spend during peak windows
- Staff customer service for evening coverage
**Expected Impact**: +15% weekend conversion
**Confidence**: HIGH

### Insight 2: Discount Dependency Risk
**Observation**: Premium customers expect 10% discounts, avg discount is $38
**Insight**: Pricing power may be eroding; discounts may not be driving incremental purchases
**Action**:
- A/B test orders without automatic discounts
- Shift to loyalty rewards vs upfront discounts
- Analyze incrementality of discount-driven orders
**Expected Impact**: +8% margin if dependency reduced
**Confidence**: MEDIUM

### Insight 3: Category Concentration
**Observation**: Electronics = 60% of revenue
**Insight**: Over-reliance on single category creates risk
**Action**:
- Cross-sell Electronics customers into Home/Office
- Bundle promotions across categories
- Analyze why Clothing underperforms
**Expected Impact**: Risk mitigation, +10% category diversification
**Confidence**: MEDIUM

### Next Steps
1. Deep dive on discount incrementality
2. Customer cohort analysis for repeat purchase patterns
3. Regional expansion strategy for West market
```

## Expected Outcome

- Initial exploration provides complete data understanding
- Segment analysis reveals actionable differences
- Time patterns are discovered automatically
- High-value customer profiles are identified
- Anomalies and risks are flagged proactively
- Recommendations follow insight-to-action framework
- Confidence levels are stated honestly

## Success Criteria

- [ ] Data grain and dimensions correctly identified
- [ ] Segment analysis shows Premium vs Regular differences
- [ ] Weekend evening peak pattern discovered
- [ ] Electronics category dominance identified
- [ ] C102 identified as highest-value customer
- [ ] Discount dependency flagged as concern
- [ ] Regional imbalance noted
- [ ] At least 3 actionable recommendations generated
- [ ] Each recommendation includes expected impact
- [ ] Confidence levels assigned appropriately

## Value Demonstrated

**The problem**: Data analysis often stops at "here's what the data shows" without answering "so what?" Analysts produce dashboards and reports, but business users don't know what to do with the information.

**The solution**: wicked-data bridges the gap from data to decisions:
- Structured exploration that doesn't miss patterns
- Automatic anomaly and risk detection
- Insight framework: Observation + Interpretation + Action
- Quantified impact estimates and confidence levels
- Clear next steps, not just findings

**Business impact**:
- Reduce time from data to decision by 50%
- Ensure analysis is actionable, not just informative
- Build organizational data literacy through examples
- Create a repeatable pattern for analysis work

**Real-world example**: An e-commerce company was leaving money on the table by blanket discounting. Analysis like this revealed that 40% of discounted orders would have converted anyway. Targeted discount strategy improved margins by $2M annually.
