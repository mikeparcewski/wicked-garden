# Persona Details

Detailed configuration and generation patterns for report personas.

## Persona Configuration Pattern

```python
# Generate personas via utils skill
default_types = ["delivery-lead", "engineering-lead", "product-lead"]
all_types = default_types + ["qe-lead", "architecture-lead", "devsecops-lead"]

# Each persona includes:
persona = {
    "identifier": "delivery-lead",
    "name": "Delivery Lead",
    "mindset": "Focus on timeline, velocity, predictability",
    "priorities": ["blockers", "milestones", "capacity"],
    "metrics": {
        "primary": ["sprint_velocity", "blocked_items", "cycle_time"],
        "secondary": ["carryover_rate", "capacity_utilization"]
    },
    "report_emphasis": ["Sprint status", "Velocity trends", "Risk assessment"]
}
```

## Persona Generation

Generates specialized reviewer personas with:
- Role-specific mindsets and priorities
- Relevant metrics and focus areas
- Communication styles appropriate to the perspective
- Report emphasis tailored to stakeholder needs

## Data Sources

Supports multiple data input formats via wicked-garden:data
- **CSV exports**: Standard comma-separated values from project management tools
- **Excel files**: XLSX/XLS spreadsheets with project data

Auto-detects exports from:
- Jira (standard or custom fields)
- GitHub Issues
- Linear
- Asana
- Azure DevOps

## Dependencies

Requires:
- **wicked-data**: Data sampling, schema detection, SQL queries

Optional:
- **wicked-cache**: Cache API for result persistence (namespace: "delivery")
- **wicked-mem**: Memory storage for cross-session insights

## Workflow

1. **Pre-flight**: Validate dependencies and input file
2. **Data Ingestion**: Load via wicked-data
3. **Column Detection**: Auto-detect field meanings
4. **Persona Selection**: Generate personas via utils skill
5. **Analysis**: Run persona-specific queries
6. **Report Generation**: Create markdown reports per perspective
7. **Caching**: Store results in wicked-mem
8. **Output**: Write reports with manifest
