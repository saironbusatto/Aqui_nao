# Project Instructions

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.10+ |
| Web Framework | Flask | 3.x |
| Templates | Jinja2 (via Flask) | - |
| Frontend | Bootstrap 5.3 + Vanilla JS | - |
| Data Models | dataclasses (frozen) | stdlib |
| Testing | pytest + pytest-cov | - |
| Data Sources | soccerdata (FBref), requests+bs4 (Transfermarkt), football-data.org API | - |
| Charts | matplotlib (Agg backend) | - |

## Project Purpose

Sistema de comparação de carreiras de jogadores de futebol. Compara gols, assistências, lesões, tempo de jogo, e projeções entre jogadores. Interface web em português com dados de FBref, Transfermarkt e Football-Data.org.

## Code Style

### Python
- Use `from __future__ import annotations` in all modules
- All data models are `@dataclass(frozen=True)` — immutable
- Type hints required on all public functions and methods
- Properties for computed fields on dataclasses (e.g., `total_goals`)
- snake_case for functions/variables, PascalCase for classes
- Docstrings: concise, only on public APIs when behavior isn't obvious
- No unnecessary comments — code should be self-documenting

### HTML/Templates
- Portuguese (pt-BR) for all user-facing text
- Dark theme (#050509) with neon green (#00FF87) and cyan (#60EFFF) accents
- Fonts: Bebas Neue (headings), Space Grotesk (body)
- Chart.js for data visualization (bar, line, radar)
- Animations: fadeInUp, slideIn, vsPulse, neonGlow, orbFloat, borderPulse
- Particles canvas on home page
- CSRF protection on all POST forms
- No Bootstrap — pure CSS with custom properties

### Naming
- Files: snake_case (`comparison_engine.py`)
- Routes: kebab-case not applicable (Flask uses snake_case view functions)
- CSS: simple selectors, avoid nesting

## Architecture

```
src/
├── app.py                    # Flask app factory + routes + player DB
├── collectors/               # External data source adapters
│   ├── fbref_collector.py           # soccerdata/FBref wrapper
│   ├── transfermarkt_collector.py   # requests+bs4 scraper
│   ├── transfermarkt_scraper.py     # Full scrape: search + profile + stats + injuries
│   └── footballdata_collector.py    # Football-Data.org API
├── models/                   # Frozen dataclasses (domain)
│   ├── player.py             # Player, SeasonStats, Injury
│   └── comparison.py         # PlayerComparison + sub-comparisons
├── services/                 # Business logic
│   ├── comparison_engine.py  # Core comparison logic
│   ├── projection.py         # Goal projection calculations
│   └── report.py             # Text report + chart generation
├── utils/                    # Shared utilities
│   ├── cache.py              # JSON file cache with TTL
│   └── helpers.py            # Date/format helpers
├── templates/                # Jinja2 HTML templates
│   ├── index.html            # Home/search page
│   └── compare.html          # Comparison results page
└── static/css/               # Custom styles
```

## Data Flow

```
User → index.html (search via /api/search/<name>)
     → POST /compare (player1 + player2)
     → search_player() → _SEARCH_DB (hardcoded) → transfermarkt_scraper (fallback)
     → compare_players(p1, p2) → PlayerComparison
     → generate_report(comparison) → text report
     → compare.html (renders stats, charts, projections)
```

## Key Patterns

### Player Search Resolution
`search_player()` in `app.py` follows this chain:
1. Direct lookup in `_SEARCH_DB` (hardcoded players)
2. Alias resolution via `_ALIASES` dict
3. Substring matching in `_SEARCH_DB`
4. Transfermarkt scraper as external fallback

### Data Models
- `Player` → `SeasonStats` (tuple) + `Injury` (tuple)
- `PlayerComparison` aggregates: `AgeComparison`, `TeamComparison`, `GoalProjection`, `InjuryComparison`, `PlayingTimeComparison`

## Testing

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run with coverage
python3 -m pytest tests/ --cov=src --cov-report=term-missing

# Run specific test class
python3 -m pytest tests/test_services.py::TestComparePlayers -v
```

### Test Conventions
- Markers: `@pytest.mark.unit`, `@pytest.mark.integration`
- Fixtures in `conftest.py` and top of each test file
- Mock external APIs (soccerdata, requests) — never hit network
- Test classes grouped by feature (TestComparePlayers, TestProjection, etc.)
- Use `tmp_path` fixture for chart file tests

## Build & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run dev server
cd src && python3 -m flask --app app run

# Access
# http://localhost:5000
```

## Security Notes

- CSRF token generated per-session and validated on POST
- `app.secret_key` falls back to hardcoded dev key (set `SECRET_KEY` env in prod)
- Scrapers use timeout=30 on all requests
- No user data stored — all in-memory

## Conventions to Follow

1. **Don't add comments** unless explicitly asked
2. **Frozen dataclasses** for all domain models
3. **Properties** for computed fields, not methods
4. **Tuple** for collections in dataclasses (not list)
5. **Error handling**: raise ValueError for domain errors, ConnectionError for network
6. **Imports**: stdlib → third-party → local, separated by blank lines
7. **No type: ignore** — fix the type properly or use proper casts

## Anti-Patterns to Avoid

- Don't use mutable defaults in dataclasses (use `field(default_factory=...)`)
- Don't add features beyond what's requested
- Don't refactor working code unless asked
- Don't add comments explaining obvious code
- Don't create abstractions for 2-3 similar lines
