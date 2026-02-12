"""Wrapper to run mutatest with Python 3.12 compatibility patch.

Mutatest 3.1.0 passes a set to random.sample() at run.py:530, which
Python 3.12 rejects (requires a sequence). This wrapper monkey-patches
random.sample to accept sets by converting them to lists first.

See: https://github.com/EvanKepner/mutatest/issues (unmaintained, 3.1.0 is latest)
"""

import random
import sys

_original_sample = random.sample


def _patched_sample(population, k, *, counts=None):  # type: ignore[no-untyped-def]
    """Wrap random.sample to convert sets/dicts to lists for Py3.12 compat."""
    if isinstance(population, (set, frozenset, dict)):
        population = sorted(population, key=str)
    if counts is not None:
        return _original_sample(population, k, counts=counts)
    return _original_sample(population, k)


random.sample = _patched_sample  # type: ignore[assignment]

# Now run mutatest CLI with parsed args
from mutatest.cli import cli_args, main

parsed = cli_args(sys.argv[1:])
main(parsed)
