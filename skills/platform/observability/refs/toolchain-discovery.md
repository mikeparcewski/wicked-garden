---
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---
# Toolchain Discovery: Monitoring CLI Detection Patterns

Detection patterns and usage examples for monitoring CLIs in the engineer's environment.
All detection uses `command -v` — no external dependencies required.

## Detection Script

```bash
# Discover all monitoring CLIs in current environment
discover_monitoring_tools() {
  echo "=== APM ==="
  command -v datadog-agent &>/dev/null && echo "  datadog: $(command -v datadog-agent)"
  command -v newrelic      &>/dev/null && echo "  newrelic: $(command -v newrelic)"
  command -v dt            &>/dev/null && echo "  dynatrace: $(command -v dt)"

  echo "=== Logging ==="
  command -v splunk        &>/dev/null && echo "  splunk: $(command -v splunk)"
  command -v elasticsearch &>/dev/null && echo "  elasticsearch: $(command -v elasticsearch)"
  command -v logcli        &>/dev/null && echo "  loki: $(command -v logcli)"

  echo "=== Metrics ==="
  command -v promtool      &>/dev/null && echo "  prometheus: $(command -v promtool)"
  command -v grafana-cli   &>/dev/null && echo "  grafana: $(command -v grafana-cli)"
  command -v influx        &>/dev/null && echo "  influxdb: $(command -v influx)"

  echo "=== Cloud ==="
  command -v aws           &>/dev/null && echo "  cloudwatch: $(command -v aws)"
  command -v gcloud        &>/dev/null && echo "  gcp: $(command -v gcloud)"
  command -v az            &>/dev/null && echo "  azure: $(command -v az)"
}
```

## Run Semantics

Arguments: `[--query "..."] [--category apm|logging|metrics|cloud]`.

1. **Detect available tools** using `command -v` for each known binary (the
   detection script above covers all four categories).

2. **If no `--query` given**: Report discovered tools grouped by category. For
   each found tool, show: binary path, version if quickly available
   (`datadog-agent version`, `newrelic version`, `gcloud version`).

3. **If `--query` given**: Route the query to appropriate detected tool(s):
   - Logging tools → search/filter for the query string in recent logs (last 1h default)
   - Metrics tools → query for metric matching the query
   - APM tools → search traces/events matching the query
   - Cloud tools → query CloudWatch/Stackdriver/Azure logs for the string
   - Run queries for each detected tool in the relevant category
   - Present results side-by-side with tool attribution

4. **If `--category` given**: Limit both discovery and query execution to that
   category.

## Display Format

```
Monitoring Toolchain Discovery
==============================

APM
  datadog-agent  /usr/local/bin/datadog-agent  v7.58.0
  newrelic       (not found)
  dynatrace      (not found)

Logging
  splunk         (not found)
  loki/logcli    /usr/local/bin/logcli  v2.9.0

Metrics
  prometheus     /usr/local/bin/promtool  v2.48.0
  grafana-cli    (not found)

Cloud
  aws (cloudwatch) /usr/local/bin/aws  aws-cli/2.15.0
  gcloud (monitoring) (not found)
  azure (az)     (not found)

Detected: datadog-agent, logcli, promtool, aws
```

## Next-Step Suggestions

Based on what was found:
- If APM found: suggest `datadog-agent status` or equivalent health check
- If logging found: suggest query patterns from the per-tool sections below
- If nothing found: note that monitoring CLIs can be installed and list
  quickstart install commands

## Error Handling

- If a tool is found but errors on query: show the error and continue with
  other tools
- If no tools are found: report "No monitoring CLIs detected" and suggest
  installation options
- Never fail — discovery is read-only

---

## APM Tools

### Datadog (`datadog-agent`)

```bash
# Agent status
datadog-agent status

# Check specific integration
datadog-agent check postgres

# Query metrics via API
curl -G "https://api.datadoghq.com/api/v1/metrics/query" \
  -H "DD-API-KEY: ${DD_API_KEY}" -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
  --data-urlencode "query=avg:system.cpu.user{host:web-01}" \
  --data-urlencode "from=$(date -d '1 hour ago' +%s)" \
  --data-urlencode "to=$(date +%s)"

# Diagnose connectivity
datadog-agent diagnose
```

### New Relic (`newrelic`)

```bash
# Auth check
newrelic whoami

# NRQL query
newrelic nrql query \
  --query "SELECT count(*) FROM Transaction WHERE appName='MyApp' SINCE 1 hour ago"

# Open alerts
newrelic alerts incidents list --state OPEN

# Setup: newrelic profiles add --profile myprofile --apiKey "${NEW_RELIC_API_KEY}"
```

### Dynatrace (`dt`)

```bash
# Auth check
dt auth

# Query metrics
dt metrics query --metric-selector "builtin:host.cpu.usage" --resolution 5m

# Open problems
dt problems list --status OPEN

# Entity list
dt entities list --entitySelector "type(SERVICE),tag(env:production)"
```

---

## Logging Tools

### Splunk (`splunk`)

```bash
# Status check
splunk status

# Search last hour of errors
splunk search "index=main error" -earliest=-1h -latest=now

# Export results
splunk search "index=main sourcetype=syslog error" -earliest=-1h -output csv > errors.csv

# REST API alternative
curl -k -u "admin:${SPLUNK_PASSWORD}" "https://localhost:8089/services/search/jobs" \
  -d "search=search index=main error | head 10" -d "output_mode=json"
```

### Elasticsearch / ELK

```bash
# Cluster health
curl -s "http://localhost:9200/_cluster/health" | jq .

# Query errors (last hour)
curl -s -X GET "http://localhost:9200/logs-*/_search" \
  -H "Content-Type: application/json" \
  -d '{"query":{"bool":{"must":[{"match":{"level":"error"}}],
        "filter":[{"range":{"@timestamp":{"gte":"now-1h"}}}]}}, "size":50}' \
  | jq '.hits.hits[]._source'
```

### Loki (`logcli`)

```bash
# Query errors
logcli query '{app="my-service"} |= "error"' --limit 100 --since=1h

# Stream live
logcli query '{app="my-service"}' --tail

# List labels
logcli labels app

# export LOKI_ADDR="http://localhost:3100"
```

---

## Metrics Tools

### Prometheus (`promtool`)

```bash
# Validate config
promtool check config prometheus.yml

# Instant query (REST API)
curl -s "http://localhost:9090/api/v1/query?query=up" | jq '.data.result[]'

# Range query
curl -s "http://localhost:9090/api/v1/query_range" \
  --data-urlencode "query=rate(http_requests_total[5m])" \
  --data-urlencode "start=$(date -d '1 hour ago' +%s)" \
  --data-urlencode "end=$(date +%s)" \
  --data-urlencode "step=60" | jq '.data.result[]'
```

### Grafana (`grafana-cli`)

```bash
# Health check
curl -s "http://localhost:3000/api/health" | jq .

# List dashboards
curl -s -u "admin:${GRAFANA_PASSWORD}" \
  "http://localhost:3000/api/search?type=dash-db" | jq '.[].title'
```

---

## Cloud Monitoring Tools

### AWS CloudWatch (`aws`)

```bash
# List log groups
aws logs describe-log-groups --query 'logGroups[*].logGroupName' --output table

# Filter errors from a log group
aws logs filter-log-events \
  --log-group-name "/aws/lambda/my-function" \
  --filter-pattern "ERROR" \
  --start-time "$(date -d '1 hour ago' +%s000)" --limit 50

# Get metric stats
aws cloudwatch get-metric-statistics \
  --namespace "AWS/Lambda" --metric-name "Errors" \
  --dimensions Name=FunctionName,Value=my-function \
  --start-time "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --period 300 --statistics Sum
```

### Google Cloud Monitoring (`gcloud`)

```bash
# Recent errors
gcloud logging read "severity>=ERROR" --limit=50 --freshness=1h

# Filter by resource
gcloud logging read \
  'resource.type="k8s_container" AND severity="ERROR"' \
  --limit 50 --project="${GOOGLE_PROJECT}"
```

### Azure Monitor (`az`)

```bash
# Log Analytics query
az monitor log-analytics query \
  --workspace "${AZURE_WORKSPACE_ID}" \
  --analytics-query "AzureDiagnostics | where Level == 'Error' | take 50" \
  --output table

# Get metric values
az monitor metrics list \
  --resource "${AZURE_RESOURCE_ID}" --metric "requests" --interval PT5M \
  --start-time "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)"
```

---

## Quick Reference

| Tool | Binary | Category | Key Operation |
|------|--------|----------|---------------|
| Datadog | `datadog-agent` | APM | `status`, REST metrics API |
| New Relic | `newrelic` | APM | `nrql query` |
| Dynatrace | `dt` | APM | `metrics query`, `problems list` |
| Splunk | `splunk` | Logging | `search "index=main ..."` |
| Elasticsearch | n/a | Logging | REST `/_search` |
| Loki | `logcli` | Logging | `query '{app="..."}` |
| Prometheus | `promtool` | Metrics | REST `/api/v1/query` |
| Grafana | `grafana-cli` | Metrics | REST `/api/search` |
| AWS CloudWatch | `aws` | Cloud | `logs filter-log-events` |
| GCP Monitoring | `gcloud` | Cloud | `logging read` |
| Azure Monitor | `az` | Cloud | `monitor log-analytics query` |
