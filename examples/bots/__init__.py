"""Named, runnable bot recipes — one reusable pattern per file (no network).

Every bot exposes an async ``main()`` and an ``asyncio.run`` guard, so each
file is both a documentation artifact and a script:

    uv run python examples/bots/echo_bot.py

(The package sources live under src/, so if the import is not found, prefix
PYTHONPATH=src as with the phase examples. pytest runs them via the
tool.pytest.ini_options pythonpath setting.)
"""
