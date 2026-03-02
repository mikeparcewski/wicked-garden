---
description: Detect and visualize the service architecture from infrastructure and code patterns
argument-hint: "[project_root] [--format table|json|mermaid]"
---

# /wicked-garden:search:service-map

Detect services and their connections from infrastructure configuration files and the knowledge graph. Generates a service dependency map.

## Arguments

- `project_root` (optional): Project root directory to scan (default: current directory)
- `--format` (optional): Output format - table, json, mermaid (default: table)
- `--project` (optional): Project name in knowledge graph

## Instructions

1. Detect infrastructure-defined services by scanning for config files:
   ```
   Glob: **/docker-compose*.yml, **/k8s/**, **/kubernetes/**, **/helm/**
   ```

   Parse found files to extract service names, types, and connections.

2. Query the knowledge graph for code-level services:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "service" --type code ${project:+--project "${project}"}
   ```

3. Get hotspot services (high connectivity = likely service boundaries):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph hotspots --type CLASS --limit 20 ${project:+--project "${project}"}
   ```

4. Merge infrastructure and code-level discoveries into a unified service map.

5. Report in requested format:

   ### Table Format (default)
   ```markdown
   ## Service Map

   | Service | Type | Technology | Source |
   |---------|------|------------|--------|
   | api | application | nodejs | docker-compose |
   | db | database | postgres | docker-compose |
   | UserService | service_class | java | code_pattern |

   ### Connections

   | From | To | Type | Confidence |
   |------|-----|------|------------|
   | api | db | database | high |
   ```

   ### Mermaid Format
   Generate a `graph TD` diagram with service nodes and connection edges.

## Example

```
/wicked-garden:search:service-map
/wicked-garden:search:service-map --format mermaid
/wicked-garden:search:service-map /path/to/project --project my-app
```

## Detection Sources (Priority Order)

1. **Docker Compose** (highest confidence): `docker-compose.yml`, `depends_on`
2. **Kubernetes** (high confidence): Deployment, Service manifests
3. **Code Patterns** (medium confidence): `@Service`, `@RestController`, connection strings

## Notes

- Infrastructure sources (docker, k8s) don't require indexing
- Code patterns require prior indexing with `/wicked-garden:search:index`
