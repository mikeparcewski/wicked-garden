"""crew.detectors — steering detector registry.

PR-2 of the steering detector epic (#679) ships the first real detector:
``sensitive_path``. Each detector is a pure stdlib module that:

  1. Takes some observed input (changed paths, gate verdicts, test results, ...)
  2. Returns a list of payloads that conform to ``crew.steering_event_schema``
  3. Optionally provides an emitter helper to push those payloads onto wicked-bus

Detectors and emitters are kept SEPARATE so that tests can validate payload
shape without touching the bus.
"""
