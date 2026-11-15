"""Can this job be done by someone living in Finland (Turku)?

``available_from_finland`` is ``yes``, ``no`` or ``unknown``. It is read only from what the
posting states: a work location in Finland, or a remote job open to Finland (worldwide,
Europe/EU/EMEA, the Nordics, Finland itself, or a time zone that includes Finland). A remote
job limited to other countries (e.g. "USA only") is ``no``. Anything unclear is ``unknown``;
nothing is guessed.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

YES, NO, UNKNOWN = "yes", "no", "unknown"
FINLAND_UTC_OFFSET = 2  # standard time (EET); summer time is UTC+3

# Words that put the job in Finland or open it to people living in Finland.
_OPEN = [
    r"finland", r"suomi", r"finnish", r"fi", r"fin", r"turku", r"åbo", r"helsinki", r"helsingfors", r"espoo",
    r"vantaa", r"tampere", r"oulu", r"jyväskylä", r"kuopio", r"lahti", r"pori", r"vaasa",
    r"joensuu", r"lappeenranta", r"rovaniemi", r"salo", r"raisio", r"kaarina", r"naantali",
    # More Finnish municipalities (job alerts often name only the town).
    r"lieto", r"masku", r"mynämäki", r"nousiainen", r"paimio", r"sauvo", r"parainen", r"pargas",
    r"uusikaupunki", r"laitila", r"loimaa", r"rauma", r"eura", r"eurajoki", r"harjavalta", r"kankaanpää",
    r"ulvila", r"nakkila", r"huittinen", r"forssa", r"hämeenlinna", r"riihimäki", r"hyvinkää", r"järvenpää",
    r"kerava", r"tuusula", r"nurmijärvi", r"mäntsälä", r"porvoo", r"borgå", r"loviisa", r"kirkkonummi",
    r"kyrkslätt", r"siuntio", r"lohja", r"vihti", r"karkkila", r"raasepori", r"raseborg", r"hanko", r"hangö",
    r"inkoo", r"kauniainen", r"grankulla", r"sipoo", r"pornainen", r"askola", r"lapinjärvi", r"kotka",
    r"hamina", r"kouvola", r"mikkeli", r"savonlinna", r"pieksämäki", r"imatra", r"heinola", r"orimattila",
    r"hollola", r"asikkala", r"nastola", r"valkeakoski", r"akaa", r"kangasala", r"lempäälä", r"pirkkala",
    r"nokia", r"ylöjärvi", r"sastamala", r"orivesi", r"mänttä-vilppula", r"parkano", r"ikaalinen",
    r"seinäjoki", r"lapua", r"kauhava", r"kurikka", r"alavus", r"ähtäri", r"kokkola", r"karleby",
    r"jakobstad", r"pietarsaari", r"kristinestad", r"kristiinankaupunki", r"närpes", r"närpiö", r"mustasaari",
    r"korsholm", r"ylivieska", r"raahe", r"kajaani", r"iisalmi", r"varkaus", r"siilinjärvi", r"kemi",
    r"tornio", r"kemijärvi", r"sodankylä", r"inari", r"kittilä", r"kuusamo", r"kempele", r"liminka",
    r"jämsä", r"äänekoski", r"keuruu", r"saarijärvi", r"viitasaari", r"laukaa", r"muurame", r"kitee",
    r"nurmes", r"lieksa", r"kontiolahti", r"liperi", r"outokumpu", r"mariehamn", r"maarianhamina", r"åland",
    r"ahvenanmaa", r"vaasa", r"vasa",
    r"worldwide", r"world ?wide", r"anywhere", r"global(?:ly)?", r"international",
    r"europe(?:an)?", r"eu", r"eea", r"emea", r"nordics?", r"scandinavia", r"baltics?",
    r"cet", r"cest", r"eet", r"eest", r"(?:utc|gmt) ?\+ ?[123]",
]
# Places that say where a job is when they appear without any of the words above.
_ELSEWHERE = [
    r"usa?", r"u\.s\.a?\.?", r"united states", r"america", r"americas", r"north america",
    r"latam", r"latin america", r"south america", r"canada", r"mexico", r"brazil", r"argentina",
    r"colombia", r"chile", r"peru", r"uk", r"united kingdom", r"england", r"ireland", r"india",
    r"pakistan", r"philippines", r"apac", r"asia", r"asia-pacific", r"australia",
    r"new zealand", r"singapore", r"japan", r"china", r"africa", r"nigeria", r"south africa",
    r"kenya", r"egypt", r"israel", r"uae", r"saudi arabia", r"turkey", r"türkiye", r"germany",
    r"deutschland", r"france", r"spain", r"portugal", r"italy", r"netherlands", r"belgium",
    r"switzerland", r"austria", r"poland", r"romania", r"czechia", r"hungary", r"sweden",
    r"norway", r"denmark", r"estonia", r"latvia", r"lithuania", r"greece", r"ukraine",
    r"[a-z ]+, (?:ca|ny|tx|wa|ma|fl|il|co|ga|nc|va|or|az|pa|nj|mn|ut|oh|mi)",
    # More countries.
    r"serbia", r"bulgaria", r"croatia", r"slovakia", r"slovenia", r"luxembourg", r"bosnia", r"albania",
    r"north macedonia", r"moldova", r"belarus", r"russia", r"cyprus", r"malta", r"iceland", r"vietnam",
    r"indonesia", r"malaysia", r"thailand", r"bangladesh", r"sri lanka", r"south korea", r"korea", r"taiwan",
    r"hong kong", r"morocco", r"tunisia", r"ghana", r"uruguay", r"costa rica",
    # US states, and DC.
    r"alabama", r"alaska", r"arizona", r"arkansas", r"california", r"colorado", r"connecticut", r"delaware",
    r"florida", r"georgia, usa", r"hawaii", r"idaho", r"illinois", r"indiana", r"iowa", r"kansas", r"kentucky",
    r"louisiana", r"maine", r"maryland", r"massachusetts", r"michigan", r"minnesota", r"mississippi",
    r"missouri", r"montana", r"nebraska", r"nevada", r"new hampshire", r"new jersey", r"new mexico",
    r"new york", r"north carolina", r"north dakota", r"ohio", r"oklahoma", r"oregon", r"pennsylvania",
    r"rhode island", r"south carolina", r"south dakota", r"tennessee", r"texas", r"utah", r"vermont",
    r"virginia", r"washington, dc", r"washington dc", r"west virginia", r"wisconsin", r"wyoming",
    # Cities that job alerts name without their country.
    r"vienna", r"wien", r"graz", r"linz", r"salzburg", r"innsbruck", r"klagenfurt", r"wiener neudorf",
    r"schwechat", r"guntramsdorf", r"mödling", r"st\.? pölten", r"berlin", r"munich", r"münchen",
    r"hamburg", r"frankfurt", r"cologne", r"köln", r"düsseldorf", r"stuttgart", r"leipzig", r"dresden",
    r"amsterdam", r"rotterdam", r"utrecht", r"the hague", r"eindhoven", r"brussels", r"antwerp", r"ghent",
    r"paris", r"lyon", r"marseille", r"toulouse", r"madrid", r"barcelona", r"valencia", r"lisbon", r"porto",
    r"rome", r"milan", r"turin", r"zurich", r"zürich", r"geneva", r"basel", r"bern", r"lausanne",
    r"london", r"manchester", r"edinburgh", r"glasgow", r"birmingham", r"bristol", r"dublin", r"cork",
    r"stockholm", r"gothenburg", r"göteborg", r"malmö", r"uppsala", r"oslo", r"bergen", r"copenhagen",
    r"københavn", r"aarhus", r"tallinn", r"tartu", r"riga", r"vilnius", r"warsaw", r"warszawa", r"krakow",
    r"kraków", r"wroclaw", r"wrocław", r"gdansk", r"poznan", r"prague", r"praha", r"brno", r"budapest",
    r"bratislava", r"bucharest", r"sofia", r"belgrade", r"zagreb", r"ljubljana", r"athens", r"istanbul",
    r"kyiv", r"kiev", r"lviv", r"limmared", r"new york city", r"san francisco", r"seattle", r"boston",
    r"chicago", r"austin", r"toronto", r"vancouver", r"montreal", r"bangalore", r"bengaluru", r"hyderabad",
    r"mumbai", r"delhi", r"dhaka", r"singapore city", r"sydney", r"melbourne", r"dubai", r"tel aviv",
    r"pst", r"est", r"cst", r"mst", r"(?:utc|gmt) ?[-−] ?\d+",
]
_OPEN_RE = re.compile(r"(?<![a-zåäö])(?:" + "|".join(_OPEN) + r")(?![a-zåäö])")
_ELSEWHERE_RE = re.compile(r"(?<![a-zåäö])(?:" + "|".join(_ELSEWHERE) + r")(?![a-zåäö])")
_ONLY_RE = re.compile(r"\b(only|must (?:be|reside|live)|based in|residents? of|located in)\b")


def from_text(text: str | None) -> str:
    """Judge a stated location or "candidates must be in ..." text."""
    if not text or not text.strip():
        return UNKNOWN
    lowered = " ".join(text.lower().replace("_", " ").split())
    if "\ufffd" in lowered:
        # Unreadable letters in a Finnish name ("Sein\ufffdjoki"): read them as ä or ö.
        lowered = lowered.replace("\ufffd", "ä") if _OPEN_RE.search(lowered.replace("\ufffd", "ä")) else lowered.replace("\ufffd", "ö")
    if _OPEN_RE.search(lowered):
        if re.search(r"\b(?:europe|eu|emea)\b", lowered) and re.search(r"\bexcept\b[^.]*\bfinland\b", lowered):
            return NO
        return YES
    if _ELSEWHERE_RE.search(lowered) or _ONLY_RE.search(lowered):
        return NO
    return UNKNOWN


_TITLE_LIMIT = re.compile(
    r"(?<![a-z])(?:u\.?s\.?a?|united states|uk|canada|latam|americas?|india|apac)\.?[ -]?(?:only|based|residents?)(?![a-z])"
    r"|(?<![a-z])(?:only|based) in (?:the )?(?:u\.?s\.?a?|united states|uk|canada|latam|india)(?![a-z])"
)


def title_restriction(title: str | None) -> bool:
    """A job title that itself limits the job to another country ("Web Developer (U.S. Based)")."""
    return bool(title and _TITLE_LIMIT.search(title.lower()))


def from_restrictions(countries: Iterable[str] | None, utc_offsets: Iterable[float] | None) -> str:
    """Structured lists (empty country list = any country; offsets must include Finland's)."""
    country_list = [c for c in (countries or []) if isinstance(c, str) and c.strip()]
    if country_list and from_text(", ".join(country_list)) != YES:
        return NO
    offsets = [o for o in (utc_offsets or []) if isinstance(o, (int, float))]
    if offsets and FINLAND_UTC_OFFSET not in offsets:
        return NO
    return YES


def assess(location: str | None) -> str:
    """For any job, from its stated location: a place in Finland, or a remote job open to
    Finland, is ``yes``; a place or remote restriction elsewhere is ``no``. (A job located
    elsewhere could still be remote, but the posting would then say where it is open to.)"""
    return from_text(location)
