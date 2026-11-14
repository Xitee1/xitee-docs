"""Data for the home page: latest blog posts, docs categories and GitHub projects.

The home page template (overrides/home.html) reads these context variables:

- latest_posts: newest blog posts with title, date, URL and cover image
- docs_categories: top-level sections of the "Docs" navigation entry
- projects: GitHub repositories listed under `extra.projects` in mkdocs.yml;
  their live data is loaded in the browser by javascripts/projects.js

The Jinja filter `cover_image` returns the cover image of a blog post as site URL.
The cover is the `cover` metadata entry of the post, otherwise its first image.
"""

from __future__ import annotations

import posixpath
import re

from mkdocs.exceptions import PluginError
from mkdocs.structure.nav import Section
from mkdocs.utils import get_relative_url

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

IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)")

_files = None


def on_files(files, config):
    global _files
    _files = files
    return files


def on_env(env, config, files):
    env.filters["cover_image"] = _cover_image
    return env


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
            "image": _relative_url(_cover_image(post), page),
        }
        for post in blog.posts[:LATEST_POSTS]
    ]


def _cover_image(post):
    """Return the cover image of a blog post as site URL, or None without image.

    Paths in the `cover` metadata entry are relative to the post file, like image links.
    """
    post = getattr(post, "post", post)  # excerpts in blog views wrap their post
    src = post.meta.get("cover")
    if not src:
        match = IMAGE_PATTERN.search(post.markdown)
        if not match:
            return None
        src = match.group(1)
    if "://" in src:
        return src
    path = posixpath.normpath(posixpath.join(posixpath.dirname(post.file.src_uri), src))
    file = _files.get_file_from_path(path)
    if file is None:
        if post.meta.get("cover"):
            raise PluginError(f'home hook: cover image "{src}" of "{post.file.src_uri}" not found')
        return None
    return file.url


def _relative_url(url, page):
    if url is None or "://" in url:
        return url
    return get_relative_url(url, page.url)


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
    """Return the configured repositories. Description, language, stars and forks
    are loaded live in the browser by javascripts/projects.js."""
    projects = []
    for name in names:
        owner, repo = name.split("/", 1)
        projects.append(
            {
                "full_name": name,
                "owner": owner,
                "name": repo,
                "url": f"https://github.com/{name}",
            }
        )
    return projects
