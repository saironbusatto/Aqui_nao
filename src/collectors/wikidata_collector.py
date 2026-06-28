from __future__ import annotations

import logging

import requests

from src.models.player import Player
from src.utils.cache import get_cached, set_cached

logger = logging.getLogger(__name__)

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
USER_AGENT = "AquiNao/1.0 (comparador de jogadores)"
SEARCH_CACHE_NS = "wikidata_search"


def _search_entity(name: str) -> str | None:
    cached = get_cached(SEARCH_CACHE_NS, name.lower())
    if cached:
        return cached

    params = {
        "action": "wbsearchentities",
        "search": name,
        "language": "en",
        "limit": 5,
        "format": "json",
    }
    try:
        resp = requests.get(
            WIKIDATA_API,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        for result in data.get("search", []):
            qid = result.get("id")
            if qid:
                set_cached(SEARCH_CACHE_NS, name.lower(), qid)
                return qid
    except requests.RequestException:
        logger.warning("Erro ao buscar entidade no Wikidata: %s", name)

    return None


def _fetch_entity(qid: str) -> dict | None:
    cached = get_cached("wikidata_entity", qid)
    if cached:
        return cached

    try:
        resp = requests.get(
            WIKIDATA_ENTITY.format(qid=qid),
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        set_cached("wikidata_entity", qid, data)
        return data
    except requests.RequestException:
        logger.warning("Erro ao buscar entidade no Wikidata: %s", qid)

    return None


def _wikimedia_url(filename: str) -> str:
    filename = filename.replace(" ", "_")
    filename = filename[0].upper() + filename[1:]
    md5 = __import__("hashlib").md5(filename.encode()).hexdigest()
    return f"https://upload.wikimedia.org/wikipedia/commons/{md5[0]}/{md5[0:2]}/{filename}"


INSTAGRAM_PROP = "P2003"
TWITTER_PROP = "P2002"
IMAGE_PROP = "P18"


def fetch_player_social(player: Player) -> Player:
    if player.social_media and player.profile_image_url:
        return player

    qid = _search_entity(player.full_name)
    if not qid:
        qid = _search_entity(player.name)
    if not qid:
        return player

    entity = _fetch_entity(qid)
    if not entity:
        return player

    claims = (entity.get("entities", {}).get(qid, {}) or {}).get("claims", {})

    social_media = dict(player.social_media)
    profile_image_url = player.profile_image_url

    instagram_claims = claims.get(INSTAGRAM_PROP, [])
    twitter_claims = claims.get(TWITTER_PROP, [])
    image_claims = claims.get(IMAGE_PROP, [])

    if not social_media.get("instagram") and instagram_claims:
        value = instagram_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
        if value:
            social_media["instagram"] = value

    if not social_media.get("twitter") and twitter_claims:
        value = twitter_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
        if value:
            social_media["twitter"] = value

    if not profile_image_url and image_claims:
        filename = image_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
        if filename:
            profile_image_url = _wikimedia_url(filename)

    if social_media != player.social_media or profile_image_url != player.profile_image_url:
        from dataclasses import replace

        return replace(player, social_media=social_media, profile_image_url=profile_image_url)

    return player
