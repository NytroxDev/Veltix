# Performance

Veltix 3.0.0 ships a Rust-powered hot path (parse / compile / buffering via `veltix._rust`) with
an automatic pure-Python fallback. Two independent comparisons:

- **Rust engine vs Python fallback (v3.2.0)** - Python 3.14.8, 12-core CPU, 30.5 GB RAM, Linux
  (loopback), 5-run averages.
- **Socket backends** (Threading vs Async, pure-Python path) - Python 3.14.8, same machine,
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

## Rust engine vs Python fallback (v3.2.0)

| Metric                          | Rust engine  | Python fallback | Gain      |
|---------------------------------|--------------|-----------------|-----------|
| Concurrent stress (100 clients) | 133,312 msg/s| 110,650 msg/s   | **+20%**  |
| Latency average                 | 0.049 ms     | 0.056 ms        | **-13%**  |
| Latency P95                     | 0.059 ms     | 0.078 ms        | **-24%**  |
| Latency P99                     | 0.086 ms     | 0.116 ms        | **-26%**  |
| Jitter                          | 0.015 ms     | 0.015 ms        | ±0 (outlier-bound) |
| Ping throughput                 | 18,954 ping/s| 16,559 ping/s   | **+14%**  |
| Burst send                      | 65,132 msg/s | 58,082 msg/s    | **+12%**  |
| FPS 64 tick stdev               | 0.233 ms     | 0.230 ms        | ±0 (noise) |
| Idle server memory              | ≈0 (noise)   | ≈0 (noise)      | 0%        |

> The Rust engine cuts framing/parse overhead: **-26% P99 latency**, **+20% throughput** under
> 100-client stress, and **+12% burst send**. FPS tick stability is comparable (both within run-to-run
> noise) and FPS *throughput* is tick-limited and unchanged, as expected. Jitter (stdev of consecutive
> ping deltas) is dominated by rare OS-scheduler outliers - a single >3 ms sample out of 250,000 - and
> landed within noise in this run. Results are workload-dependent and were measured on Veltix 3.2.0.

---

## Side-by-Side Summary (socket backends - pure-Python path)

| Metric                              | Threading        | Async            |
|-------------------------------------|------------------|------------------|
| Idle server memory                  | ≈0 (noise)       | ≈0 (noise floor) |
| Per client memory (avg)             | 91 KB            | 57 KB (noisy)    |
| Average latency                     | 0.041 ms         | 0.056 ms         |
| Burst send                          | 65 907 msg/s     | 56 675 msg/s     |
| Burst receive                       | 55 936 msg/s     | 44 146 msg/s     |
| Concurrent stress (100 clients)     | 52 596 msg/s     | **110 216 msg/s (2.1x)** |
| FPS simulation (64 players @ 64Hz)  | 4 490 msg/s      | 4 490 msg/s      |

> **Async stress throughput is 2.1x higher** than Threading - the selectors-based single-thread model eliminates context-switch overhead under high concurrency.
> Both backends score similarly on FPS simulations (bottleneck is the simulation logic, not the transport layer).
> Memory figures are RSS-based and noisy: both backends' idle measurement lands at or below the Python
> baseline (-170 KB and -240 KB - measurement noise floor) and Async's per-client cost spans 16-90 KB
> (median ~69 KB), while Threading's is 91 ± 27 KB.

---

## Memory Footprint

> RSS-based measurement; the leak-delta rows are dominated by allocator warm caches / fragmentation
> after the 10→50-client ramp and are **not** indicative of a Veltix leak (the idle benchmark shows no
> growth, and the leak delta reproduces identically with 10 clients only). Both backends' idle
> measurement lands at or below the Python baseline (-170 KB / -240 KB) - the measurement noise floor
> for this benchmark.

### Threading

| Metric               | Value                |
|----------------------|----------------------|
| Idle server          | -170 KB (below baseline - noise) |
| Per client (avg)     | 91 KB                |
| Per client (min/max) | 56 KB / 114 KB       |
| Per client (median)  | 110 KB               |
| Per client (stdev)   | 27 KB                |
| Server + 10 clients  | 33.30 MB             |
| Server + 50 clients  | 37.66 MB             |
| RSS after teardown   | +2,966 KB (leak delta - allocator noise) |

### Async

| Metric               | Value                |
|----------------------|----------------------|
| Idle server          | ≈0 above Python baseline (noise floor, measures -240 KB) |
| Per client (avg)     | 57 KB (measurement spans 16-90 KB) |
| Per client (min/max) | 16 KB / 90 KB        |
| Per client (median)  | 69 KB                |
| Per client (stdev)   | 31 KB                |
| Server + 10 clients  | 33.78 MB             |
| Server + 50 clients  | 37.04 MB             |
| RSS after teardown   | +2,226 KB (leak delta - allocator noise) |

> Threading's per-client cost reflects the per-thread overhead (91 KB median ~110 KB); Async's is
> noisier to measure (median ~69 KB) but consistently lower. Both backends' idle figures are at the
> measurement noise floor.

---

## Ping / Pong Latency

250 000 samples per backend (5 runs × 50 000 iterations), 100% success rate.

### Threading

| Metric     | Value         |
|------------|---------------|
| Average    | 0.041 ms      |
| Median P50 | 0.039 ms      |
| P95        | 0.049 ms      |
| P99        | 0.074 ms      |
| Min        | 0.031 ms      |
| Max        | 0.786 ms      |
| Stdev      | 0.008 ms      |
| Jitter     | 0.008 ms      |
| Throughput | 22 483 ping/s |

### Async

| Metric     | Value         |
|------------|---------------|
| Average    | 0.056 ms      |
| Median P50 | 0.054 ms      |
| P95        | 0.073 ms      |
| P99        | 0.110 ms      |
| Min        | 0.035 ms      |
| Max        | 1.634 ms      |
| Stdev      | 0.014 ms      |
| Jitter     | 0.014 ms      |
| Throughput | 16 805 ping/s |

> Threading has slightly lower latency (no selectors round-trip), but both backends remain well under
> 0.15 ms P99. Jitter (stdev of consecutive deltas) is dominated by rare scheduler outliers - e.g.
> the single >1.6 ms async sample out of 250 000.

---

## FPS Server Simulation

Both backends score identically (simulation logic is the bottleneck, not the transport layer).

| Scenario    | Tick rate                    | Throughput  | Success |
|-------------|------------------------------|-------------|---------|
| 64 players  | 63.8 Hz actual (target 64Hz) | 4 490 msg/s | 100%    |

Zero overruns, zero lost messages.

---

## Burst Throughput

10 000 messages × 64 bytes.

### Threading

| Metric         | Value        |
|----------------|--------------|
| Send           | 65 907 msg/s |
| Receive        | 55 936 msg/s |
| Data rate      | 3.41 MB/s    |
| Success rate   | 100%         |
| Total duration | 182.0 ms     |

### Async

| Metric         | Value        |
|----------------|--------------|
| Send           | 56 675 msg/s |
| Receive        | 44 146 msg/s |
| Data rate      | 2.69 MB/s    |
| Success rate   | 100%         |
| Total duration | 227.0 ms     |

> Threading edges ahead on burst traffic (~16% higher send throughput); both backends drain the full
> 10 000-message burst with zero loss. Async takes over under high concurrency (see below).

---

## Concurrent Stress

100 clients firing 100 messages simultaneously (10 000 total).

### Threading

| Metric             | Value        |
|--------------------|--------------|
| Throughput         | 52 596 msg/s |
| Success rate       | 100%         |
| Total duration     | 190.0 ms     |
| Time to first recv | 0.6 ms       |
| Per-client avg     | 1 054 msg/s  |
| Per-client stdev   | 256 msg/s    |

### Async

| Metric             | Value         |
|--------------------|---------------|
| Throughput         | **110 216 msg/s** |
| Success rate       | 100%          |
| Total duration     | **91.0 ms**   |
| Time to first recv | 0.5 ms        |
| Per-client avg     | 5 561 msg/s   |
| Per-client stdev   | 4 708 msg/s   |

> **Async is 2.1x faster under stress** - single-thread selectors eliminate Python GIL contention between client-handler threads.
> Threading still handles 52k+ msg/s with zero failures; the GIL is the limiter at high concurrency.
