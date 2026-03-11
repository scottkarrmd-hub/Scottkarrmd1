# CLAUDE.md

This file provides guidance for AI assistants (Claude Code and similar tools) working in this repository.

## Project Overview

**Scottkarrmd1** is a utility program to extract copies of saved emails and links from Gmail account labels and store them in Google Drive.

- **Owner:** scottkarrmd-hub
- **License:** MIT
- **Status:** Early stage — no application code exists yet. Only README.md and LICENSE are present.

## Repository Structure

```
Scottkarrmd1/
├── README.md       # Project description
├── LICENSE         # MIT license
└── CLAUDE.md       # This file
```

## Intended Functionality

Based on the README, this project will:

1. Authenticate with a Gmail account (likely via OAuth2 / Google API)
2. Read emails and links from specified Gmail labels
3. Extract relevant content (email bodies, URLs, attachments)
4. Save or sync that content to a Google Drive folder

## Development Guidelines

### Language & Stack

No language has been chosen yet. When code is added, update this section. Likely candidates for this type of project:

- **Python** — strong Google API client libraries (`google-api-python-client`, `google-auth`)
- **Node.js** — `googleapis` npm package

### Google API Conventions

When implementing, follow these patterns:

- Use OAuth2 for authentication; never hardcode credentials
- Store credentials in environment variables or a `.env` file (never commit secrets)
- Add `.env`, `credentials.json`, and `token.json` to `.gitignore`
- Use the Gmail API v1 and Drive API v3
- Request only the OAuth scopes required:
  - `https://www.googleapis.com/auth/gmail.readonly` — read-only Gmail access
  - `https://www.googleapis.com/auth/drive.file` — write access to Drive files created by this app

### File & Code Conventions

- Keep secrets out of version control — use `.env` or OS keyring
- Document any required environment variables in README.md
- Write clear error messages when API calls fail (quota exceeded, auth errors, etc.)
- Prefer idempotent operations: re-running the program should not create duplicate files in Drive

### Git Workflow

- Default branch: `master`
- Feature branches: use descriptive names (`feature/gmail-auth`, `fix/drive-upload`)
- Commit messages: imperative mood, concise (`Add Gmail label filtering`, `Fix OAuth token refresh`)
- Do not commit `node_modules/`, `__pycache__/`, `.env`, or credential files

## AI Assistant Notes

- This repository currently has **no application code**. When asked to implement features, start with authentication setup and a minimal working script.
- Check for a `.gitignore` before creating credential files and add sensitive file patterns if missing.
- If adding dependencies, create the appropriate package manifest (`requirements.txt` / `package.json`) and document setup steps in README.md.
- Do not push secrets, API keys, or OAuth tokens to any branch.
