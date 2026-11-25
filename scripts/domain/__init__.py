"""wicked-garden domain extraction (J6 v3).

``run.py`` is the one entry point: a scoped run that finds the targets, states and checks each
decision through the run's own seats (``wicked-core model-call``), writes the prose over the checked
statements, and stores it all on the estate nodes (``store.py``), where ``wicked-core domain-graph``
builds the domain model. ``validate_domain_model.py`` checks a document against the vendored schema
(``skills/domain/vendor/domain-model.schema.json``). Garden imports no other-product code: it shells
``wicked-estate`` and ``wicked-core``.
"""
