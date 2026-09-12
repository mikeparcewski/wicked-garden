"""wicked-garden `draft` runtime — the self-checks behind the `wicked-garden-draft` skill.

Stdlib-only. Every module is both importable (pure functions the tests drive) and a CLI the
skill invokes through the launcher (`wicked-garden run scripts/draft/<x>.py …`):

* ``contrast_check``  — WCAG contrast (and a minimum print size) for every text-bearing element,
                        resolved from the document's own CSS (custom properties, alpha, media).
* ``page_count``      — rendered page count of a PDF (or a Chrome print of the HTML) against the
                        brief's page budget; a structural estimate when nothing can render.
* ``claims_scan``     — placeholders, uncited numbers, hidden mock labels, dangling
                        ``data-source`` paths and unsourced URLs in the visible text.
* ``self_check``      — the one command the worker runs before "done": all three, one verdict.
"""
