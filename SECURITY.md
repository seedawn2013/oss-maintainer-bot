# Security Policy

## Supported Versions

| Version | Supported |
|---------|----------|
| 0.1.x | ✅ Active |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability in OSS Maintainer Bot, please report it through one of the following channels:

1. **GitHub Security Advisory** (preferred): [Open a private advisory](https://github.com/seedawn2013/oss-maintainer-bot/security/advisories/new)
2. **Email**: If GitHub Security Advisories are not available, please email the maintainer directly.

### What to Include

Please include the following information in your report:
- Type of vulnerability (e.g., injection, token leakage, privilege escalation)
- The affected component(s) and version(s)
- Steps to reproduce or proof-of-concept code
- Potential impact assessment

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 5 business days
- **Fix timeline**: Depends on severity; critical issues within 7 days

## Security Best Practices for Users

1. **Never log your `OPENAI_API_KEY`** — always use `${{ secrets.OPENAI_API_KEY }}`
2. **Use the `GITHUB_TOKEN` with minimum required permissions** — only grant `issues: write` and `pull-requests: write` when needed
3. **Pin to a specific version tag** (e.g., `@v0.1.0`) rather than `@main` for production workflows
4. **Review bot comments** before relying on them for important decisions
5. **Use `dry-run: true`** when first testing in a new repository
