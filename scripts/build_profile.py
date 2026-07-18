#!/usr/bin/env python3
"""Build the light and dark SVG cards used by the profile README."""

from __future__ import annotations

import base64
from collections import Counter
from datetime import datetime
from html import escape
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
USERNAME = os.getenv("PROFILE_USERNAME", "saisharan0103")
DISPLAY_NAME = os.getenv("PROFILE_DISPLAY_NAME", "Sai Sharan")
TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
API = "https://api.github.com"


THEMES = {
    "dark": {
        "page": "#0d1117",
        "panel": "#161b22",
        "topbar": "#21262d",
        "border": "#30363d",
        "text": "#e6edf3",
        "muted": "#8b949e",
        "accent": "#58a6ff",
        "green": "#3fb950",
        "yellow": "#d29922",
        "shadow": "#010409",
    },
    "light": {
        "page": "#f6f8fa",
        "panel": "#ffffff",
        "topbar": "#f6f8fa",
        "border": "#d0d7de",
        "text": "#1f2328",
        "muted": "#656d76",
        "accent": "#0969da",
        "green": "#1a7f37",
        "yellow": "#9a6700",
        "shadow": "#8c959f",
    },
}


def api_json(path: str, *, payload: dict[str, Any] | None = None) -> Any:
    """Read JSON from GitHub's REST or GraphQL API."""
    url = path if path.startswith("https://") else f"{API}{path}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = Request(url, data=body, headers=headers, method="POST" if body else "GET")
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API request failed ({error.code}): {detail}") from error


def public_repositories() -> list[dict[str, Any]]:
    """Return every public repository visible on the user's profile."""
    repositories: list[dict[str, Any]] = []
    page = 1
    while True:
        query = urlencode(
            {
                "per_page": 100,
                "page": page,
                "type": "owner",
                "sort": "updated",
            }
        )
        batch = api_json(f"/users/{USERNAME}/repos?{query}")
        repositories.extend(batch)
        if len(batch) < 100:
            return repositories
        page += 1


def contribution_stats() -> dict[str, int] | None:
    """Return contribution totals for the rolling one-year GitHub window."""
    if not TOKEN:
        return None
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar { totalContributions }
          totalCommitContributions
          totalPullRequestContributions
        }
      }
    }
    """
    response = api_json(
        "/graphql",
        payload={"query": query, "variables": {"login": USERNAME}},
    )
    if response.get("errors"):
        raise RuntimeError(f"GitHub GraphQL request failed: {response['errors']}")
    return response["data"]["user"]["contributionsCollection"]


def profile_stats() -> dict[str, Any]:
    user = api_json(f"/users/{USERNAME}")
    repositories = public_repositories()
    originals = [
        repo
        for repo in repositories
        if not repo.get("fork") and repo.get("name", "").lower() != USERNAME.lower()
    ]
    languages = Counter(
        repo["language"]
        for repo in originals
        if repo.get("language") and repo["language"] != "Dockerfile"
    )
    contributions = contribution_stats()
    return {
        "name": DISPLAY_NAME,
        "public_repos": user.get("public_repos", len(repositories)),
        "followers": user.get("followers", 0),
        "since": datetime.fromisoformat(user["created_at"].replace("Z", "+00:00")).strftime("%b %Y"),
        "projects": len(originals),
        "stars": sum(repo.get("stargazers_count", 0) for repo in originals),
        "languages": [name for name, _ in languages.most_common(4)],
        "contributions": (
            contributions["contributionCalendar"]["totalContributions"]
            if contributions
            else None
        ),
        "commits": contributions["totalCommitContributions"] if contributions else None,
        "pull_requests": contributions["totalPullRequestContributions"] if contributions else None,
    }


def svg_text(
    x: int,
    y: int,
    value: str,
    color: str,
    *,
    size: int = 16,
    weight: int = 400,
    anchor: str = "start",
    family: str = "mono",
) -> str:
    fonts = {
        "mono": "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
        "sans": "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif",
    }
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}" '
        f'font-family="{fonts[family]}">{escape(value)}</text>'
    )


def build_svg(theme_name: str, stats: dict[str, Any], portrait: str) -> str:
    theme = THEMES[theme_name]
    display_name = stats["name"]
    languages = " · ".join(stats["languages"]) or "Building in public"
    social_proof = (
        f'{stats["stars"]:,} stars'
        if stats["stars"]
        else f'{stats["followers"]:,} followers'
    )
    if stats["contributions"] is None:
        activity = "Contribution activity refreshes in GitHub Actions"
    else:
        activity = (
            f'{stats["contributions"]:,} contributions  ·  '
            f'{stats["commits"]:,} commits  ·  {stats["pull_requests"]:,} PRs'
        )

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="560" '
        'viewBox="0 0 1100 560" role="img" aria-labelledby="title description">',
        f'<title id="title">{escape(display_name)} — AI Engineer and Systems Builder</title>',
        '<desc id="description">A terminal-inspired GitHub profile card with a portrait, '
        'technical focus, stack, and live GitHub statistics.</desc>',
        "<defs>",
        '<clipPath id="portrait-clip"><circle cx="180" cy="228" r="126"/></clipPath>',
        f'<filter id="shadow" x="-15%" y="-15%" width="130%" height="140%">'
        f'<feDropShadow dx="0" dy="10" stdDeviation="16" flood-color="{theme["shadow"]}" '
        'flood-opacity="0.22"/></filter>',
        "</defs>",
        f'<rect width="1100" height="560" rx="24" fill="{theme["page"]}"/>',
        f'<rect x="14" y="14" width="1072" height="532" rx="18" fill="{theme["panel"]}" '
        f'stroke="{theme["border"]}" filter="url(#shadow)"/>',
        f'<path d="M32 14h1036a18 18 0 0 1 18 18v36H14V32a18 18 0 0 1 18-18Z" '
        f'fill="{theme["topbar"]}"/>',
        f'<line x1="14" y1="68" x2="1086" y2="68" stroke="{theme["border"]}"/>',
        '<circle cx="43" cy="41" r="7" fill="#ff5f57"/>',
        '<circle cx="67" cy="41" r="7" fill="#febc2e"/>',
        '<circle cx="91" cy="41" r="7" fill="#28c840"/>',
        svg_text(126, 47, f"{USERNAME}@github: ~", theme["muted"], size=15),
        f'<line x1="360" y1="88" x2="360" y2="522" stroke="{theme["border"]}"/>',
        f'<image href="{portrait}" x="54" y="102" width="252" height="252" '
        'preserveAspectRatio="xMidYMid slice" clip-path="url(#portrait-clip)"/>',
        f'<circle cx="180" cy="228" r="128" fill="none" stroke="{theme["accent"]}" stroke-width="4"/>',
        f'<circle cx="274" cy="319" r="16" fill="{theme["panel"]}"/>',
        f'<circle cx="274" cy="319" r="11" fill="{theme["green"]}"/>',
        svg_text(180, 400, display_name, theme["text"], size=28, weight=700, anchor="middle", family="sans"),
        svg_text(180, 429, "AI Engineer · Systems Builder", theme["muted"], size=15, anchor="middle", family="sans"),
        f'<rect x="65" y="460" width="230" height="38" rx="19" fill="{theme["topbar"]}" '
        f'stroke="{theme["border"]}"/>',
        svg_text(180, 485, f"github.com/{USERNAME}", theme["accent"], size=14, anchor="middle"),
        svg_text(395, 108, "> whoami", theme["green"], size=16, weight=700),
        svg_text(395, 145, "I build agent-driven systems that turn messy", theme["text"], size=20, weight=650, family="sans"),
        svg_text(395, 174, "workflows into useful, reviewable outcomes.", theme["text"], size=20, weight=650, family="sans"),
        svg_text(395, 222, "FOCUS", theme["accent"], size=14, weight=700),
        svg_text(395, 251, "Agentic systems · tool calling · orchestration", theme["text"], size=16),
        svg_text(395, 278, "RAG · workflow automation · AI product prototypes", theme["text"], size=16),
        svg_text(395, 326, "WORKING SET", theme["accent"], size=14, weight=700),
        svg_text(395, 355, "Python · TypeScript · FastAPI · Next.js", theme["text"], size=16),
        svg_text(395, 382, "OpenAI · Gemini · Playwright · Supabase · GCP", theme["text"], size=16),
        svg_text(395, 430, "GITHUB", theme["accent"], size=14, weight=700),
        svg_text(
            395,
            459,
            f'{stats["public_repos"]:,} public repos  ·  {stats["projects"]:,} original projects  ·  {social_proof}',
            theme["text"],
            size=16,
        ),
        svg_text(395, 486, activity, theme["text"], size=16),
        svg_text(395, 513, f"Top languages: {languages}  ·  here since {stats['since']}", theme["muted"], size=15),
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def main() -> None:
    portrait_path = ASSETS / "profile.jpg"
    portrait = "data:image/jpeg;base64," + base64.b64encode(portrait_path.read_bytes()).decode("ascii")
    stats = profile_stats()
    for theme_name in THEMES:
        output = ASSETS / f"profile-{theme_name}.svg"
        output.write_text(build_svg(theme_name, stats, portrait), encoding="utf-8")
        print(f"wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
