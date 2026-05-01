---
name: council-consensus
title: Council Consensus Scoring and Synthesis
description: Verify consensus.py scores proposals, extracts dissent, synthesizes decisions, and formats output
type: unit
difficulty: intermediate
estimated_minutes: 10
---

# Council Consensus Scoring and Synthesis

Validates the full consensus pipeline: scoring independent proposals, synthesizing with cross-reviews, extracting dissenting views with strength classification, confidence calculation, and output formatting for display and memory storage.

## Setup

Create test proposal and review files:

```bash
cat > "${TMPDIR:-/tmp}/proposals.json" <<'EOF'
[
  {"persona": "Security Architect", "proposal": "Use OAuth2 with PKCE flow for all external APIs", "rationale": "PKCE prevents authorization code interception attacks", "confidence": 0.85, "concerns": ["Adds complexity for internal-only APIs"]},
  {"persona": "Platform Engineer", "proposal": "Use OAuth2 with PKCE for external APIs and API keys for internal services", "rationale": "Simpler for internal services while still securing external endpoints", "confidence": 0.75, "concerns": ["API key rotation adds operational burden"]},
  {"persona": "Frontend Developer", "proposal": "Use OAuth2 with PKCE for all APIs to keep auth consistent", "rationale": "Single auth pattern reduces frontend complexity", "confidence": 0.70, "concerns": ["Internal APIs dont need this complexity"]},
  {"persona": "DevOps Lead", "proposal": "Use OAuth2 for external, mTLS for internal service-to-service", "rationale": "mTLS is standard for service mesh", "confidence": 0.80, "concerns": ["Certificate management overhead"]},
  {"persona": "Product Manager", "proposal": "Use OAuth2 with PKCE for external APIs, API keys for quick internal MVP", "rationale": "Ship fast, improve later", "confidence": 0.65, "concerns": ["Technical debt from API keys"]}
]
EOF

cat > "${TMPDIR:-/tmp}/reviews.json" <<'EOF'
[
  {"reviewer": "Security Architect", "target_persona": "Platform Engineer", "agreements": ["OAuth2 for external APIs"], "disagreements": [{"point": "API keys for internal", "counter": "API keys are a security risk even internally"}], "questions": ["What is the key rotation policy?"]},
  {"reviewer": "Platform Engineer", "target_persona": "Security Architect", "agreements": ["PKCE is good"], "disagreements": [{"point": "PKCE for all APIs", "counter": "Overhead not justified for internal"}], "questions": []}
]
EOF
```

## Steps

### 1. Score consensus from proposals

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/jam/consensus.py" score --proposals "${TMPDIR:-/tmp}/proposals.json" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
result = json.load(sys.stdin)
assert 'consensus_points' in result, 'Missing consensus_points'
assert 'confidence' in result, 'Missing confidence'
assert 'divergent_points' in result, 'Missing divergent_points'
assert isinstance(result['consensus_points'], list), 'consensus_points should be a list'
print('PASS: Score output has consensus_points, confidence, divergent_points')
print('Confidence: %s' % result['confidence'])
print('Consensus points: %d, Divergent points: %d' % (len(result['consensus_points']), len(result['divergent_points'])))
"
```

**Expected**: Returns JSON with `consensus_points` (OAuth2 for external should have high agreement across 4+ of 5 personas), `confidence` (average of individual confidences), and `divergent_points`. Prints PASS.

### 2. Full synthesis with proposals and reviews

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/jam/consensus.py" synthesize \
  --proposals "${TMPDIR:-/tmp}/proposals.json" \
  --reviews "${TMPDIR:-/tmp}/reviews.json" \
  --question "How should we handle API authentication?" | tee "${TMPDIR:-/tmp}/result.json" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
result = json.load(sys.stdin)
assert 'decision' in result, 'Missing decision'
assert 'confidence' in result, 'Missing confidence'
assert 'consensus_points' in result, 'Missing consensus_points'
assert 'dissenting_views' in result, 'Missing dissenting_views'
assert 'open_questions' in result, 'Missing open_questions'
assert 'participants' in result, 'Missing participants'
assert result['participants'] == 5, 'Expected 5 participants, got %d' % result['participants']
print('PASS: Synthesis produced complete ConsensusResult')
print('Decision: %s' % result['decision'][:100])
"
```

**Expected**: Returns a full ConsensusResult with decision, confidence, consensus_points, dissenting_views, open_questions, rounds=2 (because reviews were provided), and participants=5. Prints PASS.

### 3. Dissent extraction from synthesis

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
result = json.load(open('${TMPDIR:-/tmp}/result.json'))
dissents = result.get('dissenting_views', [])
assert len(dissents) > 0, 'Expected non-empty dissenting_views'
strengths = [d['strength'] for d in dissents]
assert all(s in ('strong', 'moderate', 'mild') for s in strengths), 'Invalid strength values: %s' % strengths
# At least one dissent should mention API keys or internal
texts = ' '.join(d.get('view', '') for d in dissents).lower()
print('PASS: Found %d dissenting views with strengths: %s' % (len(dissents), strengths))
"
```

**Expected**: `dissenting_views` is non-empty. Each dissent has a `strength` field with value "strong", "moderate", or "mild". At least one dissent relates to internal API authentication approach. Prints PASS.

### 4. Confidence is in valid range

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json
result = json.load(open('${TMPDIR:-/tmp}/result.json'))
conf = result['confidence']
assert 0.0 <= conf <= 1.0, 'Confidence %s out of range [0, 1]' % conf
print('PASS: Confidence %.3f is in valid range [0.0, 1.0]' % conf)
"
```

**Expected**: Confidence is between 0.0 and 1.0 (should be around 0.75, the average of all proposal confidences). Prints PASS.

### 5. Format for display

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/jam/consensus.py" format --result "${TMPDIR:-/tmp}/result.json" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
output = sys.stdin.read()
assert '## Council Consensus' in output, 'Missing header'
assert '### Decision' in output, 'Missing Decision section'
assert 'Confidence' in output, 'Missing Confidence line'
print('PASS: Display format has expected markdown headers')
"
```

**Expected**: Markdown output with `## Council Consensus`, `### Decision`, `**Confidence:**`, and `**Participants:**` headers. Prints PASS.

### 6. Format for display with dissent section

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/jam/consensus.py" format --result "${TMPDIR:-/tmp}/result.json" --show-dissent | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
output = sys.stdin.read()
assert '### Dissenting Views' in output, 'Missing Dissenting Views section when --show-dissent used'
print('PASS: --show-dissent flag includes Dissenting Views section')
"
```

**Expected**: When `--show-dissent` is passed, the output includes a `### Dissenting Views` section with persona names and strength indicators. Prints PASS.

### 7. Format for memory produces correct structure

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/jam')
from consensus import _result_from_json, format_for_memory
data = json.load(open('${TMPDIR:-/tmp}/result.json'))
result = _result_from_json(data)
mem = format_for_memory(result)
assert mem['type'] == 'decision', 'Expected type=decision, got %s' % mem['type']
assert 'content' in mem, 'Missing content'
assert 'metadata' in mem, 'Missing metadata'
md = mem['metadata']
assert 'confidence' in md, 'Missing confidence in metadata'
assert 'dissent_count' in md, 'Missing dissent_count in metadata'
assert 'strong_dissent_count' in md, 'Missing strong_dissent_count'
print('PASS: format_for_memory has type=decision with dissent metadata')
print('Dissent count: %d, Strong: %d' % (md['dissent_count'], md['strong_dissent_count']))
"
```

**Expected**: Returns dict with `type` = "decision", `content` containing the decision text, and `metadata` including `confidence`, `participants`, `rounds`, `consensus_point_count`, `dissent_count`, and `strong_dissent_count`. Prints PASS.

### 8. Synthesis works without reviews (optional cross-reviews)

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/jam/consensus.py" synthesize \
  --proposals "${TMPDIR:-/tmp}/proposals.json" \
  --question "test without reviews" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
result = json.load(sys.stdin)
assert 'decision' in result, 'Missing decision'
assert result['rounds'] == 1, 'Expected 1 round without reviews, got %d' % result['rounds']
assert result['cross_reviews'] == [], 'Expected empty cross_reviews'
print('PASS: Synthesis works without cross-reviews (rounds=1)')
"
```

**Expected**: Synthesis completes successfully without `--reviews` flag. `rounds` = 1 (no cross-review round). `cross_reviews` is an empty list. Prints PASS.

## Success Criteria

- [ ] Score command identifies consensus points across proposals
- [ ] Full synthesis produces ConsensusResult with all required fields
- [ ] Dissenting views extracted with strength classification (strong/moderate/mild)
- [ ] Confidence is between 0.0 and 1.0
- [ ] Display format produces valid markdown with headers
- [ ] `--show-dissent` flag includes Dissenting Views section
- [ ] format_for_memory produces type=decision with dissent metadata
- [ ] Synthesis works without cross-reviews (optional parameter)

## Cleanup

```bash
rm -f "${TMPDIR:-/tmp}/proposals.json" "${TMPDIR:-/tmp}/reviews.json" "${TMPDIR:-/tmp}/result.json"
```
