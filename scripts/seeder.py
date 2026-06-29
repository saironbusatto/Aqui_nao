#!/usr/bin/env python3
"""
Smart seeder: busca listas de jogadores no Transfermarkt e atualiza o Postgres
com base em TTL inteligente por faixa etária e valor de mercado.

CLI:
  python3 scripts/seeder.py                    → todas as fontes + fase 2
  python3 scripts/seeder.py --source=premier_top50 --phase1  → só lista de uma fonte
  python3 scripts/seeder.py --phase2            → só detalhes pendentes

Fontes configuradas (12):
  global_top500, brazil_top100, champions_top50, premier_top50,
  bundesliga_top50, laliga_top50, seriea_top50, ligue1_top50,
  brasileirao_top50, saudileague_top50, portugal_top50, eredivisie_top50

Logs (fora do projeto para não serem limpos pelo rsync):
  - /var/log/aquinao/seeder.log          → log histórico de todas as execuções
  - /var/log/aquinao/runs/YYYYMMDD_HHmm.log → log isolado de cada execução
  - /var/log/aquinao/seeder_state.json   → estado persistido (última busca por fonte)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Image download
# ---------------------------------------------------------------------------

_IMAGE_DIR = "src/static/images/players"


def _download_profile_image(image_url: str, tm_url: str) -> str | None:
    if not image_url or "default" in image_url:
        return None
    m = re.search(r"/spieler/(\d+)", tm_url)
    if not m:
        return None
    tm_id = m.group(1)
    path = image_url.split("?")[0].rstrip("/")
    _, ext = os.path.splitext(path)
    ext = ext or ".jpg"
    filename = f"{tm_id}{ext}"
    os.makedirs(_IMAGE_DIR, exist_ok=True)
    local = os.path.join(_IMAGE_DIR, filename)
    if os.path.exists(local):
        return f"/static/images/players/{filename}"
    try:
        r = requests.get(image_url, timeout=15)
        r.raise_for_status()
        with open(local, "wb") as f:
            f.write(r.content)
        logger.info("Imagem salva: %s (%d bytes)", filename, len(r.content))
        return f"/static/images/players/{filename}"
    except Exception as e:
        logger.warning("Falha ao baixar imagem %s: %s", image_url, e)
        return None

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://aquinao:AquiNao_2026_Strong!@localhost:5433/aqui_nao",
)

DATA_DIR    = Path("/home/ubuntu/aqui-nao/data")
LOG_DIR     = Path("/var/log/aquinao")
RUNS_DIR    = LOG_DIR / "runs"
STATE_FILE  = LOG_DIR / "seeder_state.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

RUN_ID      = datetime.now().strftime("%Y%m%d_%H%M")
RUN_LOG     = RUNS_DIR / f"{RUN_ID}.log"

# Configura dois handlers: log histórico + log isolado deste run
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

_file_handler = logging.FileHandler(LOG_DIR / "seeder.log")
_file_handler.setFormatter(_fmt)

_run_handler = logging.FileHandler(RUN_LOG)
_run_handler.setFormatter(_fmt)

_stream_handler = logging.StreamHandler()
_stream_handler.setFormatter(_fmt)

logger = logging.getLogger("seeder")
logger.setLevel(logging.DEBUG)
logger.addHandler(_file_handler)
logger.addHandler(_run_handler)
logger.addHandler(_stream_handler)

TM_BASE        = "https://www.transfermarkt.com"
SCRAPE_DELAY   = 5          # segundos entre requests individuais
LIST_PAGE_SIZE = 25         # jogadores por página no Transfermarkt
LIST_REFRESH_DAYS = 7       # Phase 1: só rebusca lista se passou mais de N dias

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# ---------------------------------------------------------------------------
# Fontes de dados
# Para adicionar Champions League: descomente o bloco correspondente.
# ---------------------------------------------------------------------------
SOURCES: list[dict] = [
    {
        "name": "global_top500",
        "url": f"{TM_BASE}/spieler-statistik/wertvollstespieler/marktwertetop",
        "params": {},
        "pages": 20,
        "rank_offset": 0,
    },
    {
        "name": "brazil_top100",
        "url": f"{TM_BASE}/spieler-statistik/wertvollstespieler/marktwertetop",
        "params": {"land_id": 26},
        "pages": 4,
        "rank_offset": 10_000,
    },
    {
        "name": "champions_top50",
        "url": f"{TM_BASE}/spieler-statistik/wertvollstespieler/marktwertetop",
        "params": {"wettbewerb_id": "CL"},
        "pages": 2,
        "rank_offset": 20_000,
    },
    {
        "name": "premier_top50",
        "url": f"{TM_BASE}/spieler-statistik/wertvollstespieler/marktwertetop",
        "params": {"wettbewerb_id": "GB1"},
        "pages": 2,
        "rank_offset": 30_000,
    },
    {
        "name": "bundesliga_top50",
        "url": f"{TM_BASE}/spieler-statistik/wertvollstespieler/marktwertetop",
        "params": {"wettbewerb_id": "L1"},
        "pages": 2,
        "rank_offset": 40_000,
    },
    {
        "name": "laliga_top50",
        "url": f"{TM_BASE}/spieler-statistik/wertvollstespieler/marktwertetop",
        "params": {"wettbewerb_id": "ES1"},
        "pages": 2,
        "rank_offset": 50_000,
    },
    {
        "name": "seriea_top50",
        "url": f"{TM_BASE}/spieler-statistik/wertvollstespieler/marktwertetop",
        "params": {"wettbewerb_id": "IT1"},
        "pages": 2,
        "rank_offset": 60_000,
    },
    {
        "name": "ligue1_top50",
        "url": f"{TM_BASE}/spieler-statistik/wertvollstespieler/marktwertetop",
        "params": {"wettbewerb_id": "FR1"},
        "pages": 2,
        "rank_offset": 70_000,
    },
    {
        "name": "brasileirao_top50",
        "url": f"{TM_BASE}/spieler-statistik/wertvollstespieler/marktwertetop",
        "params": {"wettbewerb_id": "BRA1"},
        "pages": 2,
        "rank_offset": 80_000,
    },
    {
        "name": "saudileague_top50",
        "url": f"{TM_BASE}/spieler-statistik/wertvollstespieler/marktwertetop",
        "params": {"wettbewerb_id": "SA1"},
        "pages": 2,
        "rank_offset": 90_000,
    },
    {
        "name": "portugal_top50",
        "url": f"{TM_BASE}/spieler-statistik/wertvollstespieler/marktwertetop",
        "params": {"wettbewerb_id": "PO1"},
        "pages": 2,
        "rank_offset": 100_000,
    },
    {
        "name": "eredivisie_top50",
        "url": f"{TM_BASE}/spieler-statistik/wertvollstespieler/marktwertetop",
        "params": {"wettbewerb_id": "NL1"},
        "pages": 2,
        "rank_offset": 110_000,
    },
]

# ---------------------------------------------------------------------------
# Estado persistido (Phase 1 — controle de rebusca de lista)
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def _source_needs_list_refresh(state: dict, source_name: str) -> bool:
    """Retorna True se a lista desta fonte nunca foi buscada ou passou LIST_REFRESH_DAYS."""
    last_raw = state.get("list_fetch", {}).get(source_name)
    if not last_raw:
        return True
    try:
        last = datetime.fromisoformat(last_raw)
        return (datetime.now(timezone.utc) - last).days >= LIST_REFRESH_DAYS
    except Exception:
        return True


def _mark_list_fetched(state: dict, source_name: str) -> None:
    state.setdefault("list_fetch", {})[source_name] = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# TTL por faixa etária e valor de mercado
# ---------------------------------------------------------------------------

def _is_transfer_window() -> bool:
    return datetime.now().month in (1, 7)


REFRESH_BACKOFF_CAP_DAYS = 90       # teto do backoff p/ jogador estável
REFRESH_STREAK_CAP = 5              # 2^5 = 32x no máximo


def compute_refresh_days(
    age: int, market_value_rank: int, is_retired: bool, stable_streak: int = 0
) -> int:
    """Intervalo de atualização (dias) por idade, relevância e estabilidade.

    `stable_streak` = nº de raspagens seguidas SEM mudança. Quanto mais
    estável o jogador, mais o intervalo afrouxa (backoff ×2 por streak,
    teto REFRESH_BACKOFF_CAP_DAYS). Qualquer mudança zera o streak e ele
    volta ao intervalo-base. Top 50 por valor nunca afrouxa além de semanal.
    """
    if is_retired or age >= 43:
        return 36_500               # aposentado: seed único

    multiplier = 0.5 if _is_transfer_window() else 1.0   # janela = dobrar frequência

    if age >= 40:
        days = 30
    elif age >= 36:
        days = 15
    elif age >= 30:
        days = 7
    else:
        days = 3

    base = max(int(days * multiplier), 1)
    backed_off = base * (2 ** min(stable_streak, REFRESH_STREAK_CAP))
    days_out = min(backed_off, REFRESH_BACKOFF_CAP_DAYS)

    if market_value_rank <= 50:     # top 50 por valor: sempre no máximo semanal
        days_out = min(days_out, 7)

    return max(days_out, 1)


# ---------------------------------------------------------------------------
# Normalização de data → YYYY-MM-DD
# ---------------------------------------------------------------------------

def _normalize_date(raw: str) -> str | None:
    """Converte qualquer formato de data para YYYY-MM-DD, ou retorna None."""
    if not raw:
        return None
    raw = raw.strip()
    # DD/MM/YYYY ou DD.MM.YYYY
    m = re.match(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    # YYYY-MM-DD (já correto)
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return raw
    # "Jul 13, 2007" / "13 Jul 2007"
    for fmt in ("%b %d, %Y", "%d %b %Y", "%B %d, %Y", "%d %B %Y"):
        try:
            from datetime import datetime as _dt
            return _dt.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# Hash para detecção de mudança real nos dados
# ---------------------------------------------------------------------------

def compute_hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _get_soup(
    session: requests.Session, url: str, params: dict | None = None
) -> BeautifulSoup:
    resp = session.get(url, params=params or {}, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


# ---------------------------------------------------------------------------
# Phase 1 — buscar lista de jogadores por fonte
# ---------------------------------------------------------------------------

def fetch_player_list_page(
    session: requests.Session, url: str, params: dict, page: int
) -> list[dict]:
    """Retorna lista básica de jogadores de uma página de ranking do Transfermarkt."""
    try:
        soup = _get_soup(session, url, {**params, "page": page})
    except Exception as exc:
        logger.warning("[phase1] Falha na página %d (%s): %s", page, url, exc)
        return []

    table = soup.select_one("table.items")
    if not table:
        logger.debug("[phase1] Tabela ausente na página %d", page)
        return []

    players = []
    for row in table.select("tbody tr.odd, tbody tr.even"):
        name_tag = row.select_one("td.hauptlink a")
        if not name_tag:
            continue

        name = name_tag.get_text(strip=True)
        href = name_tag.get("href", "")
        tm_url = f"{TM_BASE}{href}" if href.startswith("/") else href

        cells = row.find_all("td")

        age = 0
        for cell in cells:
            text = cell.get_text(strip=True)
            if text.isdigit() and 15 <= int(text) <= 50:
                age = int(text)
                break

        nat_img = row.select_one("img.flaggenrahmen")
        nationality = nat_img.get("title", "") if nat_img else ""

        club_tag = row.select_one("td.zentriert.no-border-links a")
        club = club_tag.get_text(strip=True) if club_tag else ""

        mv_tag = row.select_one("td.rechts.hauptlink a")
        market_value = mv_tag.get_text(strip=True) if mv_tag else ""

        players.append({
            "name": name,
            "tm_url": tm_url,
            "age": age,
            "nationality": nationality,
            "club": club,
            "market_value": market_value,
        })

    return players


# ---------------------------------------------------------------------------
# Phase 2 — raspar perfil completo de um jogador
# ---------------------------------------------------------------------------

def _extract_profile(soup: BeautifulSoup) -> dict:
    data: dict = {}

    h1 = soup.select_one("h1.data-header__headline-wrapper")
    if h1:
        strong = h1.select_one("strong")
        data["full_name"] = (strong or h1).get_text(strip=True)

    for label_el, value_el in zip(
        soup.select(".info-table__content--regular"),
        soup.select(".info-table__content--bold"),
    ):
        label = label_el.get_text(strip=True).lower()
        value = value_el.get_text(" ", strip=True)

        if "date of birth" in label or "geboren" in label:
            m = re.search(r"(\w[^(]+\d{4})", value)
            if m:
                data["date_of_birth"] = _normalize_date(m.group(1).strip())
        elif "citizenship" in label or "nationality" in label or "staatsbürger" in label:
            data["nationality"] = value.split()[0] if value else ""
        elif "position" in label:
            data["position"] = value.split(" - ")[-1].strip() if " - " in value else value
        elif "current club" in label or "aktueller verein" in label:
            data["current_team"] = value
        elif "outfitter" in label or "ausrüster" in label:
            data["sponsors"] = value

    mv_el = soup.select_one(".tm-market-value-desenvolvimento__market-value")
    if not mv_el:
        # tenta pegar só o valor numérico via data-header
        mv_el = soup.select_one(".data-header__market-value-wrapper")
    if mv_el:
        # extrai só a parte do valor: "€200.00m" ignorando "Last update: ..."
        raw_mv = mv_el.get_text(" ", strip=True)
        mv_match = re.search(r"[€£$][\d,.]+[mk]?", raw_mv, re.I)
        data["market_value"] = mv_match.group(0) if mv_match else raw_mv.split("Last")[0].strip()

    # aposentado: só marca se encontrar o badge/bloco específico de fim de carreira
    data["is_retired"] = bool(
        soup.select_one(".data-header__badge--retired")
        or soup.find("span", string=re.compile(r"karriereende|career end", re.I))
    )
    # lesionado: só marca se houver banner ativo de lesão (não a página de histórico)
    data["is_injured"] = bool(
        soup.select_one(".verletzungsbox, .injury-box, [class='verletzung']")
    )

    # Só o container social DO JOGADOR. Varrer a página toda pegava os
    # links do rodapé do Transfermarkt (ex: twitter.com/TMuk_news).
    social: dict[str, str] = {}
    for a in soup.select(".social-media-toolbar__icons a[href]"):
        href = a["href"]
        if "transfermarkt" in href:
            continue
        handle = href.rstrip("/").split("/")[-1]
        if not handle or handle == "home":
            continue
        if "instagram.com/" in href:
            social["instagram"] = handle
        elif "x.com/" in href or "twitter.com/" in href:
            social["twitter"] = handle
        elif "facebook.com/" in href:
            social["facebook"] = handle
    if social:
        data["social_media"] = social

    img = soup.select_one("img.data-header__profile-image")
    if img:
        src = img.get("src", "")
        if src and "default" not in src:
            data["profile_image_url"] = src

    return data


_TMAPI_BASE = "https://tmapi.transfermarkt.technology"
_TMAPI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.transfermarkt.com/",
}


def _fetch_club_names(club_ids: set[str]) -> dict[str, str]:
    if not club_ids:
        return {}
    ids_param = "&".join(f"ids[]={i}" for i in club_ids)
    try:
        r = requests.get(f"{_TMAPI_BASE}/clubs?{ids_param}", headers=_TMAPI_HEADERS, timeout=15)
        r.raise_for_status()
        clubs = r.json().get("data", [])
        return {str(c["id"]): c["name"] for c in clubs if c.get("id") and c.get("name")}
    except Exception as exc:
        logger.debug("[phase2] clube names falhou: %s", exc)
        return {}


def _extract_seasons(session: requests.Session, profile_url: str) -> list[dict]:
    m_id = re.search(r"/spieler/(\d+)", profile_url)
    if not m_id:
        logger.debug("[phase2] não encontrou ID do jogador em: %s", profile_url)
        return []

    player_id = m_id.group(1)
    api_url = f"{_TMAPI_BASE}/player/{player_id}/performance-game"

    try:
        r = requests.get(api_url, headers=_TMAPI_HEADERS, timeout=20)
        r.raise_for_status()
        performances = r.json().get("data", {}).get("performance", [])
    except Exception as exc:
        logger.debug("[phase2] performance-game falhou (id=%s): %s", player_id, exc)
        return []

    from collections import defaultdict

    by_key: dict[tuple, dict] = defaultdict(lambda: {"appearances": 0, "goals": 0, "assists": 0, "club_id": None, "season": ""})

    for perf in performances:
        # API pode retornar chaves com valor null; `or {}` cobre isso
        # (get(k, {}) só usa default quando a chave falta, não quando é null)
        gi = perf.get("gameInformation") or {}
        stats = perf.get("statistics") or {}
        gen = stats.get("generalStatistics") or {}
        goal = stats.get("goalStatistics") or {}

        if gen.get("participationState") != "played":
            continue

        season = gi.get("season") or {}
        season_name = season.get("nonCyclicalName") or season.get("display", "?")
        club_id = str(gen.get("primaryClubId") or "")
        key = (season_name, club_id)

        by_key[key]["appearances"] += 1
        goals = goal.get("goalsScoredTotalOfficial") if goal.get("goalsScoredTotalOfficial") is not None else goal.get("goalsScoredTotal", 0)
        assists = goal.get("assistsOfficial") if goal.get("assistsOfficial") is not None else goal.get("assists", 0)
        by_key[key]["goals"] += goals or 0
        by_key[key]["assists"] += assists or 0
        by_key[key]["club_id"] = club_id
        by_key[key]["season"] = season_name

    if not by_key:
        logger.debug("[phase2] performance-game sem jogos 'played' (id=%s)", player_id)
        return []

    all_club_ids = {v["club_id"] for v in by_key.values() if v["club_id"]}
    club_names = _fetch_club_names(all_club_ids)

    seasons = [
        {
            "season": v["season"],
            "team": club_names.get(v["club_id"], v["club_id"]),
            "appearances": v["appearances"],
            "goals": v["goals"],
            "assists": v["assists"],
        }
        for v in by_key.values()
    ]

    logger.debug("[phase2] performance-game: %d temporadas via tmapi (id=%s)", len(seasons), player_id)
    return seasons


def _extract_injuries(session: requests.Session, profile_url: str) -> list[dict]:
    injury_url = re.sub(r"/profil/", "/verletzungen/", profile_url)
    if "/verletzungen/" not in injury_url:
        return []
    try:
        soup = _get_soup(session, injury_url)
    except Exception as exc:
        logger.debug("[phase2] lesões falhou (%s): %s", injury_url, exc)
        return []

    injuries = []
    for row in soup.select("table.items tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 5:
            continue
        season = cells[0].get_text(strip=True)
        injury_type = cells[1].get_text(strip=True)
        if not season or not injury_type:
            continue

        def _int(idx: int) -> int:
            try:
                return int(re.sub(r"\D", "", cells[idx].get_text()))
            except (ValueError, IndexError):
                return 0

        injuries.append({
            "season": season,
            "injury_type": injury_type,
            "date_from": cells[2].get_text(strip=True) if len(cells) > 2 else "",
            "date_until": cells[3].get_text(strip=True) if len(cells) > 3 else "",
            "days_missed": _int(4),
            "games_missed": _int(5),
        })
    return injuries


def scrape_full_player(session: requests.Session, tm_url: str) -> dict | None:
    profile_url = re.sub(r"/(leistungsdaten|verletzungen|transfers)/", "/profil/", tm_url)
    profile_url = re.sub(r"\?.*", "", profile_url)

    try:
        soup = _get_soup(session, profile_url)
    except Exception as exc:
        logger.warning("[phase2] perfil falhou (%s): %s", profile_url, exc)
        return None

    profile = _extract_profile(soup)
    if not profile:
        logger.warning("[phase2] perfil vazio: %s", profile_url)
        return None

    time.sleep(SCRAPE_DELAY)
    seasons = _extract_seasons(session, profile_url)
    logger.debug("[phase2]   %d temporadas encontradas", len(seasons))

    time.sleep(SCRAPE_DELAY)
    injuries = _extract_injuries(session, profile_url)
    logger.debug("[phase2]   %d lesões encontradas", len(injuries))

    return {**profile, "seasons": seasons, "injuries": injuries, "tm_url": profile_url}


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------

def _get_conn() -> psycopg2.extensions.connection:
    return psycopg2.connect(DATABASE_URL, connect_timeout=5)


def upsert_player_basic(
    cur: psycopg2.extensions.cursor,
    name: str, nationality: str, club: str, tm_url: str, rank: int,
) -> None:
    cur.execute(
        """
        INSERT INTO players
            (name, full_name, nationality, current_team, market_value_rank,
             transfermarkt_url, next_refresh_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (name) DO UPDATE SET
            current_team      = EXCLUDED.current_team,
            market_value_rank = LEAST(players.market_value_rank, EXCLUDED.market_value_rank),
            transfermarkt_url = COALESCE(EXCLUDED.transfermarkt_url, players.transfermarkt_url)
        """,
        (name, name, nationality, club, rank, tm_url),
    )


def update_full_player(
    conn: psycopg2.extensions.connection,
    player_id: int,
    data: dict,
    new_hash: str,
    next_refresh: datetime,
    stable_streak: int = 0,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE players SET
                full_name         = COALESCE(%s, full_name),
                date_of_birth     = COALESCE(%s, date_of_birth),
                nationality       = COALESCE(%s, nationality),
                position          = COALESCE(%s, position),
                current_team      = COALESCE(%s, current_team),
                market_value      = COALESCE(%s, market_value),
                social_media      = %s,
                profile_image_url = COALESCE(%s, profile_image_url),
                is_retired        = %s,
                is_injured        = %s,
                last_scraped_at   = NOW(),
                next_refresh_at   = %s,
                stable_streak     = %s,
                data_hash         = %s
            WHERE id = %s
            """,
            (
                data.get("full_name"), _normalize_date(data.get("date_of_birth") or ""), data.get("nationality"),
                data.get("position"), data.get("current_team"), data.get("market_value"),
                json.dumps(data.get("social_media")) if data.get("social_media") else None,
                data.get("profile_image_url"),
                data.get("is_retired", False), data.get("is_injured", False),
                next_refresh, stable_streak, new_hash, player_id,
            ),
        )

        if data.get("seasons"):
            cur.execute("DELETE FROM season_stats WHERE player_id = %s", (player_id,))
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO season_stats
                       (player_id, season, team, age, appearances, starts, minutes_played,
                        goals, assists, yellow_cards, red_cards)
                   VALUES %s""",
                [
                    (player_id, s["season"], s["team"], 0, s["appearances"], 0, 0,
                     s["goals"], s["assists"], 0, 0)
                    for s in data["seasons"]
                ],
            )

        if data.get("injuries"):
            cur.execute("DELETE FROM injuries WHERE player_id = %s", (player_id,))
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO injuries
                       (player_id, season, injury_type, date_from, date_until,
                        days_missed, games_missed)
                   VALUES %s""",
                [
                    (player_id, i["season"], i["injury_type"],
                     _normalize_date(i["date_from"]), _normalize_date(i["date_until"]),
                     i["days_missed"], i["games_missed"])
                    for i in data["injuries"]
                ],
            )
    conn.commit()


def bump_next_refresh(
    conn: psycopg2.extensions.connection, player_id: int, days: int,
    stable_streak: int | None = None,
) -> None:
    with conn.cursor() as cur:
        if stable_streak is None:
            cur.execute(
                "UPDATE players SET last_scraped_at = NOW(), "
                "next_refresh_at = NOW() + (%s || ' days')::INTERVAL WHERE id = %s",
                (str(days), player_id),
            )
        else:
            cur.execute(
                "UPDATE players SET last_scraped_at = NOW(), stable_streak = %s, "
                "next_refresh_at = NOW() + (%s || ' days')::INTERVAL WHERE id = %s",
                (stable_streak, str(days), player_id),
            )
    conn.commit()


# ---------------------------------------------------------------------------
# Orquestrador principal
# ---------------------------------------------------------------------------

def seed_all(source_filter: str | None = None,
             only_phase1: bool = False,
             only_phase2: bool = False,
             limit: int | None = None) -> None:
    start = time.time()
    logger.info("=" * 60)
    logger.info("RUN %s — Seeder iniciado", RUN_ID)
    if source_filter:
        logger.info("Filtro: --source=%s", source_filter)
    if only_phase1:
        logger.info("Modo: --phase1 (apenas listas)")
    if only_phase2:
        logger.info("Modo: --phase2 (apenas detalhes pendentes)")
    logger.info("Log desta execução: %s", RUN_LOG)
    logger.info("=" * 60)

    state = _load_state()
    session = _make_session()
    conn = _get_conn()

    # -----------------------------------------------------------------------
    # Phase 1: buscar listas (apenas se passou LIST_REFRESH_DAYS por fonte)
    # -----------------------------------------------------------------------
    phase1_total = 0
    if not only_phase2:
        for source in SOURCES:
            name = source["name"]
            if source_filter and source_filter != name:
                logger.debug("[phase1] %s — pulando (filtrado por --source)", name)
                continue
            if not _source_needs_list_refresh(state, name):
                logger.info("[phase1] %s — lista atualizada há menos de %d dias, pulando",
                            name, LIST_REFRESH_DAYS)
                continue

        logger.info("[phase1] %s — buscando %d páginas", name, source["pages"])
        source_count = 0

        for page in range(1, source["pages"] + 1):
            players = fetch_player_list_page(
                session, source["url"], source["params"], page
            )
            if not players:
                logger.info("[phase1] %s pág %d — vazia, encerrando fonte", name, page)
                break

            with conn.cursor() as cur:
                for i, p in enumerate(players):
                    rank = source["rank_offset"] + (page - 1) * LIST_PAGE_SIZE + i + 1
                    upsert_player_basic(cur, p["name"], p["nationality"], p["club"],
                                        p["tm_url"], rank)
            conn.commit()

            source_count += len(players)
            logger.info("[phase1] %s pág %d/%d — %d jogadores (acumulado: %d)",
                        name, page, source["pages"], len(players), source_count)
            time.sleep(SCRAPE_DELAY)

        _mark_list_fetched(state, name)
        _save_state(state)
        phase1_total += source_count
        logger.info("[phase1] %s concluído: %d jogadores indexados", name, source_count)

    logger.info("[phase1] TOTAL indexado nesta execução: %d", phase1_total)

    # -----------------------------------------------------------------------
    # Phase 2: raspar dados completos dos pendentes
    # -----------------------------------------------------------------------
    if only_phase1:
        elapsed = int(time.time() - start)
        conn.close()
        logger.info("=" * 60)
        logger.info("RUN %s CONCLUÍDO (--phase1) em %dm%ds | listas=%d",
                    RUN_ID, elapsed // 60, elapsed % 60, phase1_total)
        logger.info("Log completo: %s", RUN_LOG)
        logger.info("=" * 60)
        return

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, transfermarkt_url,
                   COALESCE(market_value_rank, 9999),
                   data_hash,
                   COALESCE(is_retired, FALSE),
                   COALESCE(is_injured, FALSE),
                   date_of_birth,
                   COALESCE(stable_streak, 0)
            FROM players
            WHERE next_refresh_at <= NOW()
              AND transfermarkt_url IS NOT NULL
            ORDER BY COALESCE(market_value_rank, 9999), next_refresh_at
            """
            + ("LIMIT %s" % int(limit) if limit else "")
        )
        due = cur.fetchall()

    total_due = len(due)
    logger.info("[phase2] %d jogadores pendentes de atualização", total_due)

    refreshed = skipped_injured = skipped_unchanged = errors = 0

    for idx, row in enumerate(due, 1):
        pid, pname, tm_url, mv_rank, old_hash, is_retired, is_injured, dob, old_streak = row
        # calcula idade em Python para evitar cast SQL problemático
        age = 25
        if dob:
            m = re.search(r"(\d{4})", str(dob))
            if m:
                age = datetime.now().year - int(m.group(1))
        progress = f"[{idx}/{total_due}]"

        # Pula lesionado só no refresh (já tem dados); no seed inicial
        # (old_hash NULL) raspa mesmo lesionado, senão nunca pega o histórico.
        if is_injured and not is_retired and old_hash:
            logger.info("[phase2] %s %s — LESIONADO, reagendando em 3 dias", progress, pname)
            bump_next_refresh(conn, pid, 3)
            skipped_injured += 1
            continue

        logger.info("[phase2] %s Raspando: %s (rank=%d, idade=%d, url=%s)",
                    progress, pname, mv_rank, age, tm_url)

        try:
            data = scrape_full_player(session, tm_url)
        except Exception as exc:
            logger.error("[phase2] %s ERRO raspando %s: %s", progress, pname, exc)
            bump_next_refresh(conn, pid, 1)
            errors += 1
            continue

        if not data:
            logger.warning("[phase2] %s %s — sem dados retornados", progress, pname)
            errors += 1
            continue

        if data.get("profile_image_url"):
            local_url = _download_profile_image(data["profile_image_url"], tm_url)
            if local_url:
                data["profile_image_url"] = local_url

        new_hash = compute_hash(data)

        effective_age = age
        if data.get("date_of_birth"):
            m = re.search(r"(\d{4})", data["date_of_birth"])
            if m:
                effective_age = datetime.now().year - int(m.group(1))

        # backoff adaptativo: estável (hash igual) → streak++; mudou → zera
        unchanged = old_hash is not None and new_hash == old_hash
        new_streak = (old_streak + 1) if unchanged else 0

        refresh_days = compute_refresh_days(
            effective_age, mv_rank, data.get("is_retired", False), new_streak
        )
        next_refresh = datetime.now(timezone.utc) + timedelta(days=refresh_days)

        if unchanged:
            logger.info("[phase2] %s %s — SEM MUDANÇAS (streak=%d) → próxima em %d dias",
                        progress, pname, new_streak, refresh_days)
            bump_next_refresh(conn, pid, refresh_days, stable_streak=new_streak)
            skipped_unchanged += 1
        else:
            logger.info("[phase2] %s %s — ATUALIZADO (%d temp, %d lesões) → próxima em %d dias",
                        progress, pname,
                        len(data.get("seasons", [])), len(data.get("injuries", [])),
                        refresh_days)
            update_full_player(conn, pid, data, new_hash, next_refresh, stable_streak=0)
            refreshed += 1

        time.sleep(SCRAPE_DELAY)

    elapsed = int(time.time() - start)
    conn.close()

    logger.info("=" * 60)
    logger.info(
        "RUN %s CONCLUÍDO em %dm%ds | atualizados=%d sem_mudança=%d "
        "lesionados_pulados=%d erros=%d",
        RUN_ID, elapsed // 60, elapsed % 60,
        refreshed, skipped_unchanged, skipped_injured, errors,
    )
    logger.info("Log completo: %s", RUN_LOG)
    logger.info("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Smart seeder do Transfermarkt")
    parser.add_argument("--source", help="Processar apenas esta fonte (ex: premier_top50)")
    parser.add_argument("--phase1", action="store_true", help="Apenas buscar listas")
    parser.add_argument("--phase2", action="store_true", help="Apenas raspar detalhes pendentes")
    parser.add_argument("--limit", type=int, default=None, help="Máx de jogadores por execução (lote)")
    args = parser.parse_args()

    try:
        seed_all(source_filter=args.source, only_phase1=args.phase1,
                 only_phase2=args.phase2, limit=args.limit)
    except Exception:
        logger.exception("CRASH FATAL no seeder — traceback completo acima")
        raise
