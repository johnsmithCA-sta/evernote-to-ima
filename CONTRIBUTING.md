# Contributing to evernote-to-ima

Thanks for your interest in contributing! This project helps users migrate their Evernote/印象笔记 data into ima (or any Markdown-based knowledge base). We welcome bug reports, feature ideas, documentation improvements, and code contributions.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Skill Development Notes](#skill-development-notes)
- [Testing](#testing)
- [Code Style](#code-style)
- [Commit Guidelines](#commit-guidelines)
- [License](#license)

## Code of Conduct

Be respectful and constructive. Harassment, discrimination, and offensive behavior are not tolerated. This project is open to contributors of all backgrounds and experience levels.

## How to Contribute

### 1. Report a Bug

Open an issue with the following information:

- A clear, descriptive title
- Steps to reproduce the problem
- Expected vs. actual behavior
- Your environment: OS version, Python version, Evernote client version
- Any error logs or stack traces (trim sensitive data first)

### 2. Propose a Feature

Open an issue describing:

- The problem you are trying to solve
- The proposed behavior
- Why this is useful to the broader community

### 3. Submit a Pull Request

1. Fork the repository.
2. Create a feature branch: `git checkout -b feat/your-feature`.
3. Make your changes with clear commit messages.
4. Run the test suite (see [Testing](#testing)).
5. Push your branch and open a Pull Request against `main`.
6. In the PR description, explain what changed and why. Reference related issues if any.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/<owner>/evernote-to-ima.git
cd evernote-to-ima

# Requirements
# - Python 3.6+ (scripts use only the standard library)
# - Optional: evernote-backup (step 1 data export)
# - Optional: cos-python-sdk-v5 (step 5 COS upload)
```

The project uses **zero third-party Python dependencies** for the core scripts. If you need to add a dependency, discuss it first in an issue — the zero-dependency design is intentional.

## Skill Development Notes

This repository is distributed as an **Agent Skill** following the open [Agent Skills specification](https://agentskills.io).

When modifying the skill:

- **`SKILL.md`** is the contract. Keep the frontmatter (`name`, `description`, `version`, `license`, `tags`) accurate and up to date.
- The `description` must clearly state input, output, and boundaries — it is what agents and users read to decide whether to install.
- Keep instructions executable: every command in `SKILL.md` should be directly runnable.
- Bump `version` when behavior changes (semantic versioning).

## Testing

Run the conversion pipeline against the bundled test fixtures:

```bash
# 1. Convert a sample ENEX directory
python3 scripts/convert_all.py ./test/fixtures ./test/out

# 2. Slim the output (removes ads / invalid images)
python3 scripts/slim_notes.py ./test/out --dry-run

# 3. Merge by sub-notebook (dry run)
python3 scripts/merge_notes.py ./test/out ./test/merged

# 4. Verify a candidate password offline (HMAC-based, no network)
python3 scripts/verify_password.py ./test/fixtures/sample.enex --password "test"
```

Add fixtures under `test/fixtures/` when you introduce new behaviors. All scripts print clear success/failure stats and must never silently drop note content.

## Code Style

- Python 3.6+ compatible, standard library only.
- 4-space indentation, ~100 char lines.
- Functions keep a short docstring; non-obvious logic gets inline comments.
- CLI scripts use `argparse` with clear `usage` strings.
- No secrets, personal paths, or account identifiers in committed files — sanitize any test data.

## Commit Guidelines

- Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- One logical change per commit.
- Keep the subject under 72 characters.

Example:

```text
fix(convert): strip XML declaration and DOCTYPE before parsing ENML

ElementTree cannot parse content that references an external DTD, which
caused the fallback branch to retain HTML indentation noise. Strip the
XML declaration and DOCTYPE before parsing.
```

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
