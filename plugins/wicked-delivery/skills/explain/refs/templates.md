# Explanation Templates

Detailed templates for code explanations.

## Component Deep Dive Template

```markdown
## Component: {Name}

**Location**: `{file path}:{line range}`

### Purpose
{What this component does and its role in the system}

### Context
**Problem Solved**: {What need does this address?}
**Design Rationale**: {Why this implementation approach?}
**Tradeoffs**:
- **Chosen**: {What was prioritized}
- **Sacrificed**: {What was deprioritized}

### Key Responsibilities
1. **{Primary responsibility}** - {How accomplished}
2. **{Secondary responsibility}** - {How accomplished}

### Important Methods
#### `method_name(params)`
**Purpose**: {What it does}
**When to use**: {Use cases}
**Example**:
```{language}
{Code snippet from tests or usage}
```

### Dependencies
**Requires**:
- {Dependency 1} - {Why needed}

**Used By**:
- {Dependent 1} - {How they use it}

### Example Usage
```{language}
{Real example from codebase or tests}
```

### Testing
**Test file**: `{test file path}`
**Key test cases**:
- {Test scenario 1}
- {Test scenario 2}

### Related
- **Similar pattern**: {Other component}
- **See also**: {Related functionality}
- **Next**: {Suggested exploration}
```

## Flow Explanation Template

```markdown
## Flow: {Process Name}

### Overview
{What happens, start to finish, in 2-3 sentences}

### Participants
{List components involved and their roles}

### Step-by-Step

#### Step 1: {Stage name}
**Location**: `{file}:{line}`
**Action**: {What happens}

```{language}
{Relevant code snippet}
```

**Explanation**: {Why this step exists}

#### Step 2: {Stage name}
**Location**: `{file}:{line}`
**Action**: {What happens}
**Transformation**: {How data changes}

{Continue for each step}

### Decision Points
**Condition 1**: {What determines the path}
- If true: {Path A}
- If false: {Path B}

### Error Handling
{How failures are detected and handled at each stage}

### Performance Considerations
{Caching, async operations, optimizations}

### Example Trace
**Scenario**: {Concrete example}

```
Input: {Example input}
Step 1: {What happens with this input}
Step 2: {Transformation}
...
Output: {Final result}
```

### Testing
**Test file**: `{test file path}`
**Coverage**: {What scenarios are tested}

### Related Flows
- **Similar to**: {Other flow}
- **Triggers**: {What initiates this}
- **Triggered by**: {Where called from}
```

## Pattern Explanation Template

```markdown
## Pattern: {Pattern Name}

### Recognition
You'll know you're looking at this pattern when you see:
- {Indicator 1}
- {Indicator 2}

**Examples in this codebase**:
- `{file 1}` - {Brief description}
- `{file 2}` - {Brief description}

### Purpose
**Problem**: {What problem does this pattern solve?}
**Solution**: {How does this pattern solve it?}

### Structure
{Diagram or description of pattern components}

**Key Elements**:
1. {Element 1} - {Role}
2. {Element 2} - {Role}

### Implementation
**In this codebase**:

```{language}
{Example showing pattern structure}
```

**Variations**: {How pattern is adapted}

### Advantages
- {Benefit 1}
- {Benefit 2}

### Cautions
**When to use**: {Scenarios}
**When to avoid**: {Scenarios}

### Evolution
{If pattern changed over time, explain why}

### Related Patterns
- **Alternative**: {Different approach}
- **Combines with**: {Complementary patterns}
```
