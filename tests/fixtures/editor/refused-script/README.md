# Refused script conformance fixture

Scaffold plumbing plus one generated inline script, a hidden button with an inline
`onclick` handler, and a hidden `javascript:` link. A zero-delay callback triggers
all three once per document. They are harmless under the old unsafe-inline policy,
and all three produce browser CSP refusals under crew's served policy. Case 9 must
fail with the refusal kinds and count; all other base cases pass.
