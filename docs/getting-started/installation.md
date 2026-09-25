# Installation

## Requirements

- Python **3.11+**
- No runtime dependencies (pure stdlib, zero third-party packages)

## The Rust engine

Since v3.0.0, the message hot path (parse, compile, buffering) is compiled in Rust and ships as a
`cp311-abi3` extension inside the prebuilt wheels - one wheel per platform covers Python 3.11+.
No toolchain is needed to install or run Veltix:

- If the compiled `veltix._rust` extension is available, it is used automatically.
- Otherwise (or with `VELTIX_DISABLE_RUST=1`), Veltix falls back to the pure-Python implementation
  transparently.
- At runtime you can also switch in code: `veltix.disable_rust()` / `veltix.enable_rust()`. The
  engine is captured when a `Server`/`Client` is (re)initialized, so the switch affects new
  instances and `server.restart()`.

## Install from PyPI

```bash
pip install veltix
```

## Install latest from GitHub

```bash
pip install git+https://github.com/NytroxDev/Veltix.git
```

> Building from source (e.g. `pip install git+...`) requires a Rust toolchain; the maturin build
> backend handles it automatically with build isolation.

## Verify installation

```python
import veltix
print(veltix.__version__)

from veltix.network import _rust
print(_rust.rust_enabled())  # True when the compiled Rust engine is active
```