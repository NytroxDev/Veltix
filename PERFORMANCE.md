# Performance

Veltix 3.0.0 ships a Rust-powered hot path (parse / compile / buffering via `veltix._rust`) with
an automatic pure-Python fallback. Two independent comparisons:

- **Rust engine vs Python fallback (v3.0.0)** - Python 3.14.7, 12-core CPU, 30.5 GB RAM, Linux
  (loopback), 5-run averages.
- **Socket backends** (Threading vs Async, pure-Python path) - Python 3.14.7, same machine,
  5-run averages. Latency figures aggregate the default 50 000 iterations per run (250 000 samples
  across the 5 runs).

To run the benchmarks yourself (requires the benchmark extra: `pip install veltix[benchmark]`):

```bash
# Run all benchmarks with the Rust engine - 5-run averages, saved for comparison
vltxbench --engine rust --runs 5 --save rust.json

# Same suite with the pure-Python fallback (run sequentially - no CPU contention)
vltxbench --engine python --runs 5 --save python.json

# Compare the two engines (validates versioned file format + engine rows)
vltxbench --compare rust.json python.json

# Run specific benchmarks
vltxbench --only memory latency burst

# Compare socket backends (Threading vs Async, pure-Python path)
vltxbench --engine python --socket-core both --runs 5 --save backends.json

# The reported latency figures use 50 000 iterations per run by default
# (250 000 samples across the 5 runs); override with --latency-iterations
```

---

## Rust engine vs Python fallback (v3.0.0)

| Metric                          | Rust engine  | Python fallback | Gain      |
|---------------------------------|--------------|-----------------|-----------|
| Concurrent stress (100 clients) | 137,995 msg/s| 106,486 msg/s   | **+30%**  |
| Latency average                 | 0.041 ms     | 0.047 ms        | **-13%**  |
| Latency P95                     | 0.048 ms     | 0.061 ms        | **-21%**  |
| Latency P99                     | 0.066 ms     | 0.096 ms        | **-31%**  |
| Jitter                          | 0.019 ms     | 0.014 ms        | ±0 (outlier-bound) |
| Ping throughput                 | 22,582 ping/s| 19,706 ping/s   | **+15%**  |
| Burst send                      | 71,376 msg/s | 59,408 msg/s    | **+20%**  |
| FPS 64 tick stdev               | 0.175 ms     | 0.343 ms        | **-49%**  |
| Idle server memory              | 60.8 KB      | 60.8 KB         | 0%        |

> The Rust engine cuts framing/parse overhead: **-31% P99 latency**, **+30% throughput** under
> 100-client stress, **+20% burst send**, and steadier FPS ticks (stdev **-49%**). FPS *throughput*
> is tick-limited and unchanged, as expected. Jitter (stdev of consecutive ping deltas) is dominated
> by rare OS-scheduler outliers - a single >3 ms sample out of 250,000 - and landed within noise in
> this run (±0.005 ms). Results are workload-dependent and were measured on Veltix 3.0.0.

---

## Side-by-Side Summary (socket backends - pure-Python path)

| Metric                              | Threading        | Async            |
|-------------------------------------|------------------|------------------|
| Idle server memory                  | 60.8 KB          | ≈0 (noise floor) |
| Per client memory (avg)             | 111 KB           | ≈80 KB (noisy)   |
| Average latency                     | 0.041 ms         | 0.050 ms         |
| Burst send                          | 64 158 msg/s     | 60 358 msg/s     |
| Burst receive                       | 48 558 msg/s     | 46 351 msg/s     |
| Concurrent stress (100 clients)     | 51 505 msg/s     | **108 084 msg/s (2.1x)** |
| FPS simulation (64 players @ 64Hz)  | 4 489 msg/s      | 4 490 msg/s      |

> **Async stress throughput is 2.1x higher** than Threading - the selectors-based single-thread model eliminates context-switch overhead under high concurrency.
> Both backends score similarly on FPS simulations (bottleneck is the simulation logic, not the transport layer).
> Memory figures are RSS-based and noisy: Async's idle lands *below* the Python baseline (-240 KB -
> measurement noise floor) and its per-client cost spans 16-80 KB (median ~80 KB), while Threading's
> per-client cost is tight (111 ± 3 KB).

---

## Memory Footprint

> RSS-based measurement; the leak-delta rows are dominated by allocator warm caches / fragmentation
> after the 10→50-client ramp and are **not** indicative of a Veltix leak (the idle benchmark shows no
> growth, and the leak delta reproduces identically with 10 clients only). Async's idle lands *below*
> the Python baseline (-240 KB) - the measurement noise floor for this benchmark.

### Threading

| Metric               | Value                |
|----------------------|----------------------|
| Idle server          | +60.8 KB above Python baseline |
| Per client (avg)     | 111 KB               |
| Per client (min/max) | 107 KB / 117 KB      |
| Per client (median)  | 110 KB               |
| Per client (stdev)   | 3.0 KB               |
| Server + 10 clients  | 32.87 MB             |
| Server + 50 clients  | 37.33 MB             |
| RSS after teardown   | +3,495 KB (leak delta - allocator noise) |

### Async

| Metric               | Value                |
|----------------------|----------------------|
| Idle server          | ≈0 above Python baseline (noise floor, measures -240 KB) |
| Per client (avg)     | 56 KB (measurement spans 16-81 KB) |
| Per client (min/max) | 16 KB / 82 KB        |
| Per client (median)  | 80 KB                |
| Per client (stdev)   | 31.5 KB              |
| Server + 10 clients  | 33.44 MB             |
| Server + 50 clients  | 36.64 MB             |
| RSS after teardown   | +2,049 KB (leak delta - allocator noise) |

> Threading's per-client cost is tight (111 ± 3 KB) and reflects the per-thread overhead; Async's is
> noisier to measure (median ~80 KB) but consistently lower. Numbers reproduced across two
> consecutive campaigns.

---

## Ping / Pong Latency

250 000 samples per backend (5 runs × 50 000 iterations), 100% success rate.

### Threading

| Metric     | Value         |
|------------|---------------|
| Average    | 0.041 ms      |
| Median P50 | 0.039 ms      |
| P95        | 0.052 ms      |
| P99        | 0.089 ms      |
| Min        | 0.031 ms      |
| Max        | 1.299 ms      |
| Stdev      | 0.011 ms      |
| Jitter     | 0.012 ms      |
| Throughput | 22 469 ping/s |

### Async

| Metric     | Value         |
|------------|---------------|
| Average    | 0.050 ms      |
| Median P50 | 0.046 ms      |
| P95        | 0.068 ms      |
| P99        | 0.115 ms      |
| Min        | 0.032 ms      |
| Max        | 3.784 ms      |
| Stdev      | 0.033 ms      |
| Jitter     | 0.033 ms      |
| Throughput | 18 777 ping/s |

> Threading has slightly lower latency (no selectors round-trip), but both backends remain well under
> 0.15 ms P99. Jitter (stdev of consecutive deltas) is dominated by rare scheduler outliers - e.g.
> Async's single >3.7 ms sample out of 250 000.

---

## FPS Server Simulation

Both backends score identically (simulation logic is the bottleneck, not the transport layer).

| Scenario    | Tick rate                    | Throughput  | Success |
|-------------|------------------------------|-------------|---------|
| 64 players  | 63.8 Hz actual (target 64Hz) | 4 489 msg/s | 100%    |

Zero overruns, zero lost messages.

---

## Burst Throughput

10 000 messages × 64 bytes.

### Threading

| Metric         | Value        |
|----------------|--------------|
| Send           | 64 158 msg/s |
| Receive        | 48 558 msg/s |
| Data rate      | 2.96 MB/s    |
| Success rate   | 100%         |
| Total duration | 206.0 ms     |

### Async

| Metric         | Value        |
|----------------|--------------|
| Send           | 60 358 msg/s |
| Receive        | 46 351 msg/s |
| Data rate      | 2.83 MB/s    |
| Success rate   | 100%         |
| Total duration | 215.8 ms     |

> Both backends land within ~6% of each other on burst traffic; Threading edges ahead on peak send
> throughput, Async on sustained load.

---

## Concurrent Stress

100 clients firing 100 messages simultaneously (10 000 total).

### Threading

| Metric             | Value        |
|--------------------|--------------|
| Throughput         | 51 505 msg/s |
| Success rate       | 100%         |
| Total duration     | 194.2 ms     |
| Time to first recv | 0.4 ms       |
| Per-client avg     | 1 026 msg/s  |
| Per-client stdev   | 236 msg/s    |

### Async

| Metric             | Value         |
|--------------------|---------------|
| Throughput         | **108 084 msg/s** |
| Success rate       | 100%          |
| Total duration     | **92.5 ms**   |
| Time to first recv | 0.5 ms        |
| Per-client avg     | 4 538 msg/s   |
| Per-client stdev   | 2 791 msg/s   |

> **Async is 2.1x faster under stress** - single-thread selectors eliminate Python GIL contention between client-handler threads.
> Threading still handles 51k+ msg/s with zero failures; the GIL is the limiter at high concurrency.
