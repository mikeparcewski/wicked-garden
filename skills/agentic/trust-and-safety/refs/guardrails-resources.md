# Guardrail Implementation - Resources and Monitoring

Resource limiting, adaptive rate limiting, anomaly detection, and complete guardrail system architecture.

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
