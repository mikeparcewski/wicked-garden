# Capability-Based Discovery Patterns

How wicked-delivery discovers and integrates with cloud cost tools at runtime.

## Discovery Philosophy

wicked-delivery uses **pure capability-based discovery** without hardcoded provider names. This means:

1. **No assumptions**: Don't assume specific providers or tools
2. **Runtime detection**: Check what capabilities exist when invoked
3. **Graceful degradation**: Work with what's available, prompt for what's missing
4. **Extensible**: New tools work automatically if they expose standard capabilities
5. **Provider agnostic**: Works with ANY cloud provider that exposes cost data

## Discovery Pattern

### 1. Define Capability Categories

```yaml
# Pure capability-based categories
capabilities:
  cloud_cost:
    description: "Cloud provider billing and cost data"
    provides:
      - service_level_costs
      - cost_allocation_tags
      - time_series_data
      - usage_metrics

  kubernetes_cost:
    description: "Container-level cost allocation"
    provides:
      - pod_costs
      - namespace_costs
      - efficiency_metrics
      - resource_allocation

  multi_cloud_cost:
    description: "Unified cost aggregation across providers"
    provides:
      - normalized_reporting
      - cross_provider_analytics
      - unified_dashboards
      - recommendation_engine

  infrastructure_cost:
    description: "IaC-based cost estimation"
    provides:
      - resource_definitions
      - cost_modeling
      - what_if_scenarios
      - drift_detection

  cost_optimization:
    description: "Cost optimization recommendations"
    provides:
      - rightsizing_analysis
      - reservation_recommendations
      - waste_detection
      - efficiency_scoring
```

### 2. Discovery Logic

```python
def discover_cost_capabilities():
    """
    Pure capability-based discovery - no provider names
    """
    available = []

    # Check for cloud cost capability
    if has_capability("cloud-cost"):
        available.append({
            'capability': 'cloud-cost',
            'provides': ['billing_data', 'service_costs', 'tags'],
            'confidence': 'high'
        })

    # Check for kubernetes cost capability
    if has_capability("kubernetes-cost"):
        available.append({
            'capability': 'kubernetes-cost',
            'provides': ['pod_costs', 'namespace_costs'],
            'confidence': 'high'
        })

    # Check for multi-cloud aggregation
    if has_capability("multi-cloud-cost"):
        available.append({
            'capability': 'multi-cloud-cost',
            'provides': ['unified_view', 'cross_provider'],
            'confidence': 'high'
        })

    # Fallback to IaC modeling
    if not available and has_capability("infrastructure-cost"):
        available.append({
            'capability': 'infrastructure-cost',
            'provides': ['cost_estimation', 'modeling'],
            'confidence': 'medium'
        })

    return available
```

### 3. Fallback Hierarchy

```
Priority 1: cloud-cost capability
└─ Direct cloud provider billing APIs
   Provides: Real billing data, usage metrics, cost allocation

Priority 2: multi-cloud-cost capability
└─ Unified multi-cloud cost platforms
   Provides: Aggregated view, cross-provider analytics

Priority 3: kubernetes-cost capability
└─ Container cost allocation tools
   Provides: K8s-specific cost data

Priority 4: infrastructure-cost capability
└─ IaC-based cost estimation
   Provides: Modeled costs, what-if scenarios

Priority 5: Manual input
└─ Prompt user for cost data
   Provides: User-supplied estimates
```

## cloud-cost Capability

### What It Provides

The `cloud-cost` capability indicates a tool can provide cloud provider billing and cost data.

**Standard Data Points**:
- Service-level cost breakdown
- Cost allocation via tags/labels
- Time-series cost data
- Usage metrics
- Reserved capacity utilization
- Cost projections

**Detection Pattern**:
```bash
# Query for cloud-cost capability
if tool_has_capability("cloud-cost"); then
  # Use this tool for billing data
fi
```

**Example Query**:
```bash
# Generic capability-based query
get-cost-data \
  --time-period "2025-01-01 to 2025-01-31" \
  --granularity "monthly" \
  --group-by "service"
```

**Standard Response Format**:
```json
{
  "period": {"start": "2025-01-01", "end": "2025-01-31"},
  "costs": [
    {
      "service": "compute",
      "amount": 1234.56,
      "currency": "USD",
      "breakdown": {...}
    }
  ]
}
```

### Granularity Levels

**High granularity**: Resource-level costs, hourly data
**Medium granularity**: Service-level costs, daily data
**Low granularity**: Account-level totals, monthly data

## kubernetes-cost Capability

### What It Provides

The `kubernetes-cost` capability indicates a tool can provide container-level cost allocation.

**Standard Data Points**:
- Pod-level costs
- Namespace costs
- Container efficiency metrics
- Resource allocation vs usage
- Cluster cost breakdown

**Detection Pattern**:
```bash
# Query for kubernetes-cost capability
if tool_has_capability("kubernetes-cost"); then
  # Use this tool for K8s cost data
fi
```

**Example Query**:
```bash
# Generic capability-based query
get-kubernetes-costs \
  --namespace "production" \
  --time-period "last-7-days"
```

**Standard Response Format**:
```json
{
  "cluster": "production-cluster",
  "namespace": "production",
  "pods": [
    {
      "name": "app-pod-1",
      "cpu_cost": 12.34,
      "memory_cost": 5.67,
      "total_cost": 18.01
    }
  ]
}
```

## multi-cloud-cost Capability

### What It Provides

The `multi-cloud-cost` capability indicates a tool can aggregate costs across multiple cloud providers.

**Standard Data Points**:
- Unified cost view across providers
- Normalized reporting format
- Cross-provider cost analytics
- Recommendation engine
- Custom allocation rules

**Detection Pattern**:
```bash
# Query for multi-cloud-cost capability
if tool_has_capability("multi-cloud-cost"); then
  # Use this tool for unified view
fi
```

**Example Query**:
```bash
# Generic capability-based query
get-multi-cloud-costs \
  --all-providers \
  --time-period "this-month"
```

**Standard Response Format**:
```json
{
  "total_cost": 50000.00,
  "providers": [
    {
      "provider": "provider-a",
      "cost": 30000.00,
      "services": [...]
    },
    {
      "provider": "provider-b",
      "cost": 20000.00,
      "services": [...]
    }
  ]
}
```

## infrastructure-cost Capability

### What It Provides

The `infrastructure-cost` capability indicates a tool can estimate costs from infrastructure definitions.

**Standard Data Points**:
- Resource configuration analysis
- Cost estimation (not actual billing)
- What-if scenario modeling
- Change impact assessment
- Drift detection

**Detection Pattern**:
```bash
# Query for infrastructure-cost capability
if tool_has_capability("infrastructure-cost"); then
  # Use this tool for cost modeling
fi
```

**Example Query**:
```bash
# Generic capability-based query
estimate-infrastructure-costs \
  --config-path "./infrastructure" \
  --show-breakdown
```

**Standard Response Format**:
```json
{
  "estimated_monthly_cost": 5000.00,
  "confidence": "medium",
  "resources": [
    {
      "type": "compute-instance",
      "count": 10,
      "unit_cost": 50.00,
      "total_cost": 500.00
    }
  ],
  "note": "Estimates based on resource specs, not actual usage"
}
```

### Use Cases

- **Planning**: Estimate costs before deployment
- **What-if**: Model architecture changes
- **Fallback**: When no billing API available

## cost-optimization Capability

### What It Provides

The `cost-optimization` capability indicates a tool can provide optimization recommendations.

**Standard Data Points**:
- Right-sizing recommendations
- Reserved capacity opportunities
- Spot instance candidates
- Waste detection
- Efficiency scoring

**Detection Pattern**:
```bash
# Query for cost-optimization capability
if tool_has_capability("cost-optimization"); then
  # Use this tool for recommendations
fi
```

**Example Query**:
```bash
# Generic capability-based query
get-optimization-recommendations \
  --focus "quick-wins" \
  --min-savings 100
```

**Standard Response Format**:
```json
{
  "total_savings": 2500.00,
  "recommendations": [
    {
      "type": "rightsizing",
      "resource": "instance-123",
      "current_cost": 200.00,
      "recommended_cost": 100.00,
      "savings": 100.00,
      "confidence": "high"
    }
  ]
}
```

## Discovery in Action

### Example: Cost Analysis Flow

```markdown
User: "Analyze our cloud costs"

1. Discovery Phase:
   ✓ Checking for cloud-cost capability... FOUND
   ✓ Checking for kubernetes-cost capability... FOUND
   ✓ Checking for multi-cloud-cost capability... NOT FOUND

2. Data Collection:
   → Using cloud-cost capability for billing data
   → Using kubernetes-cost for container costs
   → Querying last 30 days of costs
   → Retrieving service breakdown and allocation tags

3. Analysis:
   → Service costs from cloud-cost provider
   → Container costs from kubernetes-cost provider
   → Tag-based allocation (Team, Project, Environment)
   → Anomaly detection on trends

4. Output:
   → Full cost breakdown with real data
   → Container efficiency analysis
   → Recommendations based on actual usage
```

### Example: Fallback to IaC

```markdown
User: "Estimate costs for this architecture"

1. Discovery Phase:
   ✗ No cloud-cost capability available
   ✗ No multi-cloud-cost capability available
   ✓ Checking for infrastructure-cost capability... FOUND

2. Data Collection:
   → Using infrastructure-cost for modeling
   → Extracting resource configurations
   → Analyzing compute, storage, network specs

3. Cost Modeling:
   → Compute instances: 10 units @ $50/mo = ~$500/mo
   → Database: 1 unit @ $350/mo = ~$350/mo
   → Storage: 1TB = ~$23/mo

4. Output:
   → Estimated costs based on resource specs
   → Note: "Estimates only - actual costs may vary based on usage"
   → Confidence level: MEDIUM
```

## Integration with wicked-* Ecosystem

### wicked-search

**Use**: Find resource configurations in codebase

```bash
wicked-search "instance_type" --type tf
# → Find all Terraform instance definitions
```

### wicked-mem

**Use**: Store and recall historical cost data

```bash
wicked-mem store "finops/monthly-costs/2025-01" --data "{...}"
wicked-mem recall "finops/monthly-costs/*" --limit 12
```

## Best Practices

1. **Check, don't assume**: Always discover available capabilities
2. **Communicate clearly**: Tell user what data sources you're using
3. **Graceful degradation**: Work with what's available
4. **Prompt when needed**: Ask for data if no tools found
5. **Document limitations**: Be clear about estimates vs actuals

## Error Handling

```python
def get_cost_data():
    """
    Robust cost data retrieval with capability-based fallbacks
    """
    try:
        # Try cloud-cost capability
        return get_cloud_cost_data()
    except NotAvailableError:
        try:
            # Try multi-cloud-cost capability
            return get_multi_cloud_cost_data()
        except NotAvailableError:
            try:
                # Try infrastructure-cost capability
                return estimate_from_infrastructure()
            except NotAvailableError:
                # Prompt user
                return prompt_for_cost_data()
```

## Future Extensibility

New cost tools work automatically if they expose standard capabilities:

1. **Declare capability**: Advertise what capability they provide
2. **Standard interface**: Respond to capability queries
3. **Standard format**: Return data in expected structure
4. **Provider agnostic**: No hardcoded provider assumptions

### Examples

**Example 1**: A new cloud provider's billing tool
```yaml
capability: cloud-cost
provides:
  - service_level_costs
  - cost_allocation
  - time_series
```
→ Works immediately with wicked-delivery

**Example 2**: A new container cost tool
```yaml
capability: kubernetes-cost
provides:
  - pod_costs
  - namespace_allocation
```
→ Works immediately with wicked-delivery

**Example 3**: A new multi-cloud platform
```yaml
capability: multi-cloud-cost
provides:
  - unified_view
  - cross_provider_analytics
```
→ Works immediately with wicked-delivery

The key principle: **Capabilities, not names**. Ask "Do I have cloud-cost capability?" not "Do I have AWS Cost Explorer?"
