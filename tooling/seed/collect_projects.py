"""refresh the ROPS social innovation snapshot from the library pages of rops.krakow.pl."""

from __future__ import annotations

import argparse
from datetime import date
import html
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from import_projects import validate_projects


SITE = "https://rops.krakow.pl"
LIBRARY = "/innowacje-spoleczne/biblioteka-innowacji-spolecznych"
# the site refuses a bare agent string, so the collector names itself the way a browser does
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) ehackyeah2026-seed/1.0"
PAUSE = 0.5
# the numbered sections of an innovation page and the column each one fills
SECTIONS = (
    ("na czym polega", "description"),
    ("jakich problem", "problem"),
    ("grupa docelowa", "target_group"),
    ("kto może skorzystać", "beneficiaries"),
    ("czy to działa", "effectiveness"),
    ("autorzy", "authors"),
)


def fetch(path: str) -> str:
    request = Request(SITE + path, headers={"User-Agent": USER_AGENT, "Accept-Language": "pl"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def text_of(fragment: str) -> str | None:
    """the fragment's text, one line per paragraph or list item, or None when empty."""
    fragment = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", fragment, flags=re.S)
    fragment = re.sub(r"<li[^>]*>", "\n- ", fragment)
    fragment = re.sub(r"<(br|/p|/li|/div|/tr|/h[1-6]|/ul|/ol|/table)[^>]*>", "\n", fragment)
    fragment = html.unescape(re.sub(r"<[^>]+>", "", fragment)).replace("\xa0", " ")
    lines = [" ".join(line.split()) for line in fragment.splitlines()]
    return "\n".join(line for line in lines if line) or None


def category_slugs(index: str) -> list[str]:
    found = re.findall(re.escape(LIBRARY) + r'/([a-z0-9-]+)"', index)
    return sorted({slug for slug in found if slug != "kategorie"})


def category_name(page: str) -> str:
    match = re.search(r'<h2 class="page-title">(.*?)</h2>', page, re.S)
    name = text_of(match.group(1)) if match else None
    if not name:
        raise ValueError("Category page without a title")
    return name


def library_entries(page: str, category_slug: str) -> list[tuple[str, str, str | None]]:
    """(slug, title, summary) of every innovation listed on a category page."""
    entries = []
    link = re.compile(re.escape(f"{LIBRARY}/{category_slug},") + r'([a-z0-9-]+)" class="news-list__title">(.*?)</a>',
                      re.S)
    for block in page.split('class="news-list__item"')[1:]:
        title = link.search(block)
        if not title:
            continue
        # the summary is the lead of the entry, before the award line and the icon table
        lead = re.search(r'class="news-list__desc">(.*?)(?:<p><strong>INNOWACJA|<table|class="btn)', block, re.S)
        summary = text_of(lead.group(1)) if lead else None
        entries.append((title.group(1), text_of(title.group(2)) or title.group(1), summary))
    return entries


def innovation_sections(page: str) -> dict[str, str | None]:
    """the numbered sections of an innovation page by column; a missing section is None."""
    start = page.find('<h2 class="page-title">')
    body = page[start + 1:] if start >= 0 else page
    # the sections end at the back button, or at the next heading on a page without one
    back = re.search(r"<a[^>]*>\s*Powrót\s*<", body)
    ends = [index for index in (back.start() if back else -1, body.find("<h2")) if index >= 0]
    body = body[:min(ends)] if ends else body
    parts = re.split(r"<h4[^>]*>(.*?)</h4>", body, flags=re.S)
    sections: dict[str, str | None] = {column: None for _, column in SECTIONS}
    for heading, content in zip(parts[1::2], parts[2::2]):
        key = (text_of(heading) or "").casefold()
        for needle, column in SECTIONS:
            if needle in key:
                sections[column] = text_of(content)
    if sections["authors"]:
        sections["authors"] = ", ".join(line.lstrip("- ").strip() for line in sections["authors"].splitlines())
    return sections


def collect() -> list[dict]:
    projects: dict[str, dict] = {}
    for category_slug in category_slugs(fetch(f"{LIBRARY}/kategorie")):
        page = fetch(f"{LIBRARY}/{category_slug}")
        category = category_name(page)
        entries = library_entries(page, category_slug)
        print(f"{category}: {len(entries)} innovations", file=sys.stderr)
        for slug, title, summary in entries:
            # an innovation listed under two categories keeps the first
            if slug in projects:
                continue
            time.sleep(PAUSE)
            projects[slug] = {
                "slug": slug,
                "title": title,
                "category": category,
                "category_slug": category_slug,
                "url": f"{SITE}{LIBRARY}/{category_slug},{slug}",
                "summary": summary or title,
                **innovation_sections(fetch(f"{LIBRARY}/{category_slug},{slug}")),
            }
    return [projects[slug] for slug in sorted(projects)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?",
                        default=Path(__file__).resolve().parents[2] / "db/seeds/rops_projects.json")
    args = parser.parse_args()
    try:
        projects = validate_projects(collect())
    except (HTTPError, URLError, OSError, ValueError) as error:
        print(f"Project collection failed: {error}", file=sys.stderr)
        return 1
    snapshot = {
        "format_version": 1,
        "source": SITE + LIBRARY,
        "collected_on": date.today().isoformat(),
        "projects": projects,
    }
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Collected {len(projects)} innovations into {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
