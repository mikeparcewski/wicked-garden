---
description: Discover and query engineer monitoring tools (APM, logging, metrics, cloud)
---

# /wicked-garden:observability:toolchain

Discover monitoring CLIs available in the current environment and run queries against them.

## Usage

```
/wicked-garden:observability:toolchain [--query "..."] [--category apm|logging|metrics|cloud]
```

## Arguments

- `--query "..."` — Log/metric query to run against detected tools (optional)
- `--category` — Limit discovery to one category: `apm`, `logging`, `metrics`, `cloud`

## Instructions

1. **Detect available tools** using `command -v` for each known binary:

   ```bash
   # APM
   command -v datadog-agent && echo "datadog"
   command -v newrelic      && echo "newrelic"
   command -v dt            && echo "dynatrace"

   # Logging
   command -v splunk        && echo "splunk"
   command -v elasticsearch && echo "elasticsearch"
   command -v logcli        && echo "loki"

   # Metrics
   command -v promtool      && echo "prometheus"
   command -v grafana-cli   && echo "grafana"
   command -v influx        && echo "influxdb"

   # Cloud
   command -v aws           && echo "aws-cloudwatch"
   command -v gcloud        && echo "gcp-monitoring"
   command -v az            && echo "azure-monitor"
   ```

2. **If no `--query` given**: Report discovered tools grouped by category. For each found tool, show: binary path, version if quickly available (`datadog-agent version`, `newrelic version`, `gcloud version`).

3. **If `--query` given**: Route the query to appropriate detected tool(s):
   - Logging tools → search/filter for the query string in recent logs (last 1h default)
   - Metrics tools → query for metric matching the query
   - APM tools → search traces/events matching the query
   - Cloud tools → query CloudWatch/Stackdriver/Azure logs for the string
   - Run queries for each detected tool in the relevant category
   - Present results side-by-side with tool attribution

4. **If `--category` given**: Limit both discovery and query execution to that category.

5. **Display format**:

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

6. **Suggest next steps** based on what was found:
   - If APM found: suggest `datadog-agent status` or equivalent health check
   - If logging found: suggest query patterns from [refs/toolchain-discovery.md](../skills/observability/refs/toolchain-discovery.md)
   - If nothing found: note that monitoring CLIs can be installed and list quickstart install commands

## Error Handling

- If a tool is found but errors on query: show the error and continue with other tools
- If no tools are found: report "No monitoring CLIs detected" and suggest installation options
- Never fail — this command is read-only discovery
