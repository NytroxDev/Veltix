# .vltxbench - Veltix benchmark configuration

## Structure

| Path | Description |
|------|-------------|
| `profiles/` | Saved benchmark profiles (TOML) |
| `profiles/default.toml` | Default profile, used when running `vltxbench` |
| `saved/` | JSON benchmark results with timestamps |
| `benchmarks/` | Custom external benchmarks (auto-detected) |

## Quick start

```bash
# Run default profile
vltxbench

# Run a specific profile
vltxbench --profile foo

# Run without project config (flags only)
vltxbench --tmp

# Re-generate this structure
vltxbench init
```
