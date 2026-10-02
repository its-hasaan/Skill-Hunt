"""
Places named in job location fields and description sentences.

parse_places(text) -> Places(countries, regions, remote)
  countries: ISO 3166-1 alpha-2, lowercase ("us", "in", "pk", ...)
  regions:   worldwide, apac, south_asia, southeast_asia, east_asia, emea,
             middle_east, europe, americas, north_america, latam, africa,
             oceania
  remote:    a remote/anywhere word was present

membership(places, "pk") answers "can someone in Pakistan apply?" from the
places alone: True (named, or inside a region that contains it), False
(every place excludes it), None (nothing named, or a region that only
sometimes contains it, like EMEA for Pakistan).

Short codes are ambiguous, so they are read narrowly:
- "US", "USA", "UK", "UAE" only in capitals ("join us" is not a country).
- Two-letter US state codes only after a comma in structured location
  fields ("Austin, TX"); "IN" is never read (Indiana vs India).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# --- countries: ISO2 -> names and major tech cities (lowercase) ---------------
COUNTRY_ALIASES: dict[str, list[str]] = {
    "us": ["united states", "united states of america", "u.s.", "u.s.a.", "u.s", "america",
           # states
           "california", "texas", "new york", "washington", "florida", "massachusetts", "colorado",
           "illinois", "virginia", "north carolina", "oregon", "utah", "arizona", "michigan",
           "minnesota", "ohio", "pennsylvania", "new jersey", "maryland", "tennessee", "wisconsin",
           "indiana", "missouri", "connecticut", "nevada", "kentucky", "louisiana", "alabama",
           "south carolina", "iowa", "kansas", "oklahoma", "idaho", "montana", "new hampshire",
           "vermont", "maine", "rhode island", "delaware", "nebraska", "new mexico", "alaska",
           "hawaii", "arkansas", "mississippi", "west virginia", "wyoming", "north dakota",
           "south dakota",
           # cities
           "san francisco", "bay area", "sf bay area", "nyc", "new york city", "seattle", "boston",
           "austin", "chicago", "los angeles", "denver", "atlanta", "washington dc", "washington, d.c.",
           "miami", "portland", "san diego", "san jose", "palo alto", "mountain view", "sunnyvale",
           "menlo park", "foster city", "santa clara", "pleasanton", "redwood city", "oakland",
           "berkeley", "dallas", "houston", "philadelphia", "pittsburgh", "raleigh", "durham",
           "salt lake city", "phoenix", "minneapolis", "detroit", "nashville", "indianapolis",
           "columbus", "charlotte", "st. louis", "kansas city", "boulder", "irvine", "santa monica",
           "brooklyn", "jersey city", "baltimore", "tampa", "orlando", "las vegas", "sacramento",
           "cupertino", "san mateo", "burlingame", "bellevue", "redmond", "kirkland", "ann arbor",
           "milwaukee", "cincinnati", "cleveland", "reston", "mclean", "herndon", "arlington",
           "lehi", "provo", "scottsdale", "plano", "san antonio"],
    "ca": ["canada", "toronto", "vancouver", "montreal", "montréal", "ottawa", "calgary", "edmonton",
           "waterloo", "kitchener", "winnipeg", "halifax", "quebec", "québec", "ontario",
           "british columbia", "alberta", "nova scotia", "manitoba", "saskatchewan"],
    "gb": ["united kingdom", "great britain", "britain", "england", "scotland", "wales",
           "northern ireland", "london", "manchester", "edinburgh", "glasgow", "bristol",
           "birmingham", "leeds", "belfast"],
    "ie": ["ireland", "republic of ireland", "dublin", "cork", "galway"],
    "de": ["germany", "deutschland", "berlin", "munich", "münchen", "hamburg", "frankfurt",
           "cologne", "köln", "stuttgart", "düsseldorf"],
    "fr": ["france", "paris", "lyon", "toulouse"],
    "es": ["spain", "españa", "madrid", "barcelona", "valencia", "seville"],
    "pt": ["portugal", "lisbon", "porto"],
    "nl": ["netherlands", "the netherlands", "holland", "amsterdam", "rotterdam", "utrecht", "eindhoven"],
    "be": ["belgium", "brussels", "antwerp"],
    "ch": ["switzerland", "zurich", "zürich", "geneva", "lausanne", "basel"],
    "at": ["austria", "vienna"],
    "it": ["italy", "milan", "rome", "turin"],
    "pl": ["poland", "warsaw", "krakow", "kraków", "wroclaw", "wrocław", "gdansk", "gdańsk", "poznan"],
    "cz": ["czech republic", "czechia", "prague", "brno"],
    "ro": ["romania", "bucharest", "cluj", "cluj-napoca", "iasi"],
    "hu": ["hungary", "budapest"],
    "gr": ["greece", "athens"],
    "se": ["sweden", "stockholm", "gothenburg"],
    "no": ["norway", "oslo"],
    "dk": ["denmark", "copenhagen"],
    "fi": ["finland", "helsinki"],
    "ee": ["estonia", "tallinn"],
    "lv": ["latvia", "riga"],
    "lt": ["lithuania", "vilnius"],
    "ua": ["ukraine", "kyiv", "kiev", "lviv"],
    "rs": ["serbia", "belgrade", "novi sad"],
    "hr": ["croatia", "zagreb"],
    "bg": ["bulgaria"],
    "sk": ["slovakia", "bratislava"],
    "si": ["slovenia", "ljubljana"],
    "tr": ["turkey", "türkiye", "istanbul", "ankara"],
    "il": ["israel", "tel aviv", "jerusalem", "haifa"],
    "ae": ["united arab emirates", "dubai", "abu dhabi"],
    "sa": ["saudi arabia", "riyadh", "jeddah"],
    "qa": ["qatar", "doha"],
    "eg": ["egypt", "cairo"],
    "za": ["south africa", "cape town", "johannesburg"],
    "ng": ["nigeria", "lagos"],
    "ke": ["kenya", "nairobi"],
    "br": ["brazil", "brasil", "são paulo", "sao paulo", "rio de janeiro"],
    "mx": ["mexico", "méxico", "mexico city", "guadalajara", "monterrey"],
    "ar": ["argentina", "buenos aires"],
    "co": ["colombia", "bogota", "bogotá", "medellin", "medellín"],
    "cl": ["chile", "santiago"],
    "pe": ["peru"],
    "uy": ["uruguay", "montevideo"],
    "cr": ["costa rica"],
    "au": ["australia", "sydney", "melbourne", "brisbane", "perth", "adelaide", "canberra"],
    "nz": ["new zealand", "auckland", "wellington"],
    "sg": ["singapore"],
    "jp": ["japan", "tokyo", "osaka"],
    "kr": ["south korea", "korea", "seoul"],
    "cn": ["china", "beijing", "shanghai", "shenzhen", "hangzhou", "guangzhou"],
    "hk": ["hong kong"],
    "tw": ["taiwan", "taipei"],
    "ph": ["philippines", "manila", "cebu"],
    "id": ["indonesia", "jakarta"],
    "my": ["malaysia", "kuala lumpur"],
    "th": ["thailand", "bangkok"],
    "vn": ["vietnam", "viet nam", "ho chi minh", "hanoi"],
    "in": ["india", "bangalore", "bengaluru", "hyderabad", "pune", "chennai", "mumbai", "delhi",
           "new delhi", "delhi ncr", "gurgaon", "gurugram", "noida", "kolkata", "ahmedabad", "kochi",
           "cochin", "jaipur", "chandigarh", "coimbatore", "indore", "thiruvananthapuram",
           "trivandrum", "mysore", "nagpur", "vadodara"],
    "pk": ["pakistan", "lahore", "karachi", "islamabad", "rawalpindi", "faisalabad", "peshawar",
           "multan", "quetta", "sialkot"],
    "bd": ["bangladesh", "dhaka"],
    "lk": ["sri lanka", "colombo"],
    "np": ["nepal", "kathmandu"],
}

REGION_ALIASES: dict[str, list[str]] = {
    "worldwide": ["worldwide", "world wide", "anywhere", "global", "globally", "anywhere in the world"],
    "apac": ["apac", "asia pacific", "asia-pacific", "asia"],
    "south_asia": ["south asia", "indian subcontinent"],
    "southeast_asia": ["southeast asia", "south east asia", "south-east asia"],
    "east_asia": ["east asia"],
    "emea": ["emea"],
    "middle_east": ["middle east", "mena"],
    "europe": ["europe", "european union", "eea", "dach", "nordics", "benelux", "central europe",
               "eastern europe", "western europe"],
    "americas": ["americas", "amer", "amers"],
    "north_america": ["north america", "noram"],
    "latam": ["latam", "latin america", "south america", "central america"],
    "africa": ["africa"],
    "oceania": ["oceania", "anz"],
}

# Capital-only short codes (case-sensitive).
SHORT_CODES = {"US": "us", "USA": "us", "UK": "gb", "UAE": "ae"}
SHORT_REGIONS = {"EU": "europe"}

US_STATE_CODES = ("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IA KS KY LA ME MD MA MI MN MS MO MT NE "
                  "NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY").split()

REMOTE_RE = re.compile(r"\b(remote|anywhere|worldwide|distributed|work from home|wfh|home[- ]based)\b",
                       re.IGNORECASE)

# Regions that always / sometimes contain a country of interest.
REGION_INCLUDES = {"worldwide": {"pk", "in"}, "apac": {"pk", "in"}, "south_asia": {"pk", "in"}}
REGION_MAYBE = {"emea": {"pk"}, "middle_east": {"pk"}}


def _alternation(aliases: dict[str, list[str]]) -> tuple[re.Pattern, dict[str, str]]:
    lookup = {alias: code for code, names in aliases.items() for alias in names}
    body = "|".join(re.escape(a) for a in sorted(lookup, key=len, reverse=True))
    return re.compile(rf"(?<![\w])(?:{body})(?![\w])", re.IGNORECASE), lookup


_COUNTRY_RE, _COUNTRY_LOOKUP = _alternation(COUNTRY_ALIASES)
_REGION_RE, _REGION_LOOKUP = _alternation(REGION_ALIASES)
_SHORT_RE = re.compile(r"(?<![A-Za-z.])(USA|US|UK|UAE|EU)(?![A-Za-z])")
_STATE_RE = re.compile(r",\s*(" + "|".join(US_STATE_CODES) + r")(?=\s*(?:$|[,;)(|/\-]|\d))")


@dataclass(frozen=True)
class Places:
    countries: frozenset
    regions: frozenset
    remote: bool

    @property
    def empty(self) -> bool:
        return not self.countries and not self.regions


NOWHERE = Places(frozenset(), frozenset(), False)


def parse_places(text: str, structured: bool = True) -> Places:
    """Countries/regions named in `text`. `structured` = a location field
    (enables "Austin, TX"-style state codes)."""
    if not text:
        return NOWHERE
    countries: set[str] = set()
    regions: set[str] = set()
    # Regions first, then blank them out so "south asia" doesn't also read as "asia"
    # and "Asia" inside "Southeast Asia" isn't double counted.
    remaining = text
    for m in _REGION_RE.finditer(text):
        regions.add(_REGION_LOOKUP[m.group(0).lower()])
    remaining = _REGION_RE.sub(" ", remaining)
    for m in _COUNTRY_RE.finditer(remaining):
        countries.add(_COUNTRY_LOOKUP[m.group(0).lower()])
    for m in _SHORT_RE.finditer(remaining):
        code = m.group(1)
        if code in SHORT_CODES:
            countries.add(SHORT_CODES[code])
        else:
            regions.add(SHORT_REGIONS[code])
    if structured and _STATE_RE.search(remaining):
        countries.add("us")
    return Places(frozenset(countries), frozenset(regions), bool(REMOTE_RE.search(text)))


def merge(*places: Places) -> Places:
    return Places(
        frozenset().union(*(p.countries for p in places)),
        frozenset().union(*(p.regions for p in places)),
        any(p.remote for p in places),
    )


def membership(places: Places, country: str):
    if places.empty:
        return None
    if country in places.countries:
        return True
    if any(country in REGION_INCLUDES.get(r, ()) for r in places.regions):
        return True
    if any(country in REGION_MAYBE.get(r, ()) for r in places.regions):
        return None
    return False
