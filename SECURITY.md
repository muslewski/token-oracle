# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| latest 0.x on PyPI / npm shim / main | Yes |
| older | No — please upgrade first |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report privately via
[GitHub's private security advisory](https://github.com/muslewski/token-oracle/security/advisories/new)
or email **10kento10@gmail.com** with the subject line `[SECURITY] token-oracle`.

Include:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fix (optional)

You will receive a response within **72 hours**. We aim to ship a patch within
**14 days** of a confirmed vulnerability.

## Scope

token-oracle is a local Python CLI that reads Claude/Grok log files and optionally uses a browser for live verification. Primary risk: path traversal via configured log paths, credential leakage in config, or unsafe subprocess args.

Out of scope: issues in Node.js / Python / the OS, third-party CLIs this tool
launches, or GitHub Actions runners themselves.
