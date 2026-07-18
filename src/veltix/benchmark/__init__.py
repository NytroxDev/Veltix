"""
Veltix benchmark suite.

Requires ``psutil`` — install with ``pip install veltix[benchmark]``.

Usage
-----
    # Run all benchmarks
    python -m veltix.benchmark

    # Run specific benchmarks
    python -m veltix.benchmark --only memory latency burst

    # Save results to JSON
    python -m veltix.benchmark --save results.json

    # CLI entry points (installed with ``veltix[benchmark]``)
    vltxbench
    veltix-benchmark

Available benchmark IDs: memory, latency, fps, burst, stress
"""
