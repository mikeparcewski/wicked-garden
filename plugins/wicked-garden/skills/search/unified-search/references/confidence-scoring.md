# Confidence Scoring Guide

This document explains how wicked-search assigns confidence levels to cross-reference relationships.

## Confidence Levels

| Level | Value | Meaning |
|-------|-------|---------|
| HIGH | `high` | Direct annotation or explicit mapping found |
| MEDIUM | `medium` | Naming convention match or partial evidence |
| LOW | `low` | Single weak indicator |
| INFERRED | `inferred` | Guessed from context, least reliable |

## When Each Level Is Used

### HIGH Confidence

Applied when explicit code annotations provide direct evidence:

```java
// @Column with explicit name = HIGH
@Column(name = "FIRST_NAME")
private String firstName;

// @JoinColumn = HIGH
@JoinColumn(name = "DEPT_ID", referencedColumnName = "ID")
private Department department;

// EL expression with commandName match = HIGH
<form:input path="firstName" />  // matches ${person.firstName}
```

### MEDIUM Confidence

Applied when naming conventions align but no explicit annotation:

```java
// @Id without @Column = MEDIUM (JPA defaults to field name)
@Id
private Long id;

// Form binding with partial property match = MEDIUM
<form:input path="address.city" />  // nested property
```

### LOW Confidence

Applied when only indirect or weak evidence exists:

```java
// Controller naming convention match = LOW
PersonController -> person/*.jsp  // matched by naming convention only

// Property used in JSP but source unclear = LOW
${unknownVar.property}  // no clear model attribute binding
```

### INFERRED Confidence

Applied when guessing from context without direct evidence:

```java
// No @Column annotation, using field name as column = INFERRED
private String lastName;  // assumes column is "lastName"

// EL path resolved through method chain = INFERRED
${user.profile.settings.theme}  // multi-hop traversal
```

## Using Confidence in Queries

### Filter by Confidence

```bash
# Only show high-confidence references
/wicked-garden:search-blast-radius Person --min-confidence high

# Include medium and above
/wicked-garden:search-refs PersonEntity.firstName --min-confidence medium
```

### In Code (GraphClient)

```python
from symbol_graph import Confidence

# Get references with confidence filtering
refs = graph.get_symbol_refs("Person.firstName")
high_conf = [r for r in refs if r.confidence == Confidence.HIGH]

# Check confidence in traversal
for ref in graph.get_transitive_refs(symbol_id):
    if ref.confidence in (Confidence.HIGH, Confidence.MEDIUM):
        print(f"Reliable: {ref.target_id}")
```

## Confidence by Linker

| Linker | Typical Confidence | When HIGH | When INFERRED |
|--------|-------------------|-----------|---------------|
| `jpa_column` | HIGH/INFERRED | @Column(name=...) | No annotation |
| `el_path` | MEDIUM/INFERRED | Matches model attr | Multi-hop path |
| `form_binding` | HIGH/MEDIUM | commandName match | Partial match |
| `controller` | HIGH/LOW | View name in return | Naming convention |

## Best Practices

1. **Trust HIGH for automation**: HIGH confidence refs can be used for automated refactoring
2. **Review MEDIUM for human tasks**: Flag for developer review when making changes
3. **Treat INFERRED as hints**: May have false positives, use for exploration only
4. **Combine with blast-radius**: Use `--min-confidence medium` for safer impact analysis

## Updating Confidence

Linkers assign confidence based on evidence. To improve confidence:

1. Add explicit annotations (e.g., `@Column(name="...")`)
2. Use consistent naming conventions
3. Add `commandName` to form bindings

The JPA column linker automatically upgrades confidence when annotations are explicit.
