# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MkDocs Material documentation and blog site ("Xitee's Docs") served at https://docs.xitma.de. This is a Python-based project — there is no Node.js/npm involved.

## Development Commands

```bash
# Setup (one-time)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Development server (http://127.0.0.1:8000)
mkdocs serve

# Build static site to site/
mkdocs build

# Deploy to GitHub Pages
mkdocs gh-deploy --force
```

There are no tests or linters configured for this project.

## Architecture

- **mkdocs.yml** — Central configuration: theme settings, plugins, markdown extensions
- **docs/** — All content (markdown pages, blog posts, images, navigation)
- **overrides/** — MkDocs Material theme partial overrides (currently only `partials/comments.html` for Giscus comments integration)
- **requirements.txt** — Python dependencies (mkdocs-material and plugins)
- **Dockerfile** — Multi-stage build: Python builder + nginx for production serving

### Content Organization

- `docs/docs/` — Documentation articles organized by category (android, hardware, media, networking, etc.)
- `docs/blog/posts/` — Blog posts with YAML frontmatter (date created/updated, draft support)
- `docs/.nav.yml` — Top-level navigation order (used by awesome-nav plugin)
- `.meta.yml` files in directories set shared metadata (e.g., enabling comments)

### Key Plugins

- **awesome-nav** — Navigation derived from folder structure + `.nav.yml` files
- **git-revision-date-localized** — "Last updated" timestamps from git history; requires full git history (`fetch-depth: 0` in CI)
- **blog** — Built-in MkDocs Material blog plugin
- **glightbox** — Image lightbox viewer

### Deployment

Two parallel deployment paths (both triggered on push to main):
1. **GitHub Pages** — `ci.yaml` workflow runs `mkdocs gh-deploy`
2. **Docker image** — `docker.yaml` workflow builds multi-platform (amd64/arm64) image, pushes to `ghcr.io`

### Writing Content

Blog posts go in `docs/blog/posts/<slug>/` with frontmatter:
```yaml
---
date:
  created: 2024-01-01
  updated: 2024-06-15
draft: false
---
```

Available markdown extensions: admonitions, tabbed code blocks (`pymdownx.tabbed`), syntax highlighting with line numbers, collapsible details blocks, emoji (Twemoji), and image attributes.
