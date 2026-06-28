from __future__ import annotations

import logging
import os
import secrets
from dataclasses import replace

from flask import Flask, make_response, render_template, request, jsonify, session, redirect, url_for, g
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
    if pg_players:
        default_map = {p.name.lower(): p for p in DEFAULT_PLAYERS}
        for p in pg_players:
            key = p.name.lower()
            default = default_map.get(key)
            if default:
                _SEARCH_DB[key] = replace(
                    p,
                    profile_image_url=p.profile_image_url or default.profile_image_url,
                    social_media=p.social_media or default.social_media,
                )
            else:
                _SEARCH_DB[key] = p
        logger.info("Banco de jogadores: %d jogadores (Postgres + merge)", len(_SEARCH_DB))
    else:
        for p in DEFAULT_PLAYERS:
            _SEARCH_DB[p.name.lower()] = p
        logger.info("Banco de jogadores: %d jogadores (local)", len(_SEARCH_DB))


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

    raise ValueError(f"Jogador não encontrado: {name}")


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


def _html_response(html: str, status: int = 200):
    resp = make_response(html, status)
    resp.content_type = "text/html"
    return resp


def _season_age(dob: str, season: str) -> int | None:
    try:
        birth_year = int(dob[:4])
        start_yy = int(season.split("/")[0])
        start_year = (2000 + start_yy) if start_yy < 100 else start_yy
        return start_year - birth_year
    except (ValueError, IndexError):
        return None


def _age_data(player: Player) -> list[tuple[int, int]]:
    result = []
    for s in player.career_seasons:
        age = s.age if s.age else _season_age(player.date_of_birth, s.season)
        if age is not None:
            result.append((age, s.goals))
    return result


def _projection_dict(proj) -> dict[str, int]:
    return {
        "current": proj.current_goals,
        "at_30": proj.projected_goals_at_30,
        "at_35": proj.projected_goals_at_35,
        "at_40": proj.projected_goals_at_40,
    }


def create_app() -> Flask:
    app = Flask(__name__)
    secret_key = os.environ.get("SECRET_KEY") or app.config.get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY environment variable must be set")
    app.secret_key = secret_key

    if not _SEARCH_DB:
        _init_players()

    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per hour"],
        storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
        enabled=not app.config.get("TESTING", False),
    )

    @app.after_request
    def _set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        nonce = getattr(g, "csp_nonce", "")
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://upload.wikimedia.org https://img.a.transfermarkt.technology; "
            "connect-src 'self'; "
            "frame-src 'none'; "
            "object-src 'none';"
        )
        return response

    @app.before_request
    def _generate_csrf_token():
        g.csp_nonce = secrets.token_urlsafe(16)
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)

    @app.context_processor
    def inject_csrf_token():
        return {
            "csrf_token": session.get("csrf_token", ""),
            "csp_nonce": getattr(g, "csp_nonce", ""),
        }

    def _build_players_list() -> list[dict]:
        return [
            {
                "key": k, "name": v.name, "nationality": v.nationality,
                "team": v.current_team or "",
                "profile_image_url": v.profile_image_url,
                "social_media": v.social_media,
            }
            for k, v in sorted(_SEARCH_DB.items())
        ]

    def _render_home(**kwargs):
        return render_template("index.html", all_players=_build_players_list(), **kwargs)

    @app.route("/")
    def home():
        return _html_response(_render_home())

    def _resolve_players(p1_name: str, p2_name: str):
        players = []
        for name in (p1_name, p2_name):
            try:
                players.append(search_player(name))
            except ValueError:
                msg = f'"{name}" ainda não está na nossa base. Use a busca para encontrar jogadores indexados.'
                return None, None, _html_response(_render_home(error=msg), 404)
        return players[0], players[1], None

    @app.route("/compare", methods=["GET", "POST"])
    @limiter.limit("20 per minute")
    def compare():
        if request.method == "POST":
            if not app.config.get("TESTING"):
                csrf_token = request.form.get("csrf_token", "")
                if not csrf_token or csrf_token != session.get("csrf_token"):
                    return _html_response(_render_home(error="Token CSRF inválido."), 403)
            p1_name = request.form.get("player1_selected", "").strip() or request.form.get("player1", "").strip()
            p2_name = request.form.get("player2_selected", "").strip() or request.form.get("player2", "").strip()
            if not p1_name or not p2_name:
                return _html_response(_render_home(error="Selecione dois jogadores para comparar."), 400)
            return redirect(url_for("compare", p1=p1_name, p2=p2_name))

        p1_name = request.args.get("p1", "").strip()
        p2_name = request.args.get("p2", "").strip()
        if not p1_name or not p2_name:
            return _html_response(_render_home())

        p1, p2, err = _resolve_players(p1_name, p2_name)
        if err:
            return err

        try:
            comparison = compare_players(p1, p2)
        except Exception:
            logger.exception("Error comparing players %s vs %s", p1_name, p2_name)
            return _html_response(_render_home(error="Erro interno. Tente novamente."), 500)

        html = render_template(
            "compare.html",
            comparison=comparison,
            report=generate_report(comparison),
            radar_b64=generate_radar_base64(p1, p2),
            p1=p1,
            p2=p2,
            p1_key=_resolve_key(p1_name),
            p2_key=_resolve_key(p2_name),
            players={k: v for k, v in sorted(_SEARCH_DB.items())},
            age_data_a=_age_data(p1),
            age_data_b=_age_data(p2),
            season_data_a=[(s.season, s.goals) for s in p1.career_seasons],
            season_data_b=[(s.season, s.goals) for s in p2.career_seasons],
            projection1=_projection_dict(calculate_projection(p1)),
            projection2=_projection_dict(calculate_projection(p2)),
        )
        return _html_response(html)

    @app.route("/api/search/<name>")
    @limiter.limit("30 per minute")
    def api_search(name: str):
        if len(name) > 100:
            return jsonify({"results": [], "error": "Nome muito longo."}), 400
        q = name.strip().lower()
        results = [
            {"name": p.name, "nationality": p.nationality, "club": p.current_team or "",
             "profile_image_url": p.profile_image_url}
            for key, p in _SEARCH_DB.items()
            if q in key or q in (p.current_team or "").lower() or q in p.nationality.lower()
        ]
        results.sort(key=lambda r: (not r["name"].lower().startswith(q), r["name"]))
        return jsonify({"results": results[:10]})

    @app.route("/api/player/<name>")
    @limiter.limit("30 per minute")
    def api_player(name: str):
        if len(name) > 100:
            return jsonify({"error": "Nome inválido."}), 400
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
            "profile_image_url": player.profile_image_url,
            "social_media": player.social_media,
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
