#!/usr/bin/env python3
"""
Seed mundial: descoberta via Wikidata (P2446 = Transfermarkt ID) +
scrape no Transfermarkt (fonte da verdade).

- Wikidata só fornece a LISTA de TM IDs (índice). Nada do Wikidata é
  armazenado — social, fotos, stats e lesões vêm do scrape do TM.
- Fila durável: cada candidato vira uma linha em `players` com
  next_refresh_at=NOW(). O scrape (phase2 do seeder) drena a fila em
  lotes. Crash/reset → quem não foi raspado continua pendente.
- Tiers processados em sequência: o próximo só é enfileirado quando a
  fila atual zera. Estado em world_state.json (em disco, sobrevive reboot).

Uso:
  seed_world.py tick --limit 150      # driver do cron: enfileira-se-vazio + raspa lote
  seed_world.py enqueue --tier brasil [--max N]
  seed_world.py status
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

import psycopg2
import psycopg2.errors
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.seeder import _get_conn, seed_all, LOG_DIR

logger = logging.getLogger("seed_world")

WDQS = "https://query.wikidata.org/sparql"
WDQS_HEADERS = {
    "User-Agent": "AquiNaoSeeder/1.0 (https://aquinao; ia@rfonseca.adv.br)",
    "Accept": "application/sparql-results+json",
}
PAGE_SIZE = 5000
STATE_FILE = LOG_DIR / "world_state.json"

# Ordem de prioridade dos tiers. Cada `pattern` é o corpo do WHERE em SPARQL.
TIERS: list[dict] = [
    {"key": "selecoes", "pattern": "?p wdt:P2446 ?tm . ?p wdt:P54 ?team . ?team wdt:P31 wd:Q6979593 ."},
    {"key": "brasil", "pattern": "?p wdt:P2446 ?tm . ?p wdt:P27 wd:Q155 ."},
    {"key": "fama10", "pattern": "?p wdt:P2446 ?tm . ?p wikibase:sitelinks ?s . FILTER(?s >= 10)"},
    {"key": "fama5", "pattern": "?p wdt:P2446 ?tm . ?p wikibase:sitelinks ?s . FILTER(?s >= 5)"},
    {"key": "todos", "pattern": "?p wdt:P2446 ?tm ."},
]


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            logger.warning("world_state.json corrompido, recomeçando estado")
    return {"enqueued": []}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _run_sparql(query: str) -> list[dict]:
    """Executa SPARQL com retries. Retorna lista de bindings simplificados."""
    for attempt in range(4):
        try:
            r = requests.get(
                WDQS, params={"query": query, "format": "json"},
                headers=WDQS_HEADERS, timeout=120,
            )
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 30))
                logger.warning("WDQS 429, aguardando %ds", wait)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()["results"]["bindings"]
        except Exception as exc:
            logger.warning("WDQS tentativa %d falhou: %s", attempt + 1, exc)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("WDQS falhou após retries")


def discover(pattern: str, max_n: int | None = None) -> list[tuple[str, str]]:
    """Paginação keyset por ?tm. Retorna [(tm_id, label), ...]."""
    out: list[tuple[str, str]] = []
    last = ""
    while True:
        query = f"""
        SELECT DISTINCT ?tm ?pLabel WHERE {{
          {pattern}
          FILTER(?tm > "{last}")
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,pt,es". }}
        }} ORDER BY ?tm LIMIT {PAGE_SIZE}
        """
        rows = _run_sparql(query)
        if not rows:
            break
        for b in rows:
            tm = b["tm"]["value"]
            label = b.get("pLabel", {}).get("value", "") or f"player-{tm}"
            out.append((tm, label))
        last = rows[-1]["tm"]["value"]
        logger.info("  descoberta: %d acumulados (último tm=%s)", len(out), last)
        if max_n and len(out) >= max_n:
            return out[:max_n]
        if len(rows) < PAGE_SIZE:
            break
        time.sleep(1)
    return out


def enqueue_tier(conn, tier: dict, max_n: int | None = None) -> int:
    """Insere candidatos como linhas básicas (fila). Idempotente: pula quem
    já tem o TM ID no banco. Trata colisão de nome (UNIQUE) com sufixo."""
    rows = discover(tier["pattern"], max_n=max_n)
    logger.info("[%s] %d candidatos do Wikidata", tier["key"], len(rows))
    conn.autocommit = True
    added = 0
    for tm_id, label in rows:
        url = f"https://www.transfermarkt.com/player/profil/spieler/{tm_id}"
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM players WHERE transfermarkt_url LIKE %s",
                (f"%/spieler/{tm_id}",),
            )
            if cur.fetchone():
                continue
            for cand in (label, f"{label} ({tm_id})"):
                try:
                    cur.execute(
                        "INSERT INTO players (name, full_name, transfermarkt_url, "
                        "is_retired, next_refresh_at) VALUES (%s, %s, %s, TRUE, NOW())",
                        (cand[:255], cand[:255], url),
                    )
                    added += 1
                    break
                except psycopg2.errors.UniqueViolation:
                    continue
    conn.autocommit = False
    logger.info("[%s] enfileirados %d novos (de %d)", tier["key"], added, len(rows))
    return added


def _count_due(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM players WHERE transfermarkt_url IS NOT NULL "
            "AND next_refresh_at <= NOW()"
        )
        return cur.fetchone()[0]


def _next_pending_tier(state: dict) -> dict | None:
    done = set(state.get("enqueued", []))
    for tier in TIERS:
        if tier["key"] not in done:
            return tier
    return None


def tick(limit: int) -> None:
    """Driver do cron: se a fila zerou, enfileira o próximo tier; depois
    raspa um lote limitado. Tudo idempotente e resumível."""
    conn = _get_conn()
    due = _count_due(conn)
    logger.info("tick: %d pendentes na fila", due)

    if due == 0:
        state = _load_state()
        tier = _next_pending_tier(state)
        if tier is None:
            logger.info("Todos os tiers enfileirados e drenados. Nada a fazer.")
            conn.close()
            return
        logger.info("Fila vazia → enfileirando próximo tier: %s", tier["key"])
        enqueue_tier(conn, tier)
        state.setdefault("enqueued", []).append(tier["key"])
        _save_state(state)

    conn.close()
    # Drena um lote. seed_all gerencia sua própria conexão.
    seed_all(only_phase2=True, limit=limit)


def status() -> None:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM players")
        total = cur.fetchone()[0]
        cur.execute("SELECT count(DISTINCT player_id) FROM season_stats")
        detailed = cur.fetchone()[0]
    due = _count_due(conn)
    conn.close()
    state = _load_state()
    print(f"Total jogadores: {total}")
    print(f"Detalhados:      {detailed}")
    print(f"Pendentes (fila):{due}")
    print(f"Tiers enfileirados: {state.get('enqueued', [])}")
    pending = _next_pending_tier(state)
    print(f"Próximo tier:    {pending['key'] if pending else '(nenhum)'}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    parser = argparse.ArgumentParser(description="Seed mundial Wikidata→Transfermarkt")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_tick = sub.add_parser("tick", help="Driver do cron")
    p_tick.add_argument("--limit", type=int, default=150)

    p_enq = sub.add_parser("enqueue", help="Enfileirar um tier manualmente")
    p_enq.add_argument("--tier", required=True, choices=[t["key"] for t in TIERS])
    p_enq.add_argument("--max", type=int, default=None, help="Limite p/ teste")

    sub.add_parser("status", help="Mostrar estado da fila/tiers")

    args = parser.parse_args()

    if args.cmd == "tick":
        tick(args.limit)
    elif args.cmd == "enqueue":
        conn = _get_conn()
        tier = next(t for t in TIERS if t["key"] == args.tier)
        enqueue_tier(conn, tier, max_n=args.max)
        if args.max is None:
            state = _load_state()
            if args.tier not in state.get("enqueued", []):
                state.setdefault("enqueued", []).append(args.tier)
                _save_state(state)
        conn.close()
    elif args.cmd == "status":
        status()
