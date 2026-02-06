# Contributing to Veltix

Thank you for considering contributing to Veltix! 🎉

We welcome contributions from everyone, whether you're fixing bugs, adding features, improving documentation, or just spreading the word. **Veltix is built to be accessible for beginners while powerful enough for production use.**

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Current Development Status](#current-development-status)
- [First Time Contributing?](#first-time-contributing-)
- [How to Contribute](#how-to-contribute)
  - [Reporting Bugs](#reporting-bugs-)
  - [Suggesting Features](#suggesting-features-)
  - [Code Contributions](#code-contributions-)
- [Development Setup](#development-setup)
- [Technical Areas to Contribute](#technical-areas-to-contribute)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)
- [Other Ways to Contribute](#other-ways-to-contribute)

---

## Code of Conduct

Be respectful, inclusive, and constructive. We're building a welcoming community where everyone can learn and contribute.

---

## Current Development Status

- **v1.0.0** (in progress) - Basic TCP + binary protocol with message integrity
- **v2.0.0** (planned) - End-to-end encryption (ChaCha20-Poly1305)
- **v3.0.0** (future) - Rust performance layer for extreme speed

**Right now, contributions focus on v1.0.0 stability and documentation.**

For v2/v3 ideas, open an issue tagged `[Future]` to discuss!

---

## First Time Contributing? 🌱

Never contributed to open source before? **No problem!** We're here to help.

### Good First Issues

Look for issues tagged with:
- `good first issue` - Perfect for beginners, no deep knowledge required
- `documentation` - Improve docs, no coding needed
- `help wanted` - We need your help on this!

### Step-by-Step Guide for Complete Beginners

1. **Find an issue you like** (or create one if you found a bug/have an idea!)
2. **Comment:** "I'd like to work on this" 
3. **Wait for confirmation** from maintainers (usually within 1-3 days)
4. **Fork the repo** (click the "Fork" button on GitHub)
5. **Make your changes** in your fork (see [Development Setup](#development-setup))
6. **Test everything works** (run examples and tests)
7. **Submit a Pull Request** (see [Pull Request Process](#pull-request-process))
8. **Wait for review** (be patient, we're all volunteers!)
9. **Make changes** if requested (this is normal and part of the process)
10. **Celebrate! 🎉** Your first contribution is merged!

### Need Help?

- Check existing Issues for similar questions
- Open a new Issue with `[Question]` tag
- Be specific: include error messages, code snippets, Python version
- Be patient: we're all volunteers with day jobs

**Remember:** Everyone was a beginner once. There are no stupid questions. Ask away!

---

## How to Contribute

### Reporting Bugs 🐛

Found a bug? Here's how to report it:

1. **Check if it already exists** in [Issues](https://github.com/YOUR-USERNAME/veltix/issues)
2. **Open a new issue** with the `[Bug]` tag
3. **Include:**
   - Clear title describing the problem
   - Steps to reproduce the bug
   - Expected behavior vs actual behavior
   - Python version (`python --version`)
   - Operating System (Windows, macOS, Linux)
   - Error messages (full traceback if possible)
   - Minimal code example that reproduces the issue

**Example bug report:**
```markdown
**Title:** Server crashes when client disconnects during send

**Description:**
When a client disconnects while the server is sending data, the server crashes with a BrokenPipeError.

**To Reproduce:**
1. Start server with examples/echo_server.py
2. Connect a client
3. Close client immediately after connecting
4. Server crashes

**Expected:** Server should handle disconnect gracefully

**Environment:**
- Python 3.11.5
- Ubuntu 22.04
- Veltix 1.0.0

**Error:**
```
BrokenPipeError: [Errno 32] Broken pipe
...
```
```

### Suggesting Features 💡

Have an idea? We'd love to hear it!

1. **Open an issue** with `[Feature Request]` tag
2. **Explain:**
   - What problem does it solve?
   - How would you use it?
   - Why is it beneficial to Veltix users?
   - Any implementation ideas (optional)

**Example feature request:**
```markdown
**Title:** Add automatic reconnection for Client

**Problem:**
Currently if network drops, client needs manual reconnect logic.

**Use Case:**
Building a mobile app that needs to stay connected despite spotty WiFi.

**Benefits:**
- Easier to use for beginners
- Common pattern in production apps
- Reduces boilerplate code

**Idea:**
Add ClientConfig option: `auto_reconnect=True` with configurable retry delay
```

### Code Contributions 💻

Ready to code? Here's the workflow:

1. **Fork the repository**
2. **Create a branch:** `git checkout -b feature/amazing-feature`
   - Use descriptive names: `fix/server-crash`, `feat/auto-reconnect`, `docs/quickstart`
3. **Make your changes**
4. **Write/update tests** (if adding functionality)
5. **Ensure code passes tests** (see [Development Setup](#development-setup))
6. **Commit with clear messages:** `git commit -m 'Add automatic reconnection to Client'`
   - First line: short summary (50 chars or less)
   - Optional: blank line + detailed explanation
7. **Push to your fork:** `git push origin feature/amazing-feature`
8. **Open a Pull Request** (see [Pull Request Process](#pull-request-process))

---

## Development Setup

**No dependencies needed!** Veltix uses Python stdlib only. ✨

### 1. Fork & Clone

```bash
# Fork on GitHub first, then:
git clone https://github.com/YOUR-USERNAME/veltix.git
cd veltix
```

### 2. Understand the Structure

```
veltix/
├── veltix/              # Main library code
│   ├── __init__.py      # Public API exports
│   ├── server/          # Server implementation
│   │   └── server.py    # Server, ServerConfig, ClientInfo
│   ├── client/          # Client implementation
│   │   └── client.py    # Client, ClientConfig
│   ├── network/         # Protocol implementation
│   │   ├── request.py   # Request, Response
│   │   ├── types.py     # MessageType, MessageTypeRegistry
│   │   └── sender.py    # Sender (in progress)
│   ├── utils/           # Utility functions
│   │   ├── network.py   # recv(), send() helpers
│   │   └── binding.py   # Binding enum
│   └── exceptions.py    # Custom exceptions
├── tests/               # Test files
│   └── test_basic.py    # Basic integration tests
└── examples/            # Usage examples
    ├── echo_server.py   # Simple echo server
    └── simple_chat.py   # Chat example (in progress)
```

### 3. Test Your Changes

**Run existing tests (no dependencies needed!):**
```bash
python tests/test_basic.py
```

**Try the examples:**
```bash
# Terminal 1: Start server
python examples/echo_server.py

# Terminal 2: Connect a client
python examples/simple_chat.py
```

**Test your specific changes:**
- Create a small test script in `tests/`
- Run it: `python tests/test_your_feature.py`

### 4. Optional Dev Tools

If you want to use development tools (completely optional):

```bash
# Install dev dependencies (optional)
pip install pytest black mypy

# Run tests with pytest
python -m pytest

# Format code with Black
black veltix/

# Type check with mypy
mypy veltix/
```

**Remember:** These are optional! Veltix itself has zero dependencies.

---

## Technical Areas to Contribute

Veltix has different technical areas where you can help, from beginner to advanced:

### 🌱 Beginner-Friendly

**Documentation:**
- Fix typos in README or docstrings
- Add code examples for common use cases
- Improve error messages to be more helpful
- Write tutorials or guides

**Testing:**
- Add test cases for edge cases
- Test on different Python versions
- Test on different operating systems
- Report what you find!

**Examples:**
- Create example apps (chat, file transfer, etc.)
- Add comments explaining how examples work
- Create video tutorials or blog posts

### 🔨 Intermediate

**Bug Fixes:**
- Fix reported issues
- Handle edge cases better
- Improve error handling
- Add validation

**New MessageTypes:**
- Create useful built-in message types
- Add type validation
- Improve type registry

**Protocol Improvements:**
- Optimize binary protocol
- Add protocol versioning
- Improve backwards compatibility

**Performance:**
- Profile hot paths
- Optimize critical sections
- Reduce memory usage
- Improve threading

### 🚀 Advanced

**Architecture:**
- Design new features for V2/V3
- Refactor for better extensibility
- Improve API design
- Write RFCs for major changes

**Security (V2):**
- Help implement E2E encryption
- Review security design
- Write security tests
- Audit crypto implementations

**Rust Bindings (V3):**
- Port critical paths to Rust
- Create Python bindings
- Benchmark performance
- Optimize memory layout

**Core Protocol:**
- Low-level networking improvements
- Implement async/await support
- Add UDP support
- Optimize socket operations

**Not sure where to start?** Look for the `good first issue` tag or ask in an issue!

---

## Code Style

We keep the code clean, consistent, and readable.

### Python Style Guide

**Follow PEP 8** ([Python's official style guide](https://pep8.org/))

Key points:
- **Indentation:** Use 4 spaces (not tabs)
- **Line length:** Max 88 characters (Black's default)
- **Naming:**
  - `snake_case` for functions and variables
  - `PascalCase` for classes
  - `UPPER_CASE` for constants
- **Imports:** Group stdlib, third-party, local (we only have stdlib!)

### Type Hints

Help catch bugs early by using type hints:

```python
# ✅ Good
def send_message(self, content: bytes) -> None:
    """Send a message to the server."""
    ...

def parse_response(data: bytes) -> Response:
    """Parse raw bytes into a Response object."""
    ...

# ❌ Avoid
def send_message(self, content):  # No type hints
    ...
```

### Docstrings

Document your code so others can understand it:

```python
# ✅ Good - Clear docstring
def parse_response(data: bytes) -> Response:
    """Parse raw bytes from socket into a Response object.
    
    Args:
        data: Raw bytes received from socket (must be at least 46 bytes)
        
    Returns:
        Response object with parsed message type, content, and metadata
        
    Raises:
        ValueError: If data is too short or hash verification fails
    """
    ...

# ❌ Avoid - No docstring
def parse_response(data: bytes) -> Response:
    # Parse bytes
    ...
```

### Keep It Simple

**Readable code > Clever code**

```python
# ✅ Good - Clear and simple
def is_valid_message_type(code: int) -> bool:
    """Check if message type code is in valid range."""
    return 0 <= code <= 65535

# ❌ Avoid - Too clever
def is_valid_message_type(code: int) -> bool:
    return not (code & ~0xFFFF)  # What does this do?
```

### Code Formatting

If you use Black (optional):
```bash
black veltix/
```

Otherwise, just follow PEP 8 visually. We're not strict about formatting if the code is readable.

---

## Pull Request Process

Ready to submit your code? Here's how:

### Before Submitting

**Checklist:**
- [ ] Code follows the style guide
- [ ] All tests pass: `python tests/test_basic.py`
- [ ] New features have tests
- [ ] Documentation is updated (if needed)
- [ ] Examples work correctly
- [ ] Commit messages are clear

### Creating the PR

1. **Push your branch** to your fork
2. **Open a Pull Request** on GitHub
3. **Write a clear description:**

```markdown
## Description
Brief explanation of what this PR does

## Problem
What issue does this solve? (Link to issue if exists)

## Solution
How does this PR solve it?

## Testing
How did you test this?
- [ ] Ran tests: `python tests/test_basic.py`
- [ ] Tested with examples/echo_server.py
- [ ] Tested on Python 3.11

## Breaking Changes
Does this break existing code? (Yes/No)
If yes, explain what breaks and how to migrate.

## Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] No new dependencies added
```

### After Submitting

1. **Wait for review** (usually 1-3 days for v1 development)
2. **Be open to feedback** - reviewers help make code better
3. **Make requested changes** if needed
4. **Don't take it personally** - code reviews are about code, not you
5. **Ask questions** if you don't understand feedback

### If Your PR Is Rejected

Don't be discouraged! This happens to everyone.

- **Ask for clarification** - Why was it rejected?
- **Learn from feedback** - What can you improve?
- **Try again** - Apply what you learned
- **Suggest alternatives** - Maybe there's a different approach?

**Remember:** Rejection is a learning opportunity, not a failure.

---

## Other Ways to Contribute

You don't need to write code to help Veltix grow!

### ⭐ Star the Project

Show your support by starring the repo on GitHub. It helps others discover Veltix!

### 📢 Spread the Word

- Share Veltix on social media (Twitter, Reddit, LinkedIn)
- Write a blog post or tutorial about using Veltix
- Mention it in your projects' documentation
- Present it at meetups or conferences
- Create YouTube tutorials or demos

### 📚 Documentation

- Improve README or documentation files
- Write tutorials for beginners
- Create "recipes" for common use cases
- Translate documentation (future)
- Fix typos and grammar errors

### 💬 Community Support

- Help answer questions in Issues
- Share your Veltix projects and experiences
- Provide feedback on new features
- Report bugs you encounter
- Test beta releases

**Community features coming soon:**
- Discord server (after v1.0 launch)
- Discussion forum
- Regular community calls

### 🎨 Design & Branding

- Design a logo for Veltix
- Create diagrams explaining the protocol
- Improve the website design (future)
- Create promotional graphics
- Suggest UI/UX improvements for tools

### 💰 Financial Support

**Coming after v1.0 stable:**
- GitHub Sponsors (planned)
- Help cover infrastructure costs
- Support full-time development

### 🏗️ Architecture & Vision

- Participate in roadmap discussions
- Suggest architectural improvements
- Review major design proposals
- Help plan v2 and v3 features
- Write RFCs for significant changes

### 🐛 Testing & QA

- Test new releases on different platforms
- Report edge cases and corner cases
- Create reproducible bug reports
- Test backwards compatibility
- Performance testing and benchmarking

### 🎓 Education & Outreach

- Create tutorials for beginners
- Write articles about networking concepts using Veltix
- Create example projects showcasing Veltix
- Answer questions on Stack Overflow
- Help newcomers get started

---

## Questions?

- **Found a bug?** Open an issue with `[Bug]` tag
- **Have a feature idea?** Open an issue with `[Feature Request]` tag
- **Need help?** Open an issue with `[Question]` tag
- **Want to chat?** Discord server coming after v1.0!

---

## Recognition

All contributors will be recognized in:
- README.md Contributors section
- Release notes
- Project documentation

**Every contribution matters, no matter how small!** 💚

Whether you fix a typo, report a bug, or implement a major feature - you're helping make Veltix better for everyone.

---

**Ready to contribute?** Pick an issue, fork the repo, and let's build something amazing together! 🚀

**Project Status:** 🟡 Active development (v1.0.0)  
**License:** MIT  
**Maintainer Response Time:** Usually 1-3 days during v1 development
