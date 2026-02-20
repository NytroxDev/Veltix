# Contributing to Veltix

Contributions of any kind are welcome — bug reports, feature requests, documentation improvements, or code changes. This guide explains how to get involved effectively.

---

## Code of Conduct

All contributors are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md). Be respectful and constructive.

---

## Reporting Bugs

Before opening a bug report, check if the issue already exists in the [issue tracker](https://github.com/NytroxDev/Veltix/issues).

A good bug report includes:

- Python version and operating system
- Minimal reproduction steps
- Expected behavior vs. actual behavior
- Full error message and traceback if applicable

---

## Suggesting Features

Before suggesting a new feature:

- Check the [Roadmap](README.md#roadmap) to see if it is already planned
- Consider whether it fits Veltix's philosophy: simple, zero dependencies, focused scope

Open an issue with a clear description of the use case and the proposed behavior.

---

## Contributing Code

### Setup

Veltix has no runtime dependencies. Getting started is straightforward:

```bash
git clone https://github.com/NytroxDev/Veltix.git
cd Veltix
```

Optional development tools:

```bash
pip install pytest ruff
```

### Workflow

1. Fork the repository
2. Create a branch for your change:
   ```bash
   git checkout -b fix/issue-description
   ```
3. Make your changes
4. Run the tests:
   ```bash
   python -m pytest tests/
   ```
5. Commit with a clear message:
   ```bash
   git commit -m "Fix: description of what was fixed and why"
   ```
6. Push and open a Pull Request

### Code Style

- Follow **PEP 8**
- Use **type hints** on all public methods
- Write **docstrings** for all public classes and methods (Google style)
- Keep the code readable — clarity over cleverness
- Do not add external dependencies

```python
def send_message(self, data: bytes, client: ClientInfo) -> bool:
    """
    Send a message to a specific client.

    Args:
        data: Message bytes to send
        client: Target client information

    Returns:
        True if send succeeded, False otherwise
    """
```

### Pull Request Checklist

- [ ] Code follows the project style
- [ ] Docstrings added or updated
- [ ] Tests added or updated
- [ ] All tests pass
- [ ] Documentation updated if needed
- [ ] No new dependencies introduced

---

## Other Ways to Help

You do not need to write code to contribute meaningfully:

- **Star the project** on GitHub to increase visibility
- **Report bugs** or unclear documentation
- **Improve the docs** — fix typos, clarify explanations, add examples
- **Answer questions** in issues or on Discord
- **Share the project** if you find it useful

---

## Questions

- Open an issue with a `[Question]` tag
- Join the Discord: [discord.gg/NrEjSHtfMp](https://discord.gg/NrEjSHtfMp)
- Email: nytrox.dev@gmail.com
