"""
__main__.py
-----------
Package entry point — allows running the suite with:

    python -m veltix.benchmark
    python -m veltix.benchmark --only latency burst
    python -m veltix.benchmark init
    python -m veltix.benchmark --save results.json
"""

from .cli import main

if __name__ == "__main__":
    main()
