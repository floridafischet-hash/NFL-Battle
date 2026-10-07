"""The 32 NFL teams (master data).

Logos: by default the official team logos are referenced from ESPN's logo CDN (mapping from the
nflverse team table, github.com/nflverse/nflfastR-data, ``team_logo_espn``). The image files are not
stored in this repository; the browser loads them directly. If a logo cannot be loaded the frontend
falls back to the neutral crest in frontend/public/logos/<ABBR>.svg. Every logo can be replaced in
the admin area (upload or URL)."""

# (abbreviation, city, short_name, conference, division, primary, secondary)
NFL_TEAMS: list[tuple[str, str, str, str, str, str, str]] = [
    ("BUF", "Buffalo", "Bills", "AFC", "East", "#00338D", "#C60C30"),
    ("MIA", "Miami", "Dolphins", "AFC", "East", "#008E97", "#FC4C02"),
    ("NE", "New England", "Patriots", "AFC", "East", "#002244", "#C60C30"),
    ("NYJ", "New York", "Jets", "AFC", "East", "#125740", "#FFFFFF"),
    ("BAL", "Baltimore", "Ravens", "AFC", "North", "#241773", "#9E7C0C"),
    ("CIN", "Cincinnati", "Bengals", "AFC", "North", "#FB4F14", "#000000"),
    ("CLE", "Cleveland", "Browns", "AFC", "North", "#311D00", "#FF3C00"),
    ("PIT", "Pittsburgh", "Steelers", "AFC", "North", "#FFB612", "#101820"),
    ("HOU", "Houston", "Texans", "AFC", "South", "#03202F", "#A71930"),
    ("IND", "Indianapolis", "Colts", "AFC", "South", "#002C5F", "#A2AAAD"),
    ("JAX", "Jacksonville", "Jaguars", "AFC", "South", "#006778", "#D7A22A"),
    ("TEN", "Tennessee", "Titans", "AFC", "South", "#0C2340", "#4B92DB"),
    ("DEN", "Denver", "Broncos", "AFC", "West", "#FB4F14", "#002244"),
    ("KC", "Kansas City", "Chiefs", "AFC", "West", "#E31837", "#FFB81C"),
    ("LV", "Las Vegas", "Raiders", "AFC", "West", "#000000", "#A5ACAF"),
    ("LAC", "Los Angeles", "Chargers", "AFC", "West", "#0080C6", "#FFC20E"),
    ("DAL", "Dallas", "Cowboys", "NFC", "East", "#003594", "#869397"),
    ("NYG", "New York", "Giants", "NFC", "East", "#0B2265", "#A71930"),
    ("PHI", "Philadelphia", "Eagles", "NFC", "East", "#004C54", "#A5ACAF"),
    ("WAS", "Washington", "Commanders", "NFC", "East", "#5A1414", "#FFB612"),
    ("CHI", "Chicago", "Bears", "NFC", "North", "#0B162A", "#C83803"),
    ("DET", "Detroit", "Lions", "NFC", "North", "#0076B6", "#B0B7BC"),
    ("GB", "Green Bay", "Packers", "NFC", "North", "#203731", "#FFB612"),
    ("MIN", "Minnesota", "Vikings", "NFC", "North", "#4F2683", "#FFC62F"),
    ("ATL", "Atlanta", "Falcons", "NFC", "South", "#A71930", "#000000"),
    ("CAR", "Carolina", "Panthers", "NFC", "South", "#0085CA", "#101820"),
    ("NO", "New Orleans", "Saints", "NFC", "South", "#D3BC8D", "#101820"),
    ("TB", "Tampa Bay", "Buccaneers", "NFC", "South", "#D50A0A", "#34302B"),
    ("ARI", "Arizona", "Cardinals", "NFC", "West", "#97233F", "#000000"),
    ("LAR", "Los Angeles", "Rams", "NFC", "West", "#003594", "#FFA300"),
    ("SF", "San Francisco", "49ers", "NFC", "West", "#AA0000", "#B3995D"),
    ("SEA", "Seattle", "Seahawks", "NFC", "West", "#002244", "#69BE28"),
]


OFFICIAL_LOGOS: dict[str, str] = {
    "BUF": "https://a.espncdn.com/i/teamlogos/nfl/500/buf.png",
    "MIA": "https://a.espncdn.com/i/teamlogos/nfl/500/mia.png",
    "NE": "https://a.espncdn.com/i/teamlogos/nfl/500/ne.png",
    "NYJ": "https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png",
    "BAL": "https://a.espncdn.com/i/teamlogos/nfl/500/bal.png",
    "CIN": "https://a.espncdn.com/i/teamlogos/nfl/500/cin.png",
    "CLE": "https://a.espncdn.com/i/teamlogos/nfl/500/cle.png",
    "PIT": "https://a.espncdn.com/i/teamlogos/nfl/500/pit.png",
    "HOU": "https://a.espncdn.com/i/teamlogos/nfl/500/hou.png",
    "IND": "https://a.espncdn.com/i/teamlogos/nfl/500/ind.png",
    "JAX": "https://a.espncdn.com/i/teamlogos/nfl/500/jax.png",
    "TEN": "https://a.espncdn.com/i/teamlogos/nfl/500/ten.png",
    "DEN": "https://a.espncdn.com/i/teamlogos/nfl/500/den.png",
    "KC": "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png",
    "LV": "https://a.espncdn.com/i/teamlogos/nfl/500/lv.png",
    "LAC": "https://a.espncdn.com/i/teamlogos/nfl/500/lac.png",
    "DAL": "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png",
    "NYG": "https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png",
    "PHI": "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png",
    "WAS": "https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png",
    "CHI": "https://a.espncdn.com/i/teamlogos/nfl/500/chi.png",
    "DET": "https://a.espncdn.com/i/teamlogos/nfl/500/det.png",
    "GB": "https://a.espncdn.com/i/teamlogos/nfl/500/gb.png",
    "MIN": "https://a.espncdn.com/i/teamlogos/nfl/500/min.png",
    "ATL": "https://a.espncdn.com/i/teamlogos/nfl/500/atl.png",
    "CAR": "https://a.espncdn.com/i/teamlogos/nfl/500-dark/car.png",
    "NO": "https://a.espncdn.com/i/teamlogos/nfl/500/no.png",
    "TB": "https://a.espncdn.com/i/teamlogos/nfl/500/tb.png",
    "ARI": "https://a.espncdn.com/i/teamlogos/nfl/500/ari.png",
    "LAR": "https://a.espncdn.com/i/teamlogos/nfl/500/lar.png",
    "SF": "https://a.espncdn.com/i/teamlogos/nfl/500/sf.png",
    "SEA": "https://a.espncdn.com/i/teamlogos/nfl/500/sea.png",
}


def neutral_logo_url(abbreviation: str) -> str:
    return f"/logos/{abbreviation}.svg"


def default_logo_url(abbreviation: str) -> str:
    return OFFICIAL_LOGOS.get(abbreviation, neutral_logo_url(abbreviation))
