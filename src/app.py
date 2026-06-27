from __future__ import annotations

import logging
import os
import secrets

from flask import Flask, make_response, render_template, request, jsonify, session, redirect, url_for
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from src.data.players import ALIASES, DEFAULT_PLAYERS
from src.data.postgres_loader import load_all_players
from src.models.player import Player
from src.services.comparison_engine import compare_players
from src.services.projection import calculate_projection
from src.services.radar_chart import generate_radar_base64
from src.services.report import generate_report

logger = logging.getLogger(__name__)


_SEARCH_DB: dict[str, Player] = {}


def _init_players() -> None:
    pg_players = load_all_players()
    source = pg_players if pg_players else DEFAULT_PLAYERS
    for p in source:
        _SEARCH_DB[p.name.lower()] = p
    logger.info(
        "Banco de jogadores: %d jogadores (%s)",
        len(_SEARCH_DB),
        "Postgres" if pg_players else "local",
    )


def search_player(name: str) -> Player:
    key = name.strip().lower()

    direct = _SEARCH_DB.get(key)
    if direct is not None:
        return direct

    alias_target = ALIASES.get(key)
    if alias_target:
        player = _SEARCH_DB.get(alias_target)
        if player is not None:
            return player

    for db_key, player in _SEARCH_DB.items():
        if key in db_key or db_key in key:
            return player

    try:
        from src.collectors.transfermarkt_scraper import search_players, scrape_player
        logger.info("Searching Transfermarkt for: %s", name)
        results = search_players(name)
        if results:
            best = results[0]
            logger.info("Best match: %s (%s) - %s", best["name"], best["nationality"], best["club"])
            scraped = scrape_player(best["name"])
            if scraped:
                _SEARCH_DB[key] = scraped
                return scraped
    except Exception as e:
        logger.warning("Scraping failed for %s: %s", name, e)

    raise ValueError(f"Jogador não encontrado: {name}. Jogadores disponíveis: {', '.join(sorted(_SEARCH_DB.keys()))}")


def _resolve_key(name: str) -> str:
    key = name.strip().lower()
    if key in _SEARCH_DB:
        return key
    alias = ALIASES.get(key)
    if alias and alias in _SEARCH_DB:
        return alias
    for db_key in _SEARCH_DB:
        if key in db_key or db_key in key:
            return db_key
    return key


_init_players()


def create_app() -> Flask:
    app = Flask(__name__)
    secret_key = os.environ.get("SECRET_KEY") or app.config.get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY environment variable must be set")
    app.secret_key = secret_key

    limiter = Limiter(app=app, key_func=get_remote_address, default_limits=[])

    app.config["CACHE_TYPE"] = "FileSystemCache"
    app.config["CACHE_DIR"] = str(
        __import__("pathlib").Path(__file__).parent.parent / "data" / "flask_cache"
    )
    app.config["CACHE_DEFAULT_TIMEOUT"] = 300
    flask_cache = Cache(app)

    @app.after_request
    def _set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-src 'none'; "
            "object-src 'none';"
        )
        return response

    @app.before_request
    def _generate_csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)

    @app.context_processor
    def inject_csrf_token():
        return {"csrf_token": session.get("csrf_token", "")}

    def _build_players_list() -> list[dict]:
        return [
            {"key": k, "name": v.name, "nationality": v.nationality, "team": v.current_team or ""}
            for k, v in sorted(_SEARCH_DB.items())
        ]

    def _render_home(**kwargs):
        return render_template("index.html", all_players=_build_players_list(), **kwargs)

    @app.route("/")
    def home():
        html = _render_home()
        resp = make_response(html)
        resp.content_type = "text/html"
        return resp

    @app.route("/compare", methods=["GET", "POST"])
    def compare():
        if request.method == "GET":
            p1_name = request.args.get("p1", "").strip()
            p2_name = request.args.get("p2", "").strip()
            if not p1_name or not p2_name:
                resp = make_response(_render_home())
                resp.content_type = "text/html"
                return resp
        else:
            if not app.config.get("TESTING"):
                csrf_token = request.form.get("csrf_token", "")
                if not csrf_token or csrf_token != session.get("csrf_token"):
                    resp = make_response(_render_home(error="Token CSRF inválido."), 403)
                    resp.content_type = "text/html"
                    return resp

            p1_name = request.form.get("player1_selected", "").strip() or request.form.get("player1", "").strip()
            p2_name = request.form.get("player2_selected", "").strip() or request.form.get("player2", "").strip()

            if not p1_name or not p2_name:
                resp = make_response(_render_home(error="Selecione dois jogadores para comparar."), 400)
                resp.content_type = "text/html"
                return resp

            return redirect(url_for("compare", p1=p1_name, p2=p2_name))

        if not p1_name or not p2_name:
            resp = make_response(_render_home(error="Selecione dois jogadores para comparar."), 400)
            resp.content_type = "text/html"
            return resp

        try:
            p1 = search_player(p1_name)
            p2 = search_player(p2_name)
        except ValueError as e:
            resp = make_response(_render_home(error=str(e)), 404)
            resp.content_type = "text/html"
            return resp

        p1_key = _resolve_key(p1_name)
        p2_key = _resolve_key(p2_name)

        try:
            comparison = compare_players(p1, p2)
        except Exception:
            logger.exception("Error comparing players %s vs %s", p1_name, p2_name)
            resp = make_response(_render_home(error="Erro interno. Tente novamente."), 500)
            resp.content_type = "text/html"
            return resp

        report = generate_report(comparison)
        radar_b64 = generate_radar_base64(p1, p2)

        age_data_a = [(s.age, s.goals) for s in p1.career_seasons]
        age_data_b = [(s.age, s.goals) for s in p2.career_seasons]
        season_data_a = [(s.season, s.goals) for s in p1.career_seasons]
        season_data_b = [(s.season, s.goals) for s in p2.career_seasons]

        proj1 = calculate_projection(p1)
        proj2 = calculate_projection(p2)

        players_dict = {k: v for k, v in sorted(_SEARCH_DB.items())}

        html = render_template(
            "compare.html",
            comparison=comparison,
            report=report,
            radar_b64=radar_b64,
            p1=p1,
            p2=p2,
            p1_key=p1_key,
            p2_key=p2_key,
            players=players_dict,
            age_data_a=age_data_a,
            age_data_b=age_data_b,
            season_data_a=season_data_a,
            season_data_b=season_data_b,
            projection1={
                "current": proj1.current_goals,
                "at_30": proj1.projected_goals_at_30,
                "at_35": proj1.projected_goals_at_35,
                "at_40": proj1.projected_goals_at_40,
            },
            projection2={
                "current": proj2.current_goals,
                "at_30": proj2.projected_goals_at_30,
                "at_35": proj2.projected_goals_at_35,
                "at_40": proj2.projected_goals_at_40,
            },
        )
        resp = make_response(html)
        resp.content_type = "text/html"
        return resp

    @app.route("/api/search/<name>")
    @limiter.limit("10 per minute")
    @flask_cache.cached(timeout=300, key_prefix=lambda: f"search:{request.view_args['name'].lower()}")
    def api_search(name: str):
        if len(name) > 100:
            return jsonify({"results": [], "error": "Nome muito longo."}), 400
        try:
            from src.collectors.transfermarkt_scraper import search_players
            results = search_players(name)
            return jsonify({"results": results[:10]})
        except Exception as e:
            logger.error("Search failed for %s: %s", name, e)
            return jsonify({"results": [], "error": str(e)}), 500

    @app.route("/api/player/<name>")
    def api_player(name: str):
        try:
            player = search_player(name)
        except ValueError:
            return jsonify({"error": "Player not found."}), 404

        return jsonify({
            "name": player.name,
            "full_name": player.full_name,
            "nationality": player.nationality,
            "position": player.position,
            "date_of_birth": player.date_of_birth,
            "current_team": player.current_team,
            "market_value": player.market_value,
            "sponsors": player.sponsors,
        })

    @app.route("/robots.txt")
    def robots_txt():
        body = "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n"
        return body, 200, {"Content-Type": "text/plain"}

    @app.route("/sitemap.xml")
    def sitemap_xml():
        players = sorted(_SEARCH_DB.keys())
        urls = ["<url><loc>/</loc><changefreq>weekly</changefreq></url>"]
        for p1 in players:
            for p2 in players:
                if p1 < p2:
                    urls.append(
                        f"<url><loc>/compare?p1={p1}&amp;p2={p2}</loc>"
                        f"<changefreq>monthly</changefreq></url>"
                    )
        body = '<?xml version="1.0" encoding="UTF-8"?>'
        body += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        body += "".join(urls) + "</urlset>"
        return body, 200, {"Content-Type": "application/xml"}

    return app
