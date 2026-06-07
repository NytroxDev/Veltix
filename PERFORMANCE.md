# Performance

> Benchmarked on Python 3.14.5 : 12-core CPU (6 physical), 30.5 GB RAM, Linux (loopback).

To run the benchmarks yourself :

```bash
# Run all benchmarks
python -m veltix.benchmark

# Run specific benchmarks
python -m veltix.benchmark --only memory latency burst

# Save results to JSON
python -m veltix.benchmark --save results.json
```

## Summary

| Metric                              | Result                      |
|-------------------------------------|-----------------------------|
| Idle server memory                  | 212 KB                      |
| Per client memory (avg)             | 70.8 KB                     |
| Average latency                     | 0.049 ms                    |
| Burst send                          | 50,467 msg/s                |
| Burst receive                       | 40,286 msg/s                |
| Concurrent stress (100 clients)     | 32,073 msg/s : 100% success |
| FPS simulation (64 players @ 64Hz)  | 4,488 msg/s : 100% success  |
| FPS simulation (128 players @ 20Hz) | 2,812 msg/s : 100% success  |

---

## Memory Footprint

| Metric               | Value                        |
|----------------------|------------------------------|
| Idle server          | +212 KB above Python baseline|
| Per client (avg)     | 70.8 KB                      |
| Per client (min/max) | 56 KB / 100 KB               |
| Per client (median)  | 70 KB                        |
| Per client (stdev)   | 12.23 KB                     |
| Server + 10 clients  | 21.59 MB                     |
| Server + 50 clients  | 24.07 MB                     |
| RSS after teardown   | 22.61 MB (+1.92 MB ⚠)       |

---

## Ping / Pong Latency

2,000 iterations, 100% success rate.

| Metric     | Value         |
|------------|---------------|
| Average    | 0.049 ms      |
| Median P50 | 0.039 ms      |
| P95        | 0.087 ms      |
| P99        | 0.166 ms      |
| Min        | 0.026 ms      |
| Max        | 0.796 ms      |
| Stdev      | 0.040 ms      |
| Jitter     | 0.047 ms      |
| Throughput | 18,829 ping/s |

96.9% of pings complete in under 0.1ms.

---

## FPS Server Simulation

| Scenario    | Tick rate                    | Throughput  | Success |
|-------------|------------------------------|-------------|---------|
| 64 players  | 63.7 Hz actual (target 64Hz) | 4,488 msg/s | 100%    |
| 128 players | 20.0 Hz actual (target 20Hz) | 2,812 msg/s | 100%    |

Zero overruns, zero lost messages in both scenarios.

---

## Burst Throughput

10,000 messages × 64 bytes.

| Metric         | Value        |
|----------------|--------------|
| Send           | 50,467 msg/s |
| Receive        | 40,286 msg/s |
| Data rate      | 2.46 MB/s    |
| Success rate   | 100%         |
| Total duration | 248.2 ms     |

---

## Concurrent Stress

100 clients firing 100 messages simultaneously (10,000 total).

| Metric             | Value        |
|--------------------|--------------|
| Throughput         | 32,073 msg/s |
| Success rate       | 100%         |
| Total duration     | 311.8 ms     |
| Time to first recv | 1.6 ms       |
| Per-client avg     | 3,955 msg/s  |
| Per-client stdev   | 942 msg/s    |