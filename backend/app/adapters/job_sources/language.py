"""Language of a job posting, and links to other-language versions of the same page.

Detection is deliberately conservative. It recognises only English, Finnish and Swedish by
counting very common function words, and returns ``None`` unless one language clearly wins.
A page's address or interface language says nothing about the posting text: several Finnish
boards serve an "English" page that wraps the same Finnish advertisement.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin

STOPWORDS = {
    "en": {
        "the", "and", "of", "to", "for", "with", "you", "we", "our", "is", "are", "will", "be",
        "your", "this", "that", "have", "experience", "team", "work", "who", "an", "or", "as",
    },
    "fi": {
        "ja", "sekä", "tai", "että", "olet", "olemme", "meidän", "sinulla", "haemme", "kanssa",
        "myös", "joka", "jotka", "voit", "ovat", "työ", "tehtävä", "tehtäviin", "kokemusta",
        "hakemus", "meillä", "sinä", "tarjoamme", "osaamista", "ei", "kuin",
    },
    "sv": {
        "och", "att", "är", "för", "med", "som", "vi", "du", "ett", "på", "av", "har", "söker",
        "inom", "vår", "din", "erfarenhet", "arbete", "kommer", "till", "eller",
    },
}
MIN_HITS = 5
WORD = re.compile(r"[a-zåäö]+")


def detect_language(text: str | None) -> str | None:
    """Return ``en``, ``fi`` or ``sv`` when the text is clearly in that language, else ``None``."""
    if not text:
        return None
    counts = dict.fromkeys(STOPWORDS, 0)
    for word in WORD.findall(text[:20_000].lower()):
        for code, words in STOPWORDS.items():
            if word in words:
                counts[code] += 1
    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    (best, best_hits), (_, second_hits) = ranked[0], ranked[1]
    if best_hits < MIN_HITS or best_hits < 2 * second_hits:
        return None
    return best


def primary_language(code: str | None) -> str | None:
    """``fi-FI`` -> ``fi``; anything that is not a language tag -> ``None``."""
    if not code:
        return None
    match = re.fullmatch(r"([A-Za-z]{2,3})(-[A-Za-z0-9]{2,8})?", code.strip())
    return match.group(1).lower() if match else None


class _AlternateCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "link":
            return
        values = {k.lower(): (v or "") for k, v in attrs}
        if "alternate" in values.get("rel", "").lower().split() and values.get("hreflang") and values.get("href"):
            self.links.append((values["hreflang"], values["href"]))


def alternate_url(page_html: str, base_url: str, language: str) -> str | None:
    """The page's own declared ``<link rel="alternate" hreflang=...>`` for ``language``."""
    collector = _AlternateCollector()
    try:
        collector.feed(page_html)
        collector.close()
    except Exception:  # noqa: BLE001 - malformed markup just means no alternate
        return None
    for hreflang, href in collector.links:
        if primary_language(hreflang) == language:
            return urljoin(base_url, href.strip())
    return None
