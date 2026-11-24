# Hostile DOM conformance fixture

Scaffold plumbing with two deliberate UX defects: a running animation under reduced
motion and a visible button that immediately blurs on focus. The editor replaces
`document.querySelectorAll`, `document.getAnimations`, and `HTMLElement.prototype.focus`
to conceal both from probes in its JavaScript world. Cases 10 and 11 must observe
the defects from an isolated world. The artifact rendering and protocol remain the
scaffold's, so other base cases pass.
