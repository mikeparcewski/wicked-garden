# Security Lens

Additional questions for the five lenses when the work involves authentication,
authorization, data protection, compliance, or security posture.

## Lens 1 Additions: Is This Real?

- Is this an actual vulnerability, or a theoretical risk with no practical exploit?
- Is the security scanner correct, or is this a false positive?
- Is the risk in our code, or in a dependency we don't control?
- What's the actual threat model? Who would exploit this and how?

## Lens 2 Additions: What's Actually Going On?

- Is the auth logic wrong, or is the trust boundary in the wrong place?
- Is this a missing check, or is the entire authorization model flawed?
- Is sensitive data exposed because of a code bug, or because the data flow
  shouldn't include it at all?
- Is the vulnerability in the feature, or in the error handling around it?

## Lens 3 Additions: What Else Can We Fix?

- Are other endpoints/surfaces vulnerable to the same class of attack?
- Are secrets managed consistently, or are there hardcoded values elsewhere?
- Is input validation applied uniformly at trust boundaries?
- Are there other places where we trust input we shouldn't?
- Can we add security headers, CSP rules, or rate limits broadly?

## Lens 4 Additions: Should We Rethink?

- Should we move to a zero-trust model instead of perimeter-based?
- Would a policy engine replace scattered authorization checks?
- Should secrets management be centralized instead of per-service?
- Would encryption at rest eliminate the risk class entirely?
- Should we use allowlists instead of denylists?

## Lens 5 Additions: Better Way?

- Can we eliminate the sensitive data instead of protecting it?
- Can we use a framework/library security primitive instead of custom code?
- Can we shift this to infrastructure (WAF, service mesh) instead of application?
- Can we make the secure path the default, so insecure requires explicit opt-in?
- Can automated scanning catch this class of issue going forward?
