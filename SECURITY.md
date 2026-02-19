# 🛡️ Security Policy

Thank you for helping make Veltix secure ❤️  
Security is a top priority, especially for a networking library.

---

## 📦 Supported Versions

We currently provide security updates for the following versions:

| Version | Supported |
|----------|------------|
| 1.2.x    | ✅ Yes |
| 1.1.x    | ❌ No |
| < 1.1    | ❌ No |

Only the latest minor version of the current stable release is supported.

---

## 🔍 Reporting a Vulnerability

⚠️ **Please DO NOT open a public GitHub issue for security vulnerabilities.**

Instead, report vulnerabilities privately:

- 📧 Email: **security@your-domain.com** *(replace with your real email)*  
- Or contact the maintainer directly on GitHub: https://github.com/NytroxDev

If possible, include:

- A clear description of the vulnerability
- Steps to reproduce
- Proof-of-concept code (if applicable)
- Impact assessment
- Affected versions

---

## ⏱️ Response Timeline

We aim to:

- Acknowledge the report within **72 hours**
- Provide an initial assessment within **7 days**
- Release a patch as soon as reasonably possible

Complex issues may require more time.

---

## 🔐 Security Philosophy

Veltix is designed with:

- Built-in message integrity verification (SHA256)
- Strict data validation
- Safe multi-threaded handling
- Timeout protection for request/response
- Progressive security roadmap

Future improvements include:

- v1.3.0: Handshake & authentication system
- v2.0.0: End-to-end encryption (ChaCha20 + X25519 + Ed25519)
- Perfect forward secrecy

---

## 🏆 Responsible Disclosure

We strongly encourage responsible disclosure.

Please allow time for a fix before publicly disclosing vulnerabilities.

Contributors who responsibly disclose valid security issues may be credited (unless they prefer to remain anonymous).

---

## 🚫 What is NOT a Security Issue

The following are not considered security vulnerabilities:

- Theoretical issues without proof-of-concept
- Denial of Service caused by unrealistic misuse
- Issues in unsupported versions
- Missing features from planned roadmap items

---

## 🙏 Thank You

Veltix is built with security in mind, but no software is perfect.  
Your help makes it stronger.

— Nytrox
