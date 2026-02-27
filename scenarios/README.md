# wicked-workbench Test Scenarios

This directory contains real-world test scenarios demonstrating wicked-workbench functionality. Each scenario proves actual value for dashboard-driven workflows with Claude Code.

## Scenario Overview

| Scenario | Type | Difficulty | Time | Focus |
|----------|------|------------|------|-------|
| [server-startup-health](./01-server-startup-health.md) | Setup | Basic | 5 min | Server initialization and plugin discovery |
| [task-dashboard-generation](./02-task-dashboard-generation.md) | Dashboard | Basic | 8 min | End-to-end natural language to dashboard |
| [multi-plugin-dashboard](./03-multi-plugin-dashboard.md) | Integration | Intermediate | 12 min | Cross-plugin component composition |
| [custom-catalog-component](./04-custom-catalog-component.md) | Integration | Advanced | 15 min | Plugin extensibility via catalog.json |
| [dashboard-persistence](./05-dashboard-persistence.md) | Dashboard | Intermediate | 8 min | Save and reload dashboards |

## Quick Start

### Run a Basic Scenario

```bash
# Start Workbench
wicked-workbench

# Follow the steps in any scenario markdown file
```

### What Each Scenario Proves

**server-startup-health**
- Zero-configuration server startup
- Automatic plugin ecosystem discovery
- Component catalog loading
- MCP server connection status
- API endpoint availability
- Real-world use: Verify Workbench is ready before generating dashboards

**task-dashboard-generation**
- Natural language to dashboard workflow
- A2UI JSON generation from component catalogs
- Live data integration from MCP servers
- Component filtering (priority, status, etc.)
- End-to-end rendering pipeline
- Real-world use: Ad-hoc dashboard creation from conversational requests

**multi-plugin-dashboard**
- Cross-plugin component composition
- Multi-source data fetching
- Layout components for dashboard structure
- Unified view of disparate data sources
- Catalog-driven component discovery
- Real-world use: Executive dashboards, sprint planning views, incident response

**custom-catalog-component**
- Plugin extensibility model
- Custom component definition via catalog.json
- AI-friendly component descriptions
- Rapid component prototyping
- No Workbench code changes required
- Real-world use: Custom monitoring dashboards, business KPIs, domain-specific views

**dashboard-persistence**
- Dashboard save and retrieval
- Database-backed persistence
- Dashboard metadata management
- Session-independent dashboard loading
- Dashboard library building
- Real-world use: Standard reporting dashboards, team collaboration, onboarding

## Learning Path

**New to Workbench?** Start here:
1. [server-startup-health](./01-server-startup-health.md) - Understand the foundation
2. [task-dashboard-generation](./02-task-dashboard-generation.md) - See the full workflow
3. [dashboard-persistence](./05-dashboard-persistence.md) - Learn to save dashboards

**Building custom components?** Follow this path:
1. [server-startup-health](./01-server-startup-health.md) - Verify plugin discovery
2. [custom-catalog-component](./04-custom-catalog-component.md) - Create custom catalogs
3. [multi-plugin-dashboard](./03-multi-plugin-dashboard.md) - Compose with other plugins

**Integrating multiple data sources?**
1. [multi-plugin-dashboard](./03-multi-plugin-dashboard.md) - Multi-source composition
2. [task-dashboard-generation](./02-task-dashboard-generation.md) - Single-source baseline
3. [custom-catalog-component](./04-custom-catalog-component.md) - Add custom sources

## Scenario Format

Each scenario follows this structure:

```markdown
---
name: scenario-name
title: Human Readable Title
description: One-line description
type: setup|dashboard|integration
difficulty: basic|intermediate|advanced
estimated_minutes: N
---

# Title

Brief explanation of what this proves.

## Setup
Concrete steps to create test environment.

## Steps
Numbered, executable steps with code blocks.

## Expected Outcome
What you should see at each step.

## Success Criteria
- [ ] Checkboxes for verification

## Value Demonstrated
WHY this matters in real-world usage.
```

## Command and API Coverage

### Commands

| Command | Scenarios |
|---------|-----------|
| `/wicked-workbench:workbench` | 01, 02, 03, 04, 05 |

### API Endpoints

| Endpoint | Method | Scenarios | Purpose |
|----------|--------|-----------|---------|
| `/health` | GET | 01 | Server health check |
| `/api/catalogs` | GET | 01, 03, 04 | List component catalogs |
| `/api/catalogs/{id}` | GET | 04 | Get catalog details |
| `/api/servers` | GET | 01, 03 | MCP server status |
| `/api/prompt` | GET | 01 | A2UI generation instructions |
| `/api/render` | POST | 02, 03, 04, 05 | Render A2UI document |
| `/api/current` | GET | 02 | Get displayed document |
| `/api/dashboards` | GET | 05 | List saved dashboards |
| `/api/dashboards` | POST | 05 | Save dashboard |
| `/api/dashboards/{id}` | GET | 05 | Retrieve dashboard |
| `/api/dashboards/{id}` | PUT | 05 | Update dashboard metadata |

## Personas Covered

These scenarios demonstrate value for different roles:

| Persona | Scenarios | Key Value |
|---------|-----------|-----------|
| **Product Manager** | 02, 03, 05 | Ad-hoc task views, multi-source dashboards |
| **Engineering Manager** | 03, 05 | Team dashboards, sprint planning views |
| **SRE/DevOps** | 04 | Custom monitoring dashboards |
| **Plugin Developer** | 04 | Component extensibility model |
| **Data Analyst** | 03, 04 | Multi-source data composition |

## Testing Philosophy

These scenarios are **functional tests**, not unit tests:

- **Real workflows**: End-to-end dashboard generation and rendering
- **Real integration**: Multiple plugins, MCP servers, database
- **Real value**: Time savings, improved visibility, better collaboration
- **Real extensibility**: Custom components, catalog-driven design

Each scenario answers: "Would I actually use this dashboard in production?"

## Integration Points

wicked-workbench scenarios demonstrate integration with:

- **wicked-kanban**: Task dashboard components (scenarios 02, 03, 05)
- **wicked-mem**: Memory and decision components (scenario 03)
- **Custom plugins**: Extensibility via catalog.json (scenario 04)
- **MCP protocol**: Live data fetching (scenarios 02, 03)
- **Database**: Dashboard persistence (scenario 05)

## Component Catalog Architecture

Workbench uses a **catalog-driven architecture**:

1. **Plugin Discovery**: Scans `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/catalog.json`
2. **Catalog Loading**: Loads component definitions and intents
3. **A2UI Generation**: Claude Code reads catalogs to generate valid dashboards
4. **Component Rendering**: Workbench validates and renders A2UI documents
5. **Data Fetching**: Connects to plugin MCP servers for live data

This design ensures:
- **Extensibility**: New plugins = new components automatically
- **Validation**: Claude generates valid A2UI from catalog schemas
- **Live Data**: Dashboards always show current data from MCP servers

## Contributing New Scenarios

When adding scenarios, ensure:

1. **Real-world use case** - Not a toy example
2. **Complete setup** - Reproducible environment creation
3. **Clear API usage** - Show exact curl commands and responses
4. **Value articulation** - Explain why this matters in production
5. **Verifiable criteria** - Checkboxes that can be tested

See existing scenarios as templates.

## Scenario Maintenance

- Test scenarios after each release
- Update if API endpoints or A2UI format changes
- Add scenarios for new catalog features
- Keep example A2UI JSON valid and realistic
- Verify MCP server ports match current defaults

## A2UI Format Reference

Dashboards use A2UI (Anthropic Agent UI) format:

### Surface Creation
```json
{
  "createSurface": {
    "surfaceId": "unique-id",
    "catalogId": "plugin-name"
  }
}
```

### Component Update
```json
{
  "updateComponents": {
    "surfaceId": "unique-id",
    "components": [
      {
        "id": "component-id",
        "component": "ComponentName",
        "prop1": "value1",
        "children": ["child-id"]
      }
    ]
  }
}
```

See scenarios for complete examples.

## Success Criteria Summary

All scenarios share these core criteria:

- [ ] Server starts without errors
- [ ] Component catalogs are discovered
- [ ] A2UI JSON is valid
- [ ] Dashboard renders successfully
- [ ] Live data is fetched from MCP servers
- [ ] API endpoints respond as expected

Additional criteria are scenario-specific.
