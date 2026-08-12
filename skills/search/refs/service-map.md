# Service map — detect and visualize the service architecture

Detect services and their connections from infrastructure configuration files
and code patterns. Generates a service dependency map.

## Arguments

- `project_root` (optional): Project root directory to scan (default: current directory)
- `--format` (optional): Output format - table, json, mermaid (default: table)

## Instructions

1. **Detect infrastructure-defined services** by scanning for config files:
   ```
   Glob: **/docker-compose*.yml, **/k8s/**, **/kubernetes/**, **/helm/**
   ```
   Parse found files to extract service names, types, and connections.

2. **Search code for service patterns** — the estate MCP `SearchEntity` tool
   (when connected) for service/controller/router symbols, plus Grep:
   ```
   Grep: @(Service|RestController|Controller|Router|app\.(get|post|put|delete))
   ```
   Suggest `wicked-estate index` to build the code graph for richer service discovery.

3. Merge infrastructure and code-level discoveries into a unified service map.

4. Report in requested format:

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

   ### JSON Format
   Emit the merged service map (services + connections, with source and
   confidence fields) as JSON.

   ### Mermaid Format
   Generate a `graph TD` diagram with service nodes and connection edges.

## Example

```
service-map
service-map --format mermaid
service-map /path/to/project
```

## Detection Sources (Priority Order)

1. **Docker Compose** (highest confidence): `docker-compose.yml`, `depends_on`
2. **Kubernetes** (high confidence): Deployment, Service manifests
3. **Code Patterns** (medium confidence): `@Service`, `@RestController`, connection strings

## Notes

- Infrastructure sources (docker, k8s) don't require indexing
- Code patterns benefit from the estate code graph (`wicked-estate index`)
