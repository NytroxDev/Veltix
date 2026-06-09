# Performance

> Benchmarked on Python 3.14.5 : 12-core CPU (6 physical), 30.5 GB RAM, Linux (loopback).
> All numbers are **5-run averages** (`--runs 5`). Latency uses **250 000 iterations** (`--latency-iterations 250000`).

To run the benchmarks yourself:

```bash
# Run all benchmarks on both backends
python -m veltix.benchmark --socket-core both --runs 5

# Run specific benchmarks
python -m veltix.benchmark --only memory latency burst --socket-core both

# Save results to JSON
python -m veltix.benchmark --save results.json
```

---

## Side-by-Side Summary

| Metric                              | Threading        | Async            |
|-------------------------------------|------------------|------------------|
| Idle server memory                  | 45.6 KB          | 4 KB             |
| Per client memory (avg)             | 36.08 KB         | 12.4 KB          |
| Average latency                     | 0.032 ms         | 0.035 ms         |
| Burst send                          | 52 109 msg/s     | 52 296 msg/s     |
| Burst receive                       | 41 327 msg/s     | 41 343 msg/s     |
| Concurrent stress (100 clients)     | 37 676 msg/s     | **76 929 msg/s** |
| FPS simulation (64 players @ 64Hz)  | 4 488 msg/s      | 4 488 msg/s      |
| FPS simulation (128 players @ 20Hz) | 2 812 msg/s      | 2 812 msg/s      |

> **Async stress throughput is 2x higher** than Threading — the selectors-based single-thread model eliminates context-switch overhead under high concurrency.
> Both backends score identically on FPS simulations (bottleneck is the simulation logic, not the transport layer).

---

## Memory Footprint

### Threading

| Metric               | Value                |
|----------------------|----------------------|
| Idle server          | +45.6 KB above Python baseline |
| Per client (avg)     | 36.08 KB             |
| Per client (min/max) | 17.6 KB / 45.6 KB    |
| Per client (median)  | — (N/A in new model) |
| Per client (stdev)   | 10.7 KB              |
| Server + 10 clients  | 22.1 MB              |
| Server + 50 clients  | 24.39 MB             |
| RSS after teardown   | +423 KB (leak delta) |

### Async

| Metric               | Value                |
|----------------------|----------------------|
| Idle server          | +4 KB above Python baseline |
| Per client (avg)     | 12.4 KB              |
| Per client (min/max) | 4 KB / 16 KB         |
| Server + 10 clients  | 22.82 MB             |
| Server + 50 clients  | 23.63 MB             |
| RSS after teardown   | +21 KB (leak delta)  |

> Memory per client dropped **40%** (threading: 60.4 KB → 36.08 KB) and **74%** (async: 12.4 KB).
> Leak delta reduced from 1.645 MB to **423 KB** (threading) and **21 KB** (async) — mostly warm CPU caches.

---

## Ping / Pong Latency

250 000 iterations per backend, 100% success rate.

### Threading

| Metric     | Value         |
|------------|---------------|
| Average    | 0.032 ms      |
| Median P50 | 0.030 ms      |
| P95        | 0.042 ms      |
| P99        | 0.070 ms      |
| Min        | 0.022 ms      |
| Max        | 2.690 ms      |
| Stdev      | 0.020 ms      |
| Jitter     | 0.021 ms      |
| Throughput | 29 461 ping/s |

### Async

| Metric     | Value         |
|------------|---------------|
| Average    | 0.035 ms      |
| Median P50 | 0.035 ms      |
| P95        | 0.048 ms      |
| P99        | 0.079 ms      |
| Min        | 0.023 ms      |
| Max        | 2.700 ms      |
| Stdev      | 0.014 ms      |
| Jitter     | 0.023 ms      |
| Throughput | 26 625 ping/s |

> Threading has slightly lower latency (no selectors round-trip), but both backends remain well under 0.1 ms P99.
> Async shows lower stdev (more consistent) due to the single-thread scheduling.

---

## FPS Server Simulation

Both backends score identically (simulation logic is the bottleneck, not the transport layer).

| Scenario    | Tick rate                    | Throughput  | Success |
|-------------|------------------------------|-------------|---------|
| 64 players  | 63.7 Hz actual (target 64Hz) | 4 488 msg/s | 100%    |
| 128 players | 20.0 Hz actual (target 20Hz) | 2 812 msg/s | 100%    |

Zero overruns, zero lost messages in both scenarios.

---

## Burst Throughput

10 000 messages × 64 bytes.

### Threading

| Metric         | Value        |
|----------------|--------------|
| Send           | 52 109 msg/s |
| Receive        | 41 327 msg/s |
| Data rate      | 2.48 MB/s    |
| Success rate   | 100%         |
| Total duration | 242.0 ms     |

### Async

| Metric         | Value        |
|----------------|--------------|
| Send           | 52 296 msg/s |
| Receive        | 41 343 msg/s |
| Data rate      | 2.49 MB/s    |
| Success rate   | 100%         |
| Total duration | 244.1 ms     |

> Near-identical burst performance — both backends hit the same loopback stack limits.
> Async recovers burst performance to within ~2% of v1.6.10 after hot-path optimisations (broadcast compile-once, unpack_from, bytearray passthrough).

---

## Concurrent Stress

100 clients firing 100 messages simultaneously (10 000 total).

### Threading

| Metric             | Value        |
|--------------------|--------------|
| Throughput         | 37 676 msg/s |
| Success rate       | 100%         |
| Total duration     | 267.0 ms     |
| Time to first recv | 0.8 ms       |
| Per-client avg     | 377 msg/s    |
| Per-client stdev   | 69 msg/s     |

### Async

| Metric             | Value         |
|--------------------|---------------|
| Throughput         | **76 929 msg/s** |
| Success rate       | 100%          |
| Total duration     | **136.0 ms**  |
| Time to first recv | 0.6 ms        |
| Per-client avg     | 769 msg/s     |
| Per-client stdev   | 89 msg/s      |

> **Async is 2x faster under stress** — single-thread selectors eliminate Python GIL contention between client-handler threads.
> Threading still handles 37k+ msg/s with zero failures; the GIL is the limiter at high concurrency.
