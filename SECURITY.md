# Security Policy

## Bring-Your-Own-Key (BYOK) Hygiene
StoryReel Studio runs locally on your machine using your own API credentials:
- **Never commit** `.env`, `client_secret.json`, or `token.json` to version control.
- API keys are read strictly from environment variables or `.env` and are **never** embedded into generated HTML, JSON, or logs.
- Use `--dry-run` before building a large story to preview the exact number of AI API calls before incurring charges.

## Local Studio Server Boundary
- `storyreel serve` binds strictly to `127.0.0.1` (localhost) by default.
- Static files are served exclusively from `output/` — repository source files, `.env`, and OAuth credentials are never served over HTTP.
- Do **not** expose the local Studio server directly to the public internet without adding authentication.

## Reporting a Vulnerability
If you discover a security issue (such as credential leakage, path traversal, or XSS in generated templates), please open a private security advisory on GitHub or contact the repository maintainers before disclosing it publicly.
