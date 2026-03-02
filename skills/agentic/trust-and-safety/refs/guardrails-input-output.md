# Guardrail Implementation - Input and Output Patterns

Input validation, sanitization, prompt injection detection, and output filtering patterns.

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
