"""robots.txt evaluation following RFC 9309.

Python's ``urllib.robotparser`` is not used because it ignores ``*``/``$`` wildcards and
fetches robots.txt with its own user agent (some sites answer that with 403, which it then
treats as "disallow everything").

Rules implemented:
- The group for our product token (``duuniscript``) is used if present, otherwise ``*``.
  Multiple groups for the same agent are combined.
- The longest matching rule wins; on a tie ``Allow`` wins. ``*`` matches any sequence and a
  trailing ``$`` anchors the end. An empty ``Disallow`` allows everything.
- robots.txt answering 4xx: no restrictions. 5xx or unreachable: treat as fully disallowed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

PRODUCT_TOKEN = "duuniscript"
MAX_ROBOTS_BYTES = 500 * 1024


@dataclass
class RobotsRules:
    rules: list[tuple[bool, str]] = field(default_factory=list)  # (allow, pattern)
    disallow_all: bool = False

    @classmethod
    def allow_everything(cls) -> RobotsRules:
        return cls()

    @classmethod
    def unreachable(cls) -> RobotsRules:
        return cls(disallow_all=True)

    def allows(self, url: str) -> bool:
        if self.disallow_all:
            return False
        parts = urlsplit(url)
        target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        best_len, best_allow = -1, True
        for allow, pattern in self.rules:
            if not pattern:
                continue  # empty Disallow/Allow places no restriction
            if _matches(pattern, target):
                length = len(pattern)
                if length > best_len or (length == best_len and allow):
                    best_len, best_allow = length, allow
        return best_allow


def _matches(pattern: str, target: str) -> bool:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    return re.match(regex + ("$" if anchored else ""), target) is not None


def parse_robots(text: str, product_token: str = PRODUCT_TOKEN) -> RobotsRules:
    groups: list[tuple[list[str], list[tuple[bool, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[bool, str]] = []
    last_was_agent = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if not last_was_agent and (agents or rules):
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value.lower())
            last_was_agent = True
        elif key in ("allow", "disallow"):
            if agents:
                rules.append((key == "allow", value))
            last_was_agent = False
        else:
            last_was_agent = False
    if agents:
        groups.append((agents, rules))

    token = product_token.lower()
    specific = [r for a, r in groups if token in a]
    chosen = specific or [r for a, r in groups if "*" in a]
    return RobotsRules(rules=[rule for group in chosen for rule in group])
