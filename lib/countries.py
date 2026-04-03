"""Country, continent, flag, and display-location logic."""

# ── Flag emoji helper ─────────────────────────────────────────────────────────
def _flag(code):
    return ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in code.upper())

COUNTRY_FLAGS = {
    'United States':  _flag('US'),
    'Canada':         _flag('CA'),
    'United Kingdom': _flag('GB'),
    'Ireland':        _flag('IE'),
    'Australia':      _flag('AU'),
    'New Zealand':    _flag('NZ'),
    'India':          _flag('IN'),
    'Philippines':    _flag('PH'),
    'Singapore':      _flag('SG'),
    'Thailand':       _flag('TH'),
    'Japan':          _flag('JP'),
    'Norway':         _flag('NO'),
    'Netherlands':    _flag('NL'),
    'Argentina':      _flag('AR'),
    'Brazil':         _flag('BR'),
    'Colombia':       _flag('CO'),
    'Mexico':         _flag('MX'),
    'Morocco':        _flag('MA'),
    'Egypt':          _flag('EG'),
    'Ethiopia':       _flag('ET'),
    'Kenya':          _flag('KE'),
    'Turkey':         _flag('TR'),
    'Lebanon':        _flag('LB'),
    'Iran':           _flag('IR'),
    'Israel':         _flag('IL'),
    'Austria':        _flag('AT'),
    'Hungary':        _flag('HU'),
    'Finland':        _flag('FI'),
    'Portugal':       _flag('PT'),
    'Spain':          _flag('ES'),
    'Croatia':        _flag('HR'),
    'Greece':         _flag('GR'),
    'Slovenia':       _flag('SI'),
    'Ukraine':        _flag('UA'),
    'Iceland':        _flag('IS'),
    'Kazakhstan':     _flag('KZ'),
    'Kyrgyzstan':     _flag('KG'),
    'Antarctica':     _flag('AQ'),
}

# ── Continent mapping ─────────────────────────────────────────────────────────
COUNTRY_CONTINENT = {
    'United States': 'North America', 'Canada': 'North America', 'Mexico': 'North America',
    'United Kingdom': 'Europe', 'Ireland': 'Europe', 'France': 'Europe', 'Germany': 'Europe',
    'Spain': 'Europe', 'Portugal': 'Europe', 'Netherlands': 'Europe', 'Finland': 'Europe',
    'Austria': 'Europe', 'Greece': 'Europe', 'Croatia': 'Europe', 'Norway': 'Europe',
    'Ukraine': 'Europe', 'Iceland': 'Europe', 'Slovenia': 'Europe', 'Hungary': 'Europe',
    'Belgium': 'Europe', 'Switzerland': 'Europe', 'Serbia': 'Europe', 'Romania': 'Europe',
    'Bulgaria': 'Europe', 'Czech Republic': 'Europe',
    'India': 'Asia', 'Philippines': 'Asia', 'Thailand': 'Asia', 'Japan': 'Asia',
    'China': 'Asia', 'South Korea': 'Asia', 'Singapore': 'Asia', 'Kyrgyzstan': 'Asia',
    'Kazakhstan': 'Asia', 'Lebanon': 'Asia', 'Iran': 'Asia', 'Israel': 'Asia', 'Turkey': 'Asia',
    'Egypt': 'Africa', 'Ethiopia': 'Africa', 'Kenya': 'Africa', 'Morocco': 'Africa',
    'South Africa': 'Africa', 'Nigeria': 'Africa',
    'Colombia': 'South America', 'Brazil': 'South America', 'Argentina': 'South America',
    'Uruguay': 'South America', 'Peru': 'South America',
    'Australia': 'Oceania', 'New Zealand': 'Oceania',
    'Antarctica': 'Antarctica',
}

# ── Display location → flag-emoji format ──────────────────────────────────────
# Format: "City, ST 🇺🇸" — no dash, no spelled-out country name
_US = _flag('US')
_CA = _flag('CA')
_GB = _flag('GB')
_IE = _flag('IE')

DISPLAY_LOC = {
    # Canada
    'Ontario, Canada':      f'Ontario {_CA}',
    'Toronto, Canada':      f'Toronto, ON {_CA}',
    'Vancouver':            f'Vancouver, BC {_CA}',
    'Calgary':              f'Calgary, AB {_CA}',
    'Halifax':              f'Halifax, NS {_CA}',
    'Windsor, Ontario':     f'Windsor, ON {_CA}',
    'Georgetown, Ontario':  f'Georgetown, ON {_CA}',
    'Collingwood, Ontario': f'Collingwood, ON {_CA}',
    'Manitoulin Island':    f'Manitoulin Island, ON {_CA}',
    'Canadian Far North':   f'Canadian Far North {_CA}',
    'Canada':               f'Canada {_CA}',
    # USA — cities
    'New York City':        f'New York City, NY {_US}',
    'Los Angeles':          f'Los Angeles, CA {_US}',
    'Chicago':              f'Chicago, IL {_US}',
    'Miami':                f'Miami, FL {_US}',
    'Seattle':              f'Seattle, WA {_US}',
    'Nashville':            f'Nashville, TN {_US}',
    'Orlando':              f'Orlando, FL {_US}',
    'Dallas':               f'Dallas, TX {_US}',
    'Salt Lake City':       f'Salt Lake City, UT {_US}',
    'Las Vegas':            f'Las Vegas, NV {_US}',
    'Sacramento':           f'Sacramento, CA {_US}',
    'Detroit':              f'Detroit, MI {_US}',
    'Minneapolis':          f'Minneapolis, MN {_US}',
    'Atlanta':              f'Atlanta, GA {_US}',
    'Reno':                 f'Reno, NV {_US}',
    'Baltimore':            f'Baltimore, MD {_US}',
    'Milwaukee':            f'Milwaukee, WI {_US}',
    # USA — city + state code
    'Tucson, AZ':           f'Tucson, AZ {_US}',
    'Woburn, MA':           f'Woburn, MA {_US}',
    'Lakewood, CA':         f'Lakewood, CA {_US}',
    'Mountain View, CA':    f'Mountain View, CA {_US}',
    'Bellevue, WA':         f'Bellevue, WA {_US}',
    'Fargo, ND':            f'Fargo, ND {_US}',
    'Vacaville, CA':        f'Vacaville, CA {_US}',
    'Fairbanks, AK':        f'Fairbanks, AK {_US}',
    'Lake Placid, NY':      f'Lake Placid, NY {_US}',
    'Richmond, VA':         f'Richmond, VA {_US}',
    'Ithaca, NY':           f'Ithaca, NY {_US}',
    'Farmington, CT':       f'Farmington, CT {_US}',
    'Kitty Hawk, NC':       f'Kitty Hawk, NC {_US}',
    'Silver City, NM':      f'Silver City, NM {_US}',
    'Tupelo, MS':           f'Tupelo, MS {_US}',
    'Tulsa, Oklahoma':      f'Tulsa, OK {_US}',
    'Winthrop Harbor, IL':  f'Winthrop Harbor, IL {_US}',
    'Kalamazoo, MI':        f'Kalamazoo, MI {_US}',
    'Durham, NC':           f'Durham, NC {_US}',
    'Houston, TX':          f'Houston, TX {_US}',
    'Wilmette, IL':         f'Wilmette, IL {_US}',
    'Buffalo, NY':          f'Buffalo, NY {_US}',
    'Brookline, MA':        f'Brookline, MA {_US}',
    'Austin, TX':           f'Austin, TX {_US}',
    'Louisville, CO':       f'Louisville, CO {_US}',
    'Boulder, CO':          f'Boulder, CO {_US}',
    'Pasadena, CA':         f'Pasadena, CA {_US}',
    'Chico, CA':            f'Chico, CA {_US}',
    'Westerly, RI':         f'Westerly, RI {_US}',
    'Providence, RI':       f'Providence, RI {_US}',
    'Kansas City, MO':      f'Kansas City, MO {_US}',
    'Fayetteville, Arkansas': f'Fayetteville, AR {_US}',
    'Washington, D.C.':     f'Washington, D.C. {_US}',
    'Columbus, Ohio':       f'Columbus, OH {_US}',
    'Portland, Oregon':     f'Portland, OR {_US}',
    # USA — states only
    'Vermont':              f'Vermont {_US}',
    'Idaho':                f'Idaho {_US}',
    'Utah':                 f'Utah {_US}',
    'Minnesota':            f'Minnesota {_US}',
    'North Carolina':       f'North Carolina {_US}',
    'West Virginia':        f'West Virginia {_US}',
    'Illinois':             f'Illinois {_US}',
    'Virginia':             f'Virginia {_US}',
    'Kentucky':             f'Kentucky {_US}',
    'Tennessee':            f'Tennessee {_US}',
    'Ohio':                 f'Ohio {_US}',
    'Maine':                f'Maine {_US}',
    'Michigan':             f'Michigan {_US}',
    'USA':                  f'USA {_US}',
    # UK & Ireland
    'London':               f'London {_GB}',
    'Abingdon, England':    f'Abingdon {_GB}',
    'South Queensferry':    f'South Queensferry {_GB}',
    'Dublin':               f'Dublin {_IE}',
    'Connemara':            f'Connemara {_IE}',
    'Tullamore, Ireland':   f'Tullamore {_IE}',
    'Kildare':              f'County Kildare {_IE}',
    'County Donegal':       f'County Donegal {_IE}',
    'Ireland':              f'Ireland {_IE}',
    # Europe
    'Amsterdam':            f'Amsterdam {_flag("NL")}',
    'Netherlands':          f'Netherlands {_flag("NL")}',
    'Madrid':               f'Madrid {_flag("ES")}',
    'Catalonia':            f'Catalonia {_flag("ES")}',
    'Spain':                f'Spain {_flag("ES")}',
    'Portugal':             f'Portugal {_flag("PT")}',
    'Vienna':               f'Vienna {_flag("AT")}',
    'Austria':              f'Austria {_flag("AT")}',
    'Budapest':             f'Budapest {_flag("HU")}',
    'Eger, Hungary':        f'Eger {_flag("HU")}',
    'Athens':               f'Athens {_flag("GR")}',
    'Greece':               f'Greece {_flag("GR")}',
    'Zagreb':               f'Zagreb {_flag("HR")}',
    'Croatia':              f'Croatia {_flag("HR")}',
    'Ljubljana, Slovenia':  f'Ljubljana {_flag("SI")}',
    'Slovenia':             f'Slovenia {_flag("SI")}',
    'Bergen, Norway':       f'Bergen {_flag("NO")}',
    'Norway':               f'Norway {_flag("NO")}',
    'Finland':              f'Finland {_flag("FI")}',
    'Reykjavik':            f'Reykjavik {_flag("IS")}',
    'Kyiv':                 f'Kyiv {_flag("UA")}',
    'Ukraine':              f'Ukraine {_flag("UA")}',
    # Asia
    'Bangalore':            f'Bangalore {_flag("IN")}',
    'Hyderabad':            f'Hyderabad {_flag("IN")}',
    'Kerala':               f'Kerala {_flag("IN")}',
    'Mumbai':               f'Mumbai {_flag("IN")}',
    'New Delhi':            f'New Delhi {_flag("IN")}',
    'India':                f'India {_flag("IN")}',
    'Singapore':            f'Singapore {_flag("SG")}',
    'Philippines':          f'Philippines {_flag("PH")}',
    'Manila':               f'Manila {_flag("PH")}',
    'Taguig':               f'Taguig {_flag("PH")}',
    'Thailand':             f'Thailand {_flag("TH")}',
    'Bangkok':              f'Bangkok {_flag("TH")}',
    'Tehran':               f'Tehran {_flag("IR")}',
    'Beirut':               f'Beirut {_flag("LB")}',
    'Kazakhstan':           f'Kazakhstan {_flag("KZ")}',
    'Almaty':               f'Almaty {_flag("KZ")}',
    'Kyrgyzstan':           f'Kyrgyzstan {_flag("KG")}',
    # Africa & Middle East
    'Casablanca':           f'Casablanca {_flag("MA")}',
    'Marrakesh':            f'Marrakesh {_flag("MA")}',
    'Rabat':                f'Rabat {_flag("MA")}',
    'Morocco':              f'Morocco {_flag("MA")}',
    'Egypt':                f'Egypt {_flag("EG")}',
    'Alexandria, Egypt':    f'Alexandria {_flag("EG")}',
    'Addis Ababa':          f'Addis Ababa {_flag("ET")}',
    'Kenya':                f'Kenya {_flag("KE")}',
    # Oceania
    'Auckland':             f'Auckland {_flag("NZ")}',
    'Christchurch':         f'Christchurch {_flag("NZ")}',
    'Hokitika, New Zealand':f'Hokitika {_flag("NZ")}',
    'Thames, New Zealand':  f'Thames {_flag("NZ")}',
    'New Zealand':          f'New Zealand {_flag("NZ")}',
    'Australia':            f'Australia {_flag("AU")}',
    # Latin America
    'Buenos Aires':         f'Buenos Aires {_flag("AR")}',
    'Cordoba, Argentina':   f'Córdoba {_flag("AR")}',
    'Argentina':            f'Argentina {_flag("AR")}',
    'São Paulo':            f'São Paulo {_flag("BR")}',
    'Brazil':               f'Brazil {_flag("BR")}',
    'Colombia':             f'Colombia {_flag("CO")}',
    'Mexico City':          f'Mexico City {_flag("MX")}',
    'Juárez':               f'Ciudad Juárez {_flag("MX")}',
    # Other
    'Antarctica':           f'Antarctica {_flag("AQ")}',
}


def display_location(loc, country):
    """Return a display location string with flag emoji."""
    if loc in DISPLAY_LOC:
        return DISPLAY_LOC[loc]
    # Fallback: append flag for the country if known
    flag = COUNTRY_FLAGS.get(country, '')
    if flag:
        return f'{loc} {flag}'
    return loc


def country_from_location(loc):
    loc_l = loc.lower()
    # Canada FIRST — must precede US checks because ", ca" appears in "ontario, canada"
    if any(x in loc_l for x in ['canada', 'ontario', 'toronto', 'vancouver',
                                  'calgary', 'halifax', 'collingwood', 'windsor, ontario',
                                  'manitoulin', 'georgetown, ontario', 'canadian far north']):
        return 'Canada'
    if any(x in loc_l for x in [
            ', usa', 'usa', ', az', ', ca', ', ny', ', tx', ', wa', ', ma', ', fl', ', il',
            ', nc', ', va', ', md', ', ri', ', nd', ', nh', ', co', ', ut', ', nv', ', ak',
            ', tn', ', or', ', id', ', mn', ', ms', ', mo', ', ct', ', mi', ', oh',
            'new york', 'los angeles', 'chicago', 'seattle', 'miami', 'dallas',
            'houston', 'salt lake', 'nashville', 'austin', 'boulder', 'reno',
            'sacramento', 'kitty hawk', 'orlando', 'las vegas', 'fargo',
            'richmond', 'providence', 'silver city', 'tupelo', 'chico',
            'farmington, ct', 'woburn', 'lakewood', 'vacaville', 'wilmette',
            'ithaca', 'buffalo', 'west virginia', 'winthrop harbor',
            'lake placid', 'mountain view', 'bellevue, wa',
            'minnesota', 'tucson', 'oklahoma', 'fayetteville, ark',
            'michigan', 'georgia', 'alabama', 'indiana', 'iowa',
            'kansas', 'louisiana', 'nebraska', 'new mexico', 'new jersey',
            'connecticut', 'delaware', 'arkansas', 'wyoming', 'montana',
            'south carolina', 'south dakota', 'north dakota', 'hawaii',
            ]):
        return 'United States'
    if 'australia' in loc_l:
        return 'Australia'
    if any(x in loc_l for x in ['new zealand', 'auckland', 'christchurch', 'hokitika', 'thames, new']):
        return 'New Zealand'
    if any(x in loc_l for x in ['uk', 'england', 'london', 'scotland', 'abingdon', 'south queensferry']):
        return 'United Kingdom'
    if any(x in loc_l for x in ['ireland', 'dublin', 'connemara', 'tullamore', 'kildare', 'donegal']):
        return 'Ireland'
    if any(x in loc_l for x in ['india', 'bangalore', 'hyderabad', 'kerala', 'mumbai', 'new delhi']):
        return 'India'
    if any(x in loc_l for x in ['philippines', 'manila', 'taguig', 'baguio']):
        return 'Philippines'
    if any(x in loc_l for x in ['argentina', 'buenos aires', 'córdoba', 'cordoba', 'florencia']):
        return 'Argentina'
    if any(x in loc_l for x in ['netherlands', 'amsterdam']):
        return 'Netherlands'
    if any(x in loc_l for x in ['norway', 'bergen']):
        return 'Norway'
    if 'japan' in loc_l:
        return 'Japan'
    if any(x in loc_l for x in ['thailand', 'bangkok']):
        return 'Thailand'
    if 'singapore' in loc_l:
        return 'Singapore'
    if any(x in loc_l for x in ['morocco', 'marrakesh', 'casablanca', 'rabat']):
        return 'Morocco'
    if any(x in loc_l for x in ['egypt', 'alexandria', 'cairo']):
        return 'Egypt'
    if any(x in loc_l for x in ['turkey', 'istanbul']):
        return 'Turkey'
    if 'israel' in loc_l:
        return 'Israel'
    if any(x in loc_l for x in ['lebanon', 'beirut']):
        return 'Lebanon'
    if any(x in loc_l for x in ['iran', 'tehran']):
        return 'Iran'
    if any(x in loc_l for x in ['austria', 'vienna']):
        return 'Austria'
    if any(x in loc_l for x in ['hungary', 'budapest', 'eger']):
        return 'Hungary'
    if 'finland' in loc_l:
        return 'Finland'
    if 'portugal' in loc_l:
        return 'Portugal'
    if any(x in loc_l for x in ['spain', 'madrid', 'catalonia', 'barcelona']):
        return 'Spain'
    if any(x in loc_l for x in ['croatia', 'zagreb']):
        return 'Croatia'
    if any(x in loc_l for x in ['greece', 'athens']):
        return 'Greece'
    if any(x in loc_l for x in ['slovenia', 'ljubljana']):
        return 'Slovenia'
    if any(x in loc_l for x in ['brazil', 'são paulo', 'sao paulo']):
        return 'Brazil'
    if 'colombia' in loc_l:
        return 'Colombia'
    if any(x in loc_l for x in ['mexico', 'juárez', 'mexico city']):
        return 'Mexico'
    if any(x in loc_l for x in ['ukraine', 'kyiv']):
        return 'Ukraine'
    if 'kyrgyzstan' in loc_l:
        return 'Kyrgyzstan'
    if any(x in loc_l for x in ['kazakhstan', 'almaty']):
        return 'Kazakhstan'
    if any(x in loc_l for x in ['ethiopia', 'addis ababa']):
        return 'Ethiopia'
    if 'south africa' in loc_l:
        return 'South Africa'
    if 'kenya' in loc_l:
        return 'Kenya'
    if any(x in loc_l for x in ['iceland', 'reykjavik']):
        return 'Iceland'
    if 'antarctica' in loc_l:
        return 'Antarctica'
    return 'Unknown'


def occ_category(occ):
    o = occ.lower()
    if any(x in o for x in ['doctor', 'nurse', 'icu', 'medical', 'hospital', 'therapist',
                              'health', 'pharmacist', 'dentist', 'hygienist', 'acupunctur',
                              'sober', 'poison', 'urologist', 'surgeon', 'patient',
                              'paramedic', 'lactation', 'colonoscopy', 'standardized',
                              'dermatologist']):
        return 'Healthcare'
    if any(x in o for x in ['engineer', 'tech', 'robot', 'software', 'cyber', 'data',
                              'ai', 'nasa', 'astronaut', 'research engineer']):
        return 'Technology'
    if any(x in o for x in ['lawyer', 'attorney', 'law', 'police', 'detective', 'fbi',
                              'military', 'army', 'government', 'rcmp', 'patrol',
                              'special forces', 'crime scene', 'fight promo',
                              'immigration', 'emigr', 'corrections']):
        return 'Law & Government'
    if any(x in o for x in ['artist', 'musician', 'music', 'band', 'film', 'writer',
                              'journalist', 'podcast', 'media', 'radio', 'tv', 'television',
                              'design', 'animator', 'tailor', 'weaver', 'frame', 'sculpt',
                              'tattoo', 'preservationist', 'director', 'bicycle', 'custom',
                              'illustrat', 'composer', 'photog', 'game design',
                              'video creator', 'content creator']):
        return 'Arts & Media'
    if any(x in o for x in ['teacher', 'professor', 'historian', 'researcher',
                              'archaeolog', 'paleontolog', 'geography', 'climate',
                              'university', 'school', 'education', 'study', 'academic',
                              'caltech', 'phd', 'grad', 'lecturer']):
        return 'Education'
    if any(x in o for x in ['chef', 'food', 'restaurant', 'cook', 'juice', 'drink',
                              'coffee', 'sauna', 'sommelier', 'candle', 'perfume', 'candy',
                              'hospitality', 'hotel', 'tourist', 'tour guide', 'travel',
                              'wedding', 'safari']):
        return 'Food & Hospitality'
    if any(x in o for x in ['farmer', 'farm', 'birch', 'agricultural', 'forest', 'sap',
                              'crop', 'dairy']):
        return 'Agriculture'
    if any(x in o for x in ['athlete', 'sport', 'basketball', 'baseball', 'soccer',
                              'hockey', 'ski', 'tennis', 'boxing', 'wrestling', 'luchador',
                              'clown', 'circus', 'roller derby', 'skydiv', 'badminton',
                              'bungee']):
        return 'Sports & Athletics'
    if any(x in o for x in ['entrepreneur', 'business', 'startup', 'owner', 'ceo',
                              'founder', 'sales', 'realtor', 'retail', 'shop', 'store',
                              'dvd', 'gravel', 'diamond', 'model', 'fashion']):
        return 'Business & Entrepreneurship'
    if any(x in o for x in ['transport', 'driver', 'pilot', 'bus', 'truck', '911',
                              'emergency', 'operator']):
        return 'Transportation'
    if any(x in o for x in ['science', 'biolog', 'chemist', 'physicist', 'zoolog',
                              'herpetolog', 'ecolog', 'taxidermy', 'conservation', 'bear',
                              'ranger', 'wildlife', 'zookeeper']):
        return 'Science'
    if any(x in o for x in ['entertain', 'comedian', 'actor', 'perform', 'standup',
                              'improv', 'magic', 'illusionist', 'game master',
                              'escape room', 'dungeon master', 'tarot', 'astrologer',
                              'yoga', 'shaman']):
        return 'Entertainment'
    return 'Other'
