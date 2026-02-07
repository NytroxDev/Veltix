# Contributing to Veltix

Thank you for considering contributing to Veltix! 🎉

We welcome contributions from everyone, whether you're fixing bugs, adding features, improving documentation, or
translating.

## Code of Conduct

Be respectful, inclusive, and constructive. We're here to build something great together.

## How to Contribute

### Reporting Bugs 🐛

Before creating a bug report, please check if the issue already exists.

**When reporting bugs, include:**

- Python version and OS
- Clear reproduction steps
- Expected vs actual behavior
- Error messages (if any)

### Suggesting Features 💡

We love new ideas! Before suggesting:

- Check if it's already planned in our [Roadmap](README.md#roadmap)
- Explain the use case and benefits
- Consider if it fits Veltix's philosophy (simple, zero-deps)

Open an issue with `[Feature Request]` in the title.

### Code Contributions 💻

#### Development Setup

**No dependencies needed!** Veltix uses Python stdlib only.

```bash
# Clone the repo
git clone https://github.com/NytroxDev/Veltix.git
cd Veltix

# That's it! Ready to code.
```

**Optional dev tools:**

```bash
pip install pytest  # For running tests
```

#### Making Changes

1. **Fork** the repository
2. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Make your changes**
    - Write clear, readable code
    - Add/update tests if needed
    - Follow existing code style
4. **Test your changes**
   ```bash
   python -m pytest tests/
   ```
5. **Commit** with a clear message:
   ```bash
   git commit -m "Add amazing feature that does X"
   ```
6. **Push** to your fork:
   ```bash
   git push origin feature/amazing-feature
   ```
7. **Open a Pull Request** on GitHub

#### Code Style

- Follow **PEP 8**
- Use **type hints** everywhere
- Add **docstrings** to public methods (Google style)
- Keep it **simple and readable**
- Avoid adding dependencies

**Example:**

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
    # Implementation
```

## Other Ways to Contribute

You don't need to write code to help Veltix grow!

### ⭐ Star the Project

Show your support by starring the repo on GitHub.

### 📢 Spread the Word

- Share Veltix on social media
- Write blog posts or tutorials
- Mention it in your projects
- Tell other developers

### 📚 Documentation

- Improve README or docs
- Write tutorials or guides
- Translate documentation
- Fix typos

### 💬 Community Support

- Help answer questions in Issues
- Join our Discord (coming soon)
- Share your Veltix projects
- Help newcomers get started

### 🎨 Design & Branding

- Improve the website (coming soon)
- Create graphics or logos
- Suggest UI/UX improvements

### 💰 Financial Support

- Sponsor the project (GitHub Sponsors - coming soon)
- Help cover infrastructure costs

### 🏗️ Architecture & Vision

- Participate in roadmap discussions
- Suggest architectural improvements
- Review major pull requests

### 🐛 Testing & QA

- Test new releases
- Report edge cases
- Create reproducible bug reports
- Benchmark performance

## Pull Request Process

1. **Update documentation** if needed
2. **Add tests** for new features
3. **Ensure all tests pass**
4. **Keep PRs focused** - one feature per PR
5. **Write clear descriptions** of what changed and why

### PR Checklist

- [ ] Code follows project style
- [ ] Added/updated docstrings
- [ ] Added/updated tests
- [ ] All tests pass
- [ ] Updated README if needed
- [ ] No new dependencies added

## Questions?

- Open an issue with `[Question]` tag
- Join our Discord :https://discord.gg/NrEjSHtfMp
- Email: nytrox.dev@gmail.com

## Recognition

All contributors will be recognized in our [README](README.md#contributors)!

Thank you for making Veltix better! 💚

---

**Every contribution matters, no matter how small!**