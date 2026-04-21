"""
Veltix benchmark suite.

Usage
-----
    # Run all benchmarks
    python -m benchmark

    # Run specific benchmarks
    python -m benchmark --only memory latency burst

    # Save results to JSON
    python -m benchmark --save results.json

    # Adjust parameters
    python -m benchmark --latency-iterations 5000 --stress-clients 200

Available benchmark IDs: memory, latency, fps, burst, stress
"""
