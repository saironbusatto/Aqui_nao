from __future__ import annotations

import base64
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from soccerplots.radar_chart import Radar

from src.models.player import Player

_NEON_GREEN = "#00FF87"
_CYAN = "#60EFFF"
_BG = "#050509"
_SURFACE = "#0d0d1a"

_PARAMS = ["Gols", "Assistências", "Jogos", "Min×10", "Títulos\nMundial"]
_RANGE_CAPS = [900, 400, 1000, 9000, 10]


def _player_values(p: Player) -> list[float]:
    return [
        float(p.total_goals),
        float(p.total_assists),
        float(p.total_appearances),
        float(p.total_minutes / 10),
        float(p.world_cup_goals),
    ]


def _ranges(p1: Player, p2: Player) -> list[tuple[float, float]]:
    v1 = _player_values(p1)
    v2 = _player_values(p2)
    result = []
    for i, cap in enumerate(_RANGE_CAPS):
        low = 0.0
        high = min(max(v1[i], v2[i]) * 1.25 or 1.0, float(cap))
        result.append((low, high))
    return result


def generate_radar_base64(p1: Player, p2: Player) -> str:
    ranges = _ranges(p1, p2)
    v1 = _player_values(p1)
    v2 = _player_values(p2)

    radar = Radar(
        background_color=_BG,
        patch_color=_SURFACE,
        label_color=_NEON_GREEN,
        range_color="#444466",
        label_fontsize=11,
        range_fontsize=7,
    )

    title = {
        "title_name": p1.name,
        "title_color": _NEON_GREEN,
        "subtitle_name": p1.nationality,
        "subtitle_color": "#aaaacc",
        "title_name_2": p2.name,
        "title_color_2": _CYAN,
        "subtitle_name_2": p2.nationality,
        "subtitle_color_2": "#aaaacc",
        "title_fontsize": 14,
        "subtitle_fontsize": 10,
    }

    fig, _ = radar.plot_radar(
        ranges=ranges,
        params=_PARAMS,
        values=[v1, v2],
        radar_color=[_NEON_GREEN, _CYAN],
        compare=True,
        alphas=[0.35, 0.35],
        title=title,
        endnote="aqui-nao.com · dados: FBref / Transfermarkt",
        end_color="#555577",
        end_size=8,
    )

    fig.patch.set_facecolor(_BG)
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=_BG)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")
