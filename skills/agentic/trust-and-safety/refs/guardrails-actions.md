# Guardrail Implementation - Actions and Approvals

Action whitelisting, pre-flight validation, sandboxed execution, and approval workflows.

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
