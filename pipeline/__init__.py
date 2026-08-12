"""Golden Hour — GER casualty-archetype pipeline.

Generator → Evaluator → Refiner, with a circuit breaker, producing rows for the
Unreal DataTable `DT_CasualtyArchetypes`.

Deliberately empty of re-exports: importing this package must not pull in the
Anthropic SDK or read the knowledge base, so `--selftest` stays fast and
credential-free. Import the modules you need directly.
"""

__version__ = "0.1.0"
