# Guardrail Implementation Patterns

Practical implementation patterns for safety guardrails in agentic systems.

## Input Guardrails

### Pattern 1: Layered Input Validation

Validate at multiple levels for defense in depth.

```python
class InputGuardrails:
    def __init__(self):
        self.validators = [
            SizeValidator(max_size=10000),
            EncodingValidator(),
            PromptInjectionDetector(),
            PIIDetector(),
            ContentFilter()
        ]

    async def validate(self, user_input):
        results = []

        for validator in self.validators:
            result = await validator.validate(user_input)
            results.append(result)

            if not result.is_valid:
                raise ValidationError(
                    validator=validator.name,
                    reason=result.reason,
                    severity=result.severity
                )

        return ValidationResult(valid=True, checks=results)

# Usage
guardrails = InputGuardrails()
await guardrails.validate(user_input)
```

### Pattern 2: Sanitization Pipeline

Clean inputs progressively:

```python
class SanitizationPipeline:
    @staticmethod
    async def sanitize(input_text):
        # Step 1: Normalize
        text = unicodedata.normalize('NFKC', input_text)

        # Step 2: Remove null bytes
        text = text.replace('\x00', '')

        # Step 3: Strip control characters (except common whitespace)
        text = ''.join(char for char in text
                      if unicodedata.category(char)[0] != 'C'
                      or char in '\n\r\t')

        # Step 4: Limit line length
        lines = text.split('\n')
        text = '\n'.join(line[:1000] for line in lines)

        # Step 5: Remove injection patterns
        text = await PromptInjectionFilter.filter(text)

        return text
```

### Pattern 3: Prompt Injection Detection

Detect common injection patterns:

```python
class PromptInjectionDetector:
    SUSPICIOUS_PATTERNS = [
        r'ignore\s+(previous|above|all)\s+instructions?',
        r'disregard\s+(previous|above|all)',
        r'forget\s+(previous|above|all)',
        r'new\s+instructions?:',
        r'system:',
        r'<\s*system\s*>',
        r'you\s+are\s+now',
        r'act\s+as\s+if',
        r'pretend\s+you\s+are',
    ]

    async def validate(self, text):
        text_lower = text.lower()

        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, text_lower):
                return ValidationResult(
                    is_valid=False,
                    reason=f"Suspicious pattern detected: {pattern}",
                    severity="high"
                )

        # Check for delimiter confusion
        if '```' in text and 'system' in text_lower:
            return ValidationResult(
                is_valid=False,
                reason="Potential delimiter confusion attack",
                severity="medium"
            )

        return ValidationResult(is_valid=True)
```

## Output Guardrails

### Pattern 4: Schema-Based Output Validation

Enforce structured outputs:

```python
from pydantic import BaseModel, Field, validator

class SafeOutput(BaseModel):
    """Base class for all agent outputs with built-in safety."""

    content: str = Field(..., max_length=10000)
    confidence: float = Field(..., ge=0.0, le=1.0)
    sources: List[str] = Field(default_factory=list)
    contains_pii: bool = False

    @validator('content')
    def no_sensitive_data(cls, v):
        # Check for common PII patterns
        pii_patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
            'credit_card': r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',
        }

        for pii_type, pattern in pii_patterns.items():
            if re.search(pattern, v):
                raise ValueError(f'Output contains {pii_type}')

        return v

    @validator('confidence')
    def sufficient_confidence(cls, v):
        if v < 0.3:
            raise ValueError('Confidence too low for production use')
        return v

# Force agent to use structured output
class SafeAgent:
    async def generate(self, prompt):
        raw_output = await self.llm.generate(prompt)
        # Parse into validated structure
        return SafeOutput.parse_obj(raw_output)
```

### Pattern 5: Multi-Stage Output Filtering

Filter outputs progressively:

```python
class OutputGuardrails:
    def __init__(self):
        self.filters = [
            PIIRedactor(),
            ContentSafetyFilter(),
            FactualityChecker(),
            BiasDetector()
        ]

    async def filter(self, output):
        filtered_output = output

        for filter in self.filters:
            result = await filter.process(filtered_output)

            if result.should_block:
                raise UnsafeOutputError(
                    filter=filter.name,
                    reason=result.reason
                )

            filtered_output = result.filtered_content

        return filtered_output

# Example: PII Redactor
class PIIRedactor:
    async def process(self, text):
        findings = detect_pii(text)

        if findings:
            # Redact PII
            redacted = redact_pii(text)
            return FilterResult(
                should_block=False,  # Allow but redact
                filtered_content=redacted,
                warnings=[f"Redacted {len(findings)} PII instances"]
            )

        return FilterResult(
            should_block=False,
            filtered_content=text
        )
```

### Pattern 6: Confidence-Based Output Handling

Different handling based on confidence:

```python
class ConfidenceBasedOutputHandler:
    async def handle(self, output):
        confidence = output.confidence

        if confidence >= 0.9:
            # High confidence - auto-approve
            return await self.auto_approve(output)

        elif confidence >= 0.7:
            # Medium confidence - human review optional
            return await self.queue_for_review(output, priority="low")

        elif confidence >= 0.5:
            # Low confidence - require human review
            return await self.require_human_review(output)

        else:
            # Very low confidence - reject
            raise LowConfidenceError(
                f"Confidence {confidence} below threshold"
            )
```

## Action Guardrails

### Pattern 7: Action Whitelisting Framework

Comprehensive whitelisting:

```python
class ActionWhitelist:
    def __init__(self):
        self.allowed_actions = {}

    def register_action(self, name, allowed_params, constraints):
        """Register an allowed action with parameter constraints."""
        self.allowed_actions[name] = {
            'params': allowed_params,
            'constraints': constraints
        }

    async def validate_action(self, action_name, params):
        if action_name not in self.allowed_actions:
            raise ForbiddenActionError(f"Action '{action_name}' not whitelisted")

        action_spec = self.allowed_actions[action_name]

        # Validate parameters
        for param, value in params.items():
            if param not in action_spec['params']:
                raise ForbiddenParameterError(f"Parameter '{param}' not allowed")

            # Check parameter constraints
            param_constraints = action_spec['params'][param]
            if not self._validate_constraint(value, param_constraints):
                raise ConstraintViolationError(
                    f"Parameter '{param}' violates constraints"
                )

        # Check action-level constraints
        for constraint in action_spec['constraints']:
            if not await constraint.check(action_name, params):
                raise ConstraintViolationError(constraint.reason)

        return True

# Example: Register safe actions
whitelist = ActionWhitelist()
whitelist.register_action(
    name='read_file',
    allowed_params={
        'path': {'type': str, 'pattern': r'^/safe/path/.*'},
        'max_size': {'type': int, 'max': 1000000}
    },
    constraints=[
        NoProductionAccessConstraint(),
        RateLimitConstraint(max_per_hour=100)
    ]
)
```

### Pattern 8: Pre-Flight Action Validation

Validate before executing:

```python
class PreFlightValidator:
    async def validate(self, action):
        validations = [
            self.check_authorization(action),
            self.check_resource_limits(action),
            self.check_blast_radius(action),
            self.check_reversibility(action)
        ]

        results = await asyncio.gather(*validations)

        for result in results:
            if not result.passed:
                raise PreFlightFailure(
                    check=result.check_name,
                    reason=result.reason
                )

    async def check_blast_radius(self, action):
        """Check potential impact of action."""
        if action.type == 'delete':
            affected_count = await self.estimate_affected_records(action)
            if affected_count > 1000:
                return ValidationResult(
                    passed=False,
                    check_name='blast_radius',
                    reason=f'Would affect {affected_count} records (limit: 1000)'
                )

        return ValidationResult(passed=True)

    async def check_reversibility(self, action):
        """Ensure action can be reversed."""
        if action.is_irreversible() and not action.has_approval():
            return ValidationResult(
                passed=False,
                check_name='reversibility',
                reason='Irreversible action requires approval'
            )

        return ValidationResult(passed=True)
```

### Pattern 9: Sandboxed Execution

Execute actions in isolated environment:

```python
class SandboxedExecutor:
    def __init__(self):
        self.sandbox = Sandbox(
            network_access=False,
            file_system_access='/tmp/sandbox',
            max_memory_mb=512,
            max_cpu_percent=50,
            timeout_seconds=30
        )

    async def execute(self, action):
        # Prepare sandbox
        await self.sandbox.reset()

        # Copy necessary files/data into sandbox
        await self.sandbox.copy_in(action.required_files)

        try:
            # Execute in sandbox
            result = await self.sandbox.run(
                action.command,
                timeout=action.timeout or 30
            )

            # Copy results out
            output_files = await self.sandbox.copy_out('/tmp/sandbox/output')

            return ExecutionResult(
                success=True,
                output=result.stdout,
                files=output_files
            )

        except TimeoutError:
            raise ExecutionTimeoutError()

        except MemoryError:
            raise MemoryLimitExceeded()

        finally:
            # Always clean up
            await self.sandbox.cleanup()
```

## Approval Guardrails

### Pattern 10: Risk-Based Approval Routing

Route to appropriate approver based on risk:

```python
class ApprovalRouter:
    def __init__(self):
        self.risk_assessor = RiskAssessor()

    async def route_for_approval(self, action):
        risk_score = await self.risk_assessor.assess(action)

        if risk_score >= 0.8:
            # High risk - requires senior approval
            approvers = ['senior-engineer@company.com', 'security@company.com']
            timeout = timedelta(hours=4)

        elif risk_score >= 0.5:
            # Medium risk - requires team lead approval
            approvers = ['team-lead@company.com']
            timeout = timedelta(hours=1)

        elif risk_score >= 0.3:
            # Low risk - any team member can approve
            approvers = self.get_on_call_approvers()
            timeout = timedelta(minutes=30)

        else:
            # Very low risk - auto-approve
            return ApprovalResult(approved=True, auto_approved=True)

        return await self.request_approval(
            action=action,
            approvers=approvers,
            timeout=timeout,
            risk_score=risk_score
        )

class RiskAssessor:
    async def assess(self, action):
        factors = {
            'is_production': 0.4 if action.env == 'production' else 0.0,
            'is_destructive': 0.3 if action.is_destructive else 0.0,
            'is_irreversible': 0.2 if action.is_irreversible else 0.0,
            'data_volume': min(action.affected_records / 10000, 0.1),
        }

        return sum(factors.values())
```

### Pattern 11: Approval With Context

Provide full context to approver:

```python
class ContextualApproval:
    async def request_approval(self, action):
        # Gather context
        context = {
            'action': {
                'type': action.type,
                'description': action.description,
                'parameters': action.params
            },
            'risk_analysis': await self.analyze_risk(action),
            'impact_assessment': await self.assess_impact(action),
            'alternatives': await self.suggest_alternatives(action),
            'rollback_plan': await self.create_rollback_plan(action),
            'similar_past_actions': await self.find_similar_actions(action)
        }

        # Send to approver with full context
        approval_request = ApprovalRequest(
            action=action,
            context=context,
            requested_by=action.agent_id,
            requested_at=datetime.now()
        )

        return await self.approval_service.submit(approval_request)
```

## Resource Guardrails

### Pattern 12: Multi-Dimensional Resource Limiting

Track multiple resource types:

```python
class ResourceGovernor:
    def __init__(self, limits):
        self.limits = limits
        self.usage = {
            'tokens': 0,
            'api_calls': 0,
            'execution_time': 0,
            'memory_mb': 0,
            'cost_usd': 0.0
        }

    async def check_and_track(self, resource_type, amount):
        # Check limit
        if self.usage[resource_type] + amount > self.limits[resource_type]:
            raise ResourceLimitExceeded(
                resource=resource_type,
                used=self.usage[resource_type],
                requested=amount,
                limit=self.limits[resource_type]
            )

        # Track usage
        self.usage[resource_type] += amount

    def get_remaining(self, resource_type):
        return self.limits[resource_type] - self.usage[resource_type]

# Usage
governor = ResourceGovernor(limits={
    'tokens': 100000,
    'api_calls': 1000,
    'execution_time': 300,  # seconds
    'memory_mb': 1024,
    'cost_usd': 10.0
})

# Before each operation
await governor.check_and_track('tokens', estimated_tokens)
await governor.check_and_track('api_calls', 1)
```

### Pattern 13: Adaptive Rate Limiting

Adjust limits based on behavior:

```python
class AdaptiveRateLimiter:
    def __init__(self):
        self.base_limit = 100  # requests per hour
        self.user_limits = {}

    async def check_limit(self, user_id):
        limit = self.get_user_limit(user_id)
        usage = await self.get_usage(user_id)

        if usage >= limit:
            raise RateLimitExceeded()

        await self.record_request(user_id)

    def get_user_limit(self, user_id):
        if user_id not in self.user_limits:
            self.user_limits[user_id] = {
                'limit': self.base_limit,
                'trust_score': 0.5
            }

        # Adjust limit based on trust score
        trust_score = self.user_limits[user_id]['trust_score']
        return int(self.base_limit * (0.5 + trust_score))

    async def update_trust_score(self, user_id, behavior):
        """Adjust trust based on behavior."""
        if behavior == 'good':
            # Increase trust, raise limit
            self.user_limits[user_id]['trust_score'] = min(
                1.0,
                self.user_limits[user_id]['trust_score'] + 0.1
            )
        elif behavior == 'bad':
            # Decrease trust, lower limit
            self.user_limits[user_id]['trust_score'] = max(
                0.0,
                self.user_limits[user_id]['trust_score'] - 0.2
            )
```

## Monitoring Guardrails

### Pattern 14: Anomaly Detection

Detect unusual patterns:

```python
class AnomalyDetector:
    def __init__(self):
        self.baseline = self.load_baseline()

    async def check_for_anomalies(self, agent_id, action):
        features = self.extract_features(action)

        # Compare to baseline
        deviation = self.calculate_deviation(features, self.baseline[agent_id])

        if deviation > 2.0:  # 2 standard deviations
            await self.alert_anomaly(
                agent_id=agent_id,
                action=action,
                deviation=deviation,
                features=features
            )

            # Optionally block anomalous action
            if deviation > 3.0:
                raise AnomalousActionBlocked()

    def extract_features(self, action):
        return {
            'time_of_day': datetime.now().hour,
            'action_type': action.type,
            'parameter_count': len(action.params),
            'affected_records': action.affected_records
        }
```

## Complete Guardrail System

### Pattern 15: Layered Guardrail Architecture

Combine all patterns:

```python
class ComprehensiveGuardrails:
    def __init__(self):
        # Input layer
        self.input_validators = InputGuardrails()

        # Output layer
        self.output_filters = OutputGuardrails()

        # Action layer
        self.action_whitelist = ActionWhitelist()
        self.preflight = PreFlightValidator()
        self.approval_router = ApprovalRouter()

        # Resource layer
        self.resource_governor = ResourceGovernor(...)

        # Monitoring layer
        self.anomaly_detector = AnomalyDetector()
        self.audit_logger = AuditLogger()

    async def execute_safely(self, user_input, agent):
        # 1. Input guardrails
        validated_input = await self.input_validators.validate(user_input)

        # 2. Process through agent
        raw_output = await agent.process(validated_input)

        # 3. Output guardrails
        safe_output = await self.output_filters.filter(raw_output)

        # If output includes actions...
        if safe_output.proposed_actions:
            for action in safe_output.proposed_actions:
                # 4. Action guardrails
                await self.action_whitelist.validate_action(
                    action.name,
                    action.params
                )
                await self.preflight.validate(action)

                # 5. Approval if needed
                if action.requires_approval():
                    approval = await self.approval_router.route_for_approval(action)
                    if not approval.approved:
                        continue

                # 6. Resource check
                await self.resource_governor.check_and_track(
                    'api_calls', 1
                )

                # 7. Anomaly detection
                await self.anomaly_detector.check_for_anomalies(
                    agent.id,
                    action
                )

                # 8. Execute with audit
                result = await self.execute_with_audit(action)

        return safe_output
```
