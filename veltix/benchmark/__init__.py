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

    # Compare two saved results
    python -m benchmark cmp v1.8.1 v1.8.2
    python -m benchmark compare v1.8.1 v1.8.2

Available benchmark IDs: memory, latency, fps, burst, stress
"""
