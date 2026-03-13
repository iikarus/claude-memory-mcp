# Vulture whitelist — known false positives
# These are required by Python protocols but appear unused to static analysis.

# Context manager __exit__ protocol parameters
exc_type  # noqa
exc_val  # noqa
exc_tb  # noqa
