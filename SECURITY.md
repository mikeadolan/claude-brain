# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in claude-brain, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, use GitHub's **Private Vulnerability Reporting**:

1. Go to the [Security tab](../../security) of this repository
2. Click **"Report a vulnerability"**
3. Fill in the description, steps to reproduce, potential impact, and suggested fix (if you have one)

This creates a private security advisory visible only to you and the maintainers. You will receive a response within 48 hours. Once confirmed, a fix will be prioritized and released as soon as possible.

## Scope

claude-brain runs entirely on your local machine. There are no cloud services, no API keys stored, and no data leaves your system. The primary security concerns are:

- **Local database access:** The SQLite database contains your full conversation history. Protect the database file with appropriate file permissions.
- **MCP server:** Runs locally over stdio. No network exposure by default.
- **Hooks:** Execute Python scripts automatically during Claude Code sessions. Review hook code before installing.

## Supported Versions

Only the latest version on the `main` branch is supported with security updates.
