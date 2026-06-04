# AGENTS.md

This file defines repository-level interaction rules for assistant sessions in this repository.

## Shared Rules

### Scope

These rules define the shared baseline for assistant sessions across REPACSS stack projects and paper projects.

Each repository must keep its own runtime-visible `AGENTS.md`.
This file is the canonical runtime source for this repository.

### Conversation Language Rule

1. If the user writes in Chinese, assistant replies may be in Chinese.
2. If the user writes in English, assistant replies should be in English.
3. Chinese is allowed for interactive planning and discussion in chat when that helps the user review intermediate work.

### Generated Content Language Rule (Strict)

All assistant-generated project content must be in English unless the user explicitly requests non-English file content.

This includes:

1. Source code comments and docstrings
2. Markdown documents such as `README`, `docs/*`, reports, notes, and analysis drafts
3. Config descriptions, inline help text, and usage examples
4. Commit messages created by the assistant
5. CLI or log text templates written to files
6. Any other content written into the repository or project workspace for later sharing or reuse

### Repo Material Language Rule

Anything persisted into the project workspace should default to English if it may be read, shared, reused, reviewed, or versioned later.

Do not write Chinese into repository or project files unless the user explicitly asks for that exact Chinese output.

### Correction Rule

If any generated project file content is accidentally non-English:

1. Rewrite it to English immediately in the same session.
2. Prefer updating the existing file rather than creating a duplicate.

## Repo-Specific Rules

### Project Structure Note

1. `README.md` is for project architecture and usage.
2. `AGENTS.md` is for assistant interaction and generation rules.
