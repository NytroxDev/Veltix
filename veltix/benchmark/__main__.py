"""
__main__.py
-----------
Package entry point — allows running the suite with:

    python -m benchmark
    python -m benchmark --only latency burst
    python -m benchmark --save results.json
"""

from .cli import main  # noqa: E402

if __name__ == "__main__":
    from veltix import Logger, LogLevel

    Logger.get_instance().set_level(LogLevel.ERROR)
    main()
