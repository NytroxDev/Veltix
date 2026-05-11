# Security Policy

Thank you for helping improve the security of Veltix.

## Supported Versions

Only the latest stable version of Veltix is currently supported with security updates.

Older versions may contain known or unknown vulnerabilities and should not be used in production environments.

---

## Reporting a Vulnerability

Please do NOT report security vulnerabilities through public GitHub issues.

Instead, report them privately:

- Email: nytrox.dev@gmail.com
- GitHub: https://github.com/NytroxDev

Please include, if possible:

- A description of the issue
- Steps to reproduce
- Affected versions
- Potential impact
- Proof-of-concept code (if available)

---

## Security Notes

Veltix is an actively developed networking library.

Current versions include:

- Packet validation
- Connection handshake support
- Timeout protections
- Structured packet framing

Veltix does NOT currently provide:

- End-to-end encryption
- Built-in TLS
- Guaranteed authentication security

Applications requiring strong transport security should use TLS or another secure external layer.

---

## Responsible Disclosure

Please allow reasonable time for investigation and fixes before publicly disclosing vulnerabilities.

Thank you for helping make Veltix safer.
