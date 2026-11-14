"""Data for the home page: latest blog posts, docs categories and GitHub projects.

The home page template (overrides/home.html) reads these context variables:

- latest_posts: newest blog posts with title, date, URL and cover image
- docs_categories: top-level sections of the "Docs" navigation entry
- projects: GitHub repositories listed under `extra.projects` in mkdocs.yml
"""

from __future__ import annotations

import json
import logging
import os
import posixpath
import re
import time
import urllib.request
from pathlib import Path

from mkdocs.exceptions import PluginError
from mkdocs.structure.nav import Section
from mkdocs.utils import get_relative_url

log = logging.getLogger("mkdocs.hooks.home")

LATEST_POSTS = 3
DOCS_SECTION = "Docs"
CATEGORY_ICONS = {
    "Android": "material/android",
    "Hardware": "material/chip",
    "Media": "material/filmstrip",
    "Networking": "material/lan",
    "Tools and scripts": "material/tools",
}
DEFAULT_CATEGORY_ICON = "material/folder-outline"

CACHE_FILE = Path(".cache/home/github-projects.json")
CACHE_MAX_AGE = 3600
GITHUB_API = "https://api.github.com/repos/"

LANGUAGE_COLORS = {
    "C": "#555555",
    "C++": "#f34b7d",
    "CSS": "#563d7c",
    "Go": "#00add8",
    "HTML": "#e34c26",
    "Java": "#b07219",
    "JavaScript": "#f1e05a",
    "Kotlin": "#a97bff",
    "Python": "#3572a5",
    "Rust": "#dea584",
    "Shell": "#89e051",
    "TypeScript": "#3178c6",
}
DEFAULT_LANGUAGE_COLOR = "#8b949e"

IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)")

_files = None


def on_files(files, config):
    global _files
    _files = files
    return files


def on_page_context(context, page, config, nav):
    if not page.is_homepage:
        return context
    context["latest_posts"] = _latest_posts(page, config)
    context["docs_categories"] = _docs_categories(page, nav)
    context["projects"] = _projects(config.extra.get("projects", []))
    return context


# Latest posts ----------------------------------------------------------------


def _latest_posts(page, config):
    blog = config.plugins["material/blog"].blog
    return [
        {
            "title": post.title,
            "url": get_relative_url(post.url, page.url),
            "date": post.config.date.created,
            "draft": bool(post.config.draft),
            "image": _cover_image(post, page),
        }
        for post in blog.posts[:LATEST_POSTS]
    ]


def _cover_image(post, page):
    """Return the URL of the first image in the post, relative to the home page."""
    match = IMAGE_PATTERN.search(post.markdown)
    if not match:
        return None
    src = match.group(1)
    if "://" in src:
        return src
    path = posixpath.normpath(posixpath.join(posixpath.dirname(post.file.src_uri), src))
    file = _files.get_file_from_path(path)
    if file is None:
        return None
    return get_relative_url(file.url, page.url)


# Docs categories -------------------------------------------------------------


def _docs_categories(page, nav):
    docs = next(
        (item for item in nav.items if isinstance(item, Section) and item.title == DOCS_SECTION),
        None,
    )
    if docs is None:
        raise PluginError(f'home hook: navigation section "{DOCS_SECTION}" not found')
    categories = []
    for item in docs.children:
        if not isinstance(item, Section):
            continue
        first = _first_page(item)
        if first is None:
            continue
        categories.append(
            {
                "title": item.title,
                "url": get_relative_url(first.url, page.url),
                "icon": CATEGORY_ICONS.get(item.title, DEFAULT_CATEGORY_ICON),
            }
        )
    return categories


def _first_page(section):
    for item in section.children:
        if isinstance(item, Section):
            page = _first_page(item)
            if page is not None:
                return page
        elif item.is_page:
            return item
    return None


# GitHub projects -------------------------------------------------------------


def _projects(names):
    if not names:
        return []
    cached = _read_cache()
    if cached is not None and [repo["full_name"] for repo in cached] == names:
        return cached
    projects = [_fetch_repo(name) for name in names]
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(projects), encoding="utf-8")
    log.info("home hook: GitHub projects fetched: %d", len(projects))
    return projects


def _read_cache():
    if not CACHE_FILE.exists():
        return None
    if time.time() - CACHE_FILE.stat().st_mtime > CACHE_MAX_AGE:
        return None
    return json.loads(CACHE_FILE.read_text(encoding="utf-8"))


def _fetch_repo(name):
    request = urllib.request.Request(GITHUB_API + name)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", "xitee-docs-build")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.load(response)
    except OSError as error:
        raise PluginError(f"home hook: GitHub repository {name} not fetched: {error}") from error
    language = data.get("language")
    return {
        # Keep the configured spelling, so the cache comparison stays stable
        "full_name": name,
        "name": data["name"],
        "url": data["html_url"],
        "description": data.get("description") or "",
        "language": language,
        "language_color": LANGUAGE_COLORS.get(language, DEFAULT_LANGUAGE_COLOR),
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "owner": data["owner"]["login"],
    }
