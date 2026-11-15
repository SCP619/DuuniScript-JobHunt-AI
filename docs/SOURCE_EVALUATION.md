# DuuniScript — Job Source Evaluation

**Evaluated:** 2026-11-10  
**Method:** For each source: read `robots.txt`; find one current job page (using a normal
browser where listings need JavaScript, declining non-essential cookies); run DuuniScript's real
URL import (safe fetcher + robots check + JSON-LD parser) against it, a few requests per site
with pauses. No job content was stored; this document records findings only.

Access classification follows BSD section 3. **No source below is enabled for automated or
scheduled scanning.** Each still needs its terms of use reviewed and documented (BSD 4) before
an adapter is built.

## Summary

| Source | robots.txt for job pages | Structured `JobPosting` data | URL import today | Classification | Recommendation |
|---|---|---|---|---|---|
| Kuntarekry | Allowed (`Allow: /`) | Yes | ✅ Works | Public structured data; terms not yet reviewed | Good URL-import source. Review terms before any scanning. |
| Valtiolle.fi | Allowed for job pages | Yes (same platform as Kuntarekry) | ✅ Works | Public structured data; terms not yet reviewed | As Kuntarekry. |
| Jobly | Allowed (only admin and static paths blocked) | Yes | ✅ Works | Public structured data; terms not yet reviewed | Good URL-import source. |
| Åbo Akademi (abo.rekrytointi.com) | Allowed | No on job pages | ❌ "Add manually" | **Official feed** (RSS) | Best candidate for the first scheduled adapter: RSS items have title, link, description, published date, start date and end date. |
| Työmarkkinatori | Allowed, except `/api/` | No (page built by JavaScript) | ❌ "Add manually" | Public page, JavaScript-only | Check whether an official open-data interface exists for job ads; do not use the site's internal `/api/`. |
| Duunitori | **Disallowed** (`User-agent: *` / `Disallow: /`; only named search engines allowed) | Not checked | 🚫 Refused by robots check | Restricted | Manual entry only. |
| Academic Positions | n/a | n/a | 🚫 HTTP 403 to automated requests | Restricted (bot protection) | Manual entry only. Do not work around the block. |
| EURAXESS | n/a | n/a | 🚫 HTTP 403 to automated requests | Restricted (bot protection) | Manual entry only. Check for an official feed or API. |
| University of Turku | n/a | n/a | ❌ eRekry link leads to a login page (Talentadore) | Login-based | Manual entry only. |
| Turku UAS (Turku AMK) | Allowed | Not found | Not tested | Unknown | No public vacancy listing found by this evaluation. Investigate further. |

## Findings that changed the code

1. **robots.txt is now enforced for URL import** (RFC 9309: wildcards, longest match wins, `Allow`
   wins ties; checked on every redirect hop; cached for one hour). Duunitori blocks generic
   agents, and a user-initiated import is still an automated request from DuuniScript.
   Python's built-in `urllib.robotparser` was **not** used: it ignores wildcards, and it fetches
   `robots.txt` with its own user agent, which Jobly answers with 403, making it wrongly treat
   the whole site as forbidden.
2. **Finnish free-text employment types** (Kuntarekry and Valtiolle publish e.g.
   "Kokoaikatyö, 3-vuorotyö, Vakinainen, Työsuhde"). Unambiguous Finnish and Swedish words for
   full-time, part-time and internship are now mapped. Words about permanence (vakinainen,
   määräaikainen) describe contract duration, not working time, so they are not mapped.
3. **Empty salary structures** (Jobly publishes `minValue: ""`) no longer produce junk such as
   "€ EUR". Free-text salaries are kept in the publisher's exact wording.
4. **Country-only extra locations** (Jobly) no longer produce "Turku, FI; FI".
5. Parser version bumped to `jsonld-2`; new regression tests reproduce each real-world shape with
   synthetic values.

## English versions (checked 2026-11-10)

DuuniScript asks for English and follows a page's own declared English version (parser
`jsonld-3`). In practice this rarely changes the text:

- **Jobly** declares an English page for each posting (`/en/job/...`), but it only translates the
  site menus: the advertisement in its structured data is the same Finnish text. DuuniScript
  checks it, sees Finnish, and keeps the original, labelled Finnish.
- **Kuntarekry** and **Valtiolle** have English site sections (`/en/`). An English advertisement
  is published only when the employer writes one. Per-posting English alternates on these
  sites have not been checked yet; if a posting declares one, the rule above applies.
- Most Finnish postings exist only in Finnish. Translation would need the planned local model and
  would be clearly marked as a machine translation; it is not built.

## Known source limitations (not fixed on purpose)

- Kuntarekry and Valtiolle strip paragraph breaks from the description in their structured data
  (sentences run together). DuuniScript keeps the publisher's text unchanged instead of guessing
  where breaks belong.
- None of the working sources publishes a job ID in its structured data; duplicates are detected
  by normalised URL instead.
- Kuntarekry and Valtiolle publish employer names as full organisational paths (for example
  wellbeing services county, hospital and unit). They are stored as published.
- Publication timestamps are given with a +02:00 offset; DuuniScript stores the calendar date as
  published, without converting it to UTC.

## Job alert emails (checked 2026-11-10)

Sites that refuse automated access can still be followed through the alert emails they send to
the user (docs/BACKEND_SETUP.md, section 10). Checked against real alerts in the user's mailbox:

- **LinkedIn** (`jobalerts-noreply@linkedin.com`, `jobs-noreply@linkedin.com`): the plain-text
  part lists title, company and location, then "View job: <link>". Links carry a sign-in token
  (`otpToken`), which is dropped. No posting date or description.
- **Glassdoor** (`noreply@glassdoor.com`): HTML only. Each card is one link containing company,
  rating, title, location, "Easy Apply" and an age ("3d", "14h", "30d+"). The site itself sits
  behind a bot check, so the link is kept exactly as sent.
- No Duunitori, Jobly, Indeed, Oikotie or Kuntarekry alert emails were in the mailbox, so those
  formats are untested.

## Remote job sites (checked 2026-11-10)

The user's list of remote-job sites, plus four alternatives, checked for status, robots.txt,
official feeds or APIs, and terms. Nothing was scraped and no access control was bypassed.

| Site | Finding | Decision |
|---|---|---|
| Remotive | Free public API; terms: link back, name Remotive, max. 4 reads a day, jobs delayed 24 h. robots.txt lists `/api/*` for crawlers. | **Feed** (`feed_remotive`), every 6 h |
| Jobspresso | WordPress job RSS (`/feed/job_feed/`, allowed by robots.txt; `?feed=` form is not). Terms: personal, non-commercial use. Most jobs are US-only. | **Feed** (`feed_jobspresso`) |
| We Work Remotely | Public RSS feeds, robots.txt allows. Terms page did not load without JavaScript. | **Feed** (`feed_weworkremotely`) |
| Himalayas | Free public API; terms explicitly allow use by a personal agent; don't pass jobs on. | **Feed** (`feed_himalayas`), first page only (robots.txt lists `&page=`) |
| Jobicy | Free public API; credit Jobicy, link to the original, poll at most once an hour. | **Feed** (`feed_jobicy`) |
| Arbeitnow | Free public API; "please link back". Mostly on-site jobs in Germany. | **Feed** (`feed_arbeitnow`), remote jobs only |
| Åbo Akademi | Official RSS of the Laura recruitment system (Turku). | **Feed** (`feed_abo_akademi`) |
| Dynamite Jobs | robots.txt allows job pages; JobPosting data present; no job feed (its RSS is the blog). | **URL import works** (tested) |
| Idealist | robots.txt allows job pages; JobPosting data present. | **URL import works** (tested) |
| SkipTheDrive | robots.txt: `Disallow: /job/` for all agents. Mostly US. | Not used (import is refused) |
| Europe Remotely | robots.txt: `Disallow: /` for all agents; site returns 403. | **Alert emails** (`alert_europeremotely`, format not yet checked) |
| ZipRecruiter | US/UK/IE jobs; terms not reviewed. | **Alert emails** (`alert_ziprecruiter`, format not yet checked) |
| Virtual Vocations | robots.txt allows, but US-focused and, as far as known, full details need a paid membership (not confirmed). | Not used |
| GitHub Jobs | Closed in 2021; address does not respond. | Not used |
| Outsourcely, CloudPeeps | Addresses do not respond. | Not used |
| Pangian | Domain forwards to a parked page. | Not used |
| CareerHound | AI job-search product and articles, not a job board. | Not used |
| Snagajob | US hourly jobs; refused the check (403). | Not used |
| Bandana | US hourly jobs; robots.txt blocks `/api` and AI crawlers. | Not used |

Third-party "scraper" services and reverse-engineering a site's private API were not used: they
collect data against the site's own rules, which using them through a third party does not change.

## Finnish public-sector sources (checked 2026-11-11)

| Site | Finding | Decision |
|---|---|---|
| Työmarkkinatori (Job Market Finland) | Has a job-ad search API (Hakurajapinta), but it is not open data: use needs an agreement with the KEHA Centre, acceptance of its terms and a Finnish business ID (Y-tunnus). Not available to a private person. | **Alert emails** (`alert_tyomarkkinatori`, already supported) |
| Kuntarekry | RSS/XML feeds exist only for employer accounts (to show their own ads); no public feed or API was found. | **Alert emails** (`alert_kuntarekry`, already supported) |
| Valtiolle | robots.txt allows everything, but there is no feed, API or open data, and job lists are loaded by the page's own scripts (an undocumented internal API, not used). The site offers job alert emails. | **Alert emails** (`alert_valtiolle`, new, format not yet checked) |
| Jobly | robots.txt asks for `Crawl-delay: 10`; no public feed or API found. | **Alert emails** (`alert_jobly`, already supported) |
| EURAXESS | No job feed found; robots.txt does not block job pages. | Not added; check a job page for schema.org JobPosting data before relying on URL import |

The user's mailbox had no Europe Remotely, ZipRecruiter or Valtiolle alert emails on
2026-11-11 (only Kuntarekry application messages, which are not alerts), so those three formats
stay unverified until the user subscribes and one arrives.

## Next steps

1. Subscribe to job alerts on Valtiolle, Kuntarekry, Työmarkkinatori, Jobly and Duunitori with
   the DuuniScript mailbox label; check the unverified formats when the first emails arrive.
2. Check whether EURAXESS job pages carry schema.org JobPosting data (URL import).
3. Re-run this evaluation periodically. Sites change their markup and policies.
