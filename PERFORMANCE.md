# Performance

> Benchmarked on Python 3.14.4 : 12-core CPU (6 physical), 30.5 GB RAM, Linux (loopback).

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
| Idle server memory                  | 84 KB                       |
| Per client memory                   | 66.8 KB                     |
| Average latency                     | 0.005 ms                    |
| Burst send                          | 90,999 msg/s                |
| Burst receive                       | 62,514 msg/s                |
| Concurrent stress (100 clients)     | 52,930 msg/s : 100% success |
| FPS simulation (64 players @ 64Hz)  | 4,490 msg/s : 100% success  |
| FPS simulation (128 players @ 20Hz) | 2,813 msg/s : 100% success  |

---

## Memory Footprint

| Metric               | Value                        |
|----------------------|------------------------------|
| Idle server          | +84 KB above Python baseline |
| Per client (avg)     | 66.8 KB                      |
| Per client (min/max) | 52 KB / 88 KB                |
| Server + 10 clients  | 21.3 MB                      |
| Server + 50 clients  | 23.83 MB                     |

---

## Ping / Pong Latency

2,000 iterations, 100% success rate.

| Metric     | Value         |
|------------|---------------|
| Average    | 0.005 ms      |
| Median P50 | 0.000 ms      |
| P95        | 0.000 ms      |
| P99        | 0.000 ms      |
| Max        | 1.000 ms      |
| Throughput | 46,191 ping/s |

99.5% of pings complete in under 0.1ms.

---

## FPS Server Simulation

| Scenario    | Tick rate                    | Throughput  | Success |
|-------------|------------------------------|-------------|---------|
| 64 players  | 63.8 Hz actual (target 64Hz) | 4,490 msg/s | 100%    |
| 128 players | 20.0 Hz actual (target 20Hz) | 2,813 msg/s | 100%    |

Zero overruns, zero lost messages in both scenarios.

---

## Burst Throughput

10,000 messages × 64 bytes.

| Metric         | Value        |
|----------------|--------------|
| Send           | 90,999 msg/s |
| Receive        | 62,514 msg/s |
| Data rate      | 3.82 MB/s    |
| Success rate   | 100%         |
| Total duration | 160 ms       |

---

## Concurrent Stress

100 clients firing 100 messages simultaneously (10,000 total).

| Metric             | Value        |
|--------------------|--------------|
| Throughput         | 52,930 msg/s |
| Success rate       | 100%         |
| Total duration     | 188.9 ms     |
| Time to first recv | 1.3 ms       |
| Per-client avg     | 6,229 msg/s  |