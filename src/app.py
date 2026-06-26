from __future__ import annotations

import logging
import secrets

from flask import Flask, make_response, render_template, request, jsonify, session

from src.models.player import Player
from src.services.comparison_engine import compare_players
from src.services.projection import calculate_projection
from src.services.report import generate_report

logger = logging.getLogger(__name__)


_SEARCH_DB: dict[str, Player] = {}


def _register_player(player: Player) -> None:
    _SEARCH_DB[player.name.lower()] = player


def _init_default_players() -> None:
    from src.models.player import SeasonStats, Injury

    defaults = [
        Player(
            name="Messi", full_name="Lionel Andrés Messi Cuccittini",
            date_of_birth="1987-06-24", nationality="Argentina",
            position="Forward", current_team="Inter Miami",
            sponsors=("Adidas", "Pepsi", "Budweiser", "Hard Rock Cafe", "Saudi Tourism"),
            career_seasons=(
                SeasonStats("2004-2005", "Barcelona", 17, 9, 1, 480, 1, 0, 0, 0),
                SeasonStats("2005-2006", "Barcelona", 18, 17, 11, 1104, 8, 3, 2, 0),
                SeasonStats("2006-2007", "Barcelona", 19, 36, 25, 2382, 14, 3, 4, 0),
                SeasonStats("2007-2008", "Barcelona", 20, 40, 35, 3040, 16, 8, 3, 0),
                SeasonStats("2008-2009", "Barcelona", 21, 51, 45, 4060, 38, 18, 2, 0),
                SeasonStats("2009-2010", "Barcelona", 22, 55, 49, 4350, 47, 11, 3, 0),
                SeasonStats("2010-2011", "Barcelona", 23, 55, 50, 4280, 53, 23, 3, 0),
                SeasonStats("2011-2012", "Barcelona", 24, 60, 55, 4830, 73, 29, 2, 0),
                SeasonStats("2012-2013", "Barcelona", 25, 50, 45, 3800, 60, 16, 2, 0),
                SeasonStats("2013-2014", "Barcelona", 26, 46, 38, 3150, 41, 14, 3, 0),
                SeasonStats("2014-2015", "Barcelona", 27, 57, 50, 4280, 58, 27, 1, 0),
                SeasonStats("2015-2016", "Barcelona", 28, 49, 43, 3550, 41, 18, 2, 0),
                SeasonStats("2016-2017", "Barcelona", 29, 52, 45, 3800, 54, 16, 2, 0),
                SeasonStats("2017-2018", "Barcelona", 30, 54, 48, 4020, 45, 18, 2, 0),
                SeasonStats("2018-2019", "Barcelona", 31, 50, 44, 3680, 51, 19, 2, 0),
                SeasonStats("2019-2020", "Barcelona", 32, 44, 38, 3150, 31, 25, 2, 0),
                SeasonStats("2020-2021", "Barcelona", 33, 47, 40, 3400, 38, 12, 3, 0),
                SeasonStats("2021-2022", "PSG", 34, 34, 26, 2200, 11, 14, 2, 0),
                SeasonStats("2022-2023", "PSG", 35, 41, 35, 2900, 21, 20, 2, 0),
                SeasonStats("2023-2024", "Inter Miami", 36, 38, 34, 2850, 22, 12, 1, 0),
            ),
            world_cup_goals=13, world_cup_appearances=26,
            injuries=(
                Injury("2013-2014", "Muscle injury", "2013-11-10", "2013-12-05", 25, 4),
                Injury("2015-2016", "Knee injury", "2016-04-05", "2016-05-15", 40, 5),
                Injury("2018-2019", "Hamstring", "2019-03-01", "2019-03-18", 17, 3),
            ),
        ),
        Player(
            name="Ronaldo", full_name="Cristiano Ronaldo dos Santos Aveiro",
            date_of_birth="1985-02-05", nationality="Portugal",
            position="Forward", current_team="Al Nassr",
            sponsors=("Nike", "Clear", "Herbalife", "CR7 Brand", "Pestana"),
            career_seasons=(
                SeasonStats("2002-2003", "Sporting", 17, 31, 20, 1900, 5, 6, 4, 0),
                SeasonStats("2003-2004", "Man United", 18, 40, 29, 2650, 6, 9, 5, 1),
                SeasonStats("2004-2005", "Man United", 19, 50, 37, 3100, 9, 9, 7, 0),
                SeasonStats("2005-2006", "Man United", 20, 53, 40, 3400, 12, 11, 6, 1),
                SeasonStats("2006-2007", "Man United", 21, 53, 44, 3650, 23, 18, 5, 0),
                SeasonStats("2007-2008", "Man United", 22, 49, 45, 3850, 42, 8, 4, 0),
                SeasonStats("2008-2009", "Man United", 23, 53, 47, 4100, 26, 12, 4, 0),
                SeasonStats("2009-2010", "Real Madrid", 24, 35, 30, 2650, 33, 7, 3, 0),
                SeasonStats("2010-2011", "Real Madrid", 25, 54, 48, 4050, 53, 18, 3, 0),
                SeasonStats("2011-2012", "Real Madrid", 26, 55, 50, 4300, 69, 16, 3, 0),
                SeasonStats("2012-2013", "Real Madrid", 27, 55, 48, 4000, 55, 12, 3, 0),
                SeasonStats("2013-2014", "Real Madrid", 28, 47, 40, 3350, 51, 17, 2, 0),
                SeasonStats("2014-2015", "Real Madrid", 29, 54, 46, 3800, 61, 21, 2, 0),
                SeasonStats("2015-2016", "Real Madrid", 30, 54, 47, 3900, 51, 15, 2, 0),
                SeasonStats("2016-2017", "Real Madrid", 31, 46, 40, 3400, 42, 12, 1, 0),
                SeasonStats("2017-2018", "Real Madrid", 32, 44, 38, 3200, 44, 8, 2, 0),
                SeasonStats("2018-2019", "Juventus", 33, 43, 38, 3250, 28, 10, 4, 0),
                SeasonStats("2019-2020", "Juventus", 34, 44, 38, 3200, 37, 7, 3, 0),
                SeasonStats("2020-2021", "Juventus", 35, 44, 36, 3050, 36, 4, 3, 0),
                SeasonStats("2021-2022", "Man United", 36, 38, 32, 2700, 24, 3, 4, 0),
                SeasonStats("2022-2023", "Al Nassr", 37, 30, 26, 2200, 14, 2, 2, 0),
                SeasonStats("2023-2024", "Al Nassr", 38, 35, 30, 2600, 28, 5, 2, 0),
            ),
            world_cup_goals=8, world_cup_appearances=22,
            injuries=(
                Injury("2008-2009", "Ankle", "2008-10-19", "2008-11-15", 27, 4),
                Injury("2013-2014", "Knee", "2014-05-04", "2014-05-15", 11, 2),
                Injury("2019-2020", "Knee", "2019-10-08", "2019-10-25", 17, 3),
            ),
        ),
        Player(
            name="Kaka", full_name="Ricardo Izecson dos Santos Leite",
            date_of_birth="1982-04-22", nationality="Brazil",
            position="Midfielder", current_team="Aposentado",
            sponsors=("Adidas", "Toyota", "Gillette", "EA Sports"),
            career_seasons=(
                SeasonStats("2001-2002", "São Paulo", 19, 27, 22, 1950, 12, 3, 3, 0),
                SeasonStats("2002-2003", "São Paulo", 20, 24, 20, 1700, 10, 5, 2, 0),
                SeasonStats("2003-2004", "AC Milan", 21, 30, 18, 1650, 10, 4, 2, 0),
                SeasonStats("2004-2005", "AC Milan", 22, 40, 30, 2650, 7, 6, 3, 0),
                SeasonStats("2005-2006", "AC Milan", 23, 43, 35, 3050, 14, 8, 4, 0),
                SeasonStats("2006-2007", "AC Milan", 24, 50, 44, 3800, 10, 4, 5, 0),
                SeasonStats("2007-2008", "AC Milan", 25, 39, 32, 2750, 15, 6, 3, 0),
                SeasonStats("2008-2009", "Real Madrid", 26, 32, 25, 2100, 8, 4, 2, 0),
                SeasonStats("2009-2010", "Real Madrid", 27, 25, 18, 1450, 8, 3, 1, 0),
                SeasonStats("2010-2011", "Real Madrid", 28, 14, 8, 720, 3, 2, 1, 0),
                SeasonStats("2011-2012", "AC Milan", 29, 30, 22, 1850, 7, 5, 2, 0),
                SeasonStats("2012-2013", "AC Milan", 30, 30, 25, 2100, 4, 3, 3, 0),
                SeasonStats("2013-2014", "São Paulo", 31, 19, 15, 1200, 2, 3, 1, 0),
                SeasonStats("2014-2015", "Orlando City", 32, 28, 25, 2100, 9, 4, 2, 0),
            ),
            world_cup_goals=5, world_cup_appearances=14,
            injuries=(
                Injury("2010-2011", "Groin", "2010-09-15", "2010-11-20", 66, 8),
                Injury("2011-2012", "Knee", "2012-01-10", "2012-02-15", 36, 5),
            ),
        ),
        Player(
            name="Neymar", full_name="Neymar da Silva Santos Júnior",
            date_of_birth="1992-02-05", nationality="Brazil",
            position="Forward", current_team="Al Hilal",
            sponsors=("Nike", "Puma", "Red Bull", "Gillette", "Beats"),
            career_seasons=(
                SeasonStats("2009-2010", "Santos", 17, 43, 30, 2800, 14, 7, 6, 0),
                SeasonStats("2010-2011", "Santos", 18, 53, 42, 3600, 21, 12, 8, 0),
                SeasonStats("2011-2012", "Santos", 19, 47, 40, 3400, 18, 10, 6, 0),
                SeasonStats("2012-2013", "Santos", 20, 34, 28, 2400, 14, 7, 5, 0),
                SeasonStats("2013-2014", "Barcelona", 21, 41, 30, 2550, 15, 15, 5, 0),
                SeasonStats("2014-2015", "Barcelona", 22, 51, 42, 3500, 39, 11, 6, 0),
                SeasonStats("2015-2016", "Barcelona", 23, 46, 38, 3100, 31, 20, 5, 0),
                SeasonStats("2016-2017", "Barcelona", 24, 45, 38, 3100, 20, 27, 3, 0),
                SeasonStats("2017-2018", "PSG", 25, 30, 24, 2050, 28, 16, 4, 0),
                SeasonStats("2018-2019", "PSG", 26, 28, 22, 1800, 23, 8, 4, 0),
                SeasonStats("2019-2020", "PSG", 27, 27, 20, 1650, 19, 8, 2, 0),
                SeasonStats("2020-2021", "PSG", 28, 31, 25, 2100, 17, 10, 4, 0),
                SeasonStats("2021-2022", "PSG", 29, 28, 22, 1800, 13, 13, 2, 0),
                SeasonStats("2022-2023", "PSG", 30, 29, 24, 2000, 18, 17, 2, 0),
                SeasonStats("2023-2024", "Al Hilal", 31, 20, 16, 1350, 10, 5, 2, 0),
            ),
            world_cup_goals=8, world_cup_appearances=13,
            injuries=(
                Injury("2014-2015", "Vertebra", "2014-07-04", "2014-10-05", 93, 12),
                Injury("2017-2018", "Metatarsal", "2018-02-25", "2018-05-08", 72, 9),
                Injury("2018-2019", "Groin", "2019-01-28", "2019-03-10", 41, 6),
                Injury("2019-2020", "Metatarsal", "2020-02-02", "2020-04-25", 83, 11),
                Injury("2022-2023", "Ankle", "2023-02-15", "2023-04-15", 59, 8),
            ),
        ),
        Player(
            name="Mbappe", full_name="Kylian Mbappé Lottin",
            date_of_birth="1998-12-20", nationality="France",
            position="Forward", current_team="Real Madrid",
            sponsors=("Nike", "Hublot", "EA Sports", "Ray-Ban"),
            career_seasons=(
                SeasonStats("2015-2016", "Monaco", 17, 14, 4, 480, 1, 0, 1, 0),
                SeasonStats("2016-2017", "Monaco", 18, 44, 25, 2200, 26, 12, 3, 0),
                SeasonStats("2017-2018", "PSG", 19, 43, 32, 2800, 21, 16, 3, 0),
                SeasonStats("2018-2019", "PSG", 20, 42, 35, 2950, 33, 7, 4, 0),
                SeasonStats("2019-2020", "PSG", 21, 34, 28, 2350, 30, 19, 2, 0),
                SeasonStats("2020-2021", "PSG", 22, 47, 40, 3400, 42, 11, 3, 0),
                SeasonStats("2021-2022", "PSG", 23, 46, 38, 3200, 39, 21, 2, 0),
                SeasonStats("2022-2023", "PSG", 24, 43, 36, 3050, 41, 10, 2, 0),
                SeasonStats("2023-2024", "PSG", 25, 48, 42, 3500, 44, 10, 3, 0),
            ),
            world_cup_goals=12, world_cup_appearances=14,
            injuries=(
                Injury("2018-2019", "Hamstring", "2019-03-05", "2019-03-25", 20, 3),
                Injury("2022-2023", "Hamstring", "2023-02-05", "2023-02-25", 20, 3),
            ),
        ),
        Player(
            name="Haaland", full_name="Erling Braut Haaland",
            date_of_birth="2000-07-21", nationality="Norway",
            position="Forward", current_team="Man City",
            sponsors=("Nike", "NordVPN", "Boohoo", "Red Bull"),
            career_seasons=(
                SeasonStats("2016-2017", "Molde", 16, 14, 5, 520, 4, 0, 1, 0),
                SeasonStats("2017-2018", "Molde", 17, 25, 12, 1150, 5, 1, 2, 0),
                SeasonStats("2018-2019", "Salzburg", 18, 22, 15, 1350, 16, 6, 2, 0),
                SeasonStats("2019-2020", "Salzburg/Dortmund", 19, 40, 30, 2700, 44, 10, 4, 0),
                SeasonStats("2020-2021", "Dortmund", 20, 41, 35, 3000, 41, 8, 4, 0),
                SeasonStats("2021-2022", "Dortmund", 21, 30, 25, 2150, 29, 8, 3, 0),
                SeasonStats("2022-2023", "Man City", 22, 53, 45, 3850, 52, 9, 4, 0),
                SeasonStats("2023-2024", "Man City", 23, 45, 40, 3400, 38, 6, 3, 0),
            ),
            world_cup_goals=0, world_cup_appearances=0,
            injuries=(
                Injury("2019-2020", "Knee", "2020-02-12", "2020-03-15", 32, 4),
                Injury("2022-2023", "Groin", "2023-01-15", "2023-02-08", 24, 3),
            ),
        ),
        Player(
            name="Lewandowski", full_name="Robert Lewandowski",
            date_of_birth="1988-08-21", nationality="Poland",
            position="Forward", current_team="Barcelona",
            sponsors=("Nike", "Vistula", "Procter & Gamble", "Huawei"),
            career_seasons=(
                SeasonStats("2006-2007", "Znicz Pruszków", 18, 27, 20, 1800, 15, 3, 3, 0),
                SeasonStats("2007-2008", "Lech Poznan", 19, 42, 32, 2800, 18, 7, 4, 0),
                SeasonStats("2008-2009", "Lech Poznan", 20, 36, 30, 2550, 14, 7, 3, 0),
                SeasonStats("2009-2010", "Dortmund", 21, 42, 34, 2900, 9, 5, 5, 0),
                SeasonStats("2010-2011", "Dortmund", 22, 47, 38, 3200, 22, 10, 4, 0),
                SeasonStats("2011-2012", "Dortmund", 23, 50, 42, 3550, 30, 12, 3, 0),
                SeasonStats("2012-2013", "Dortmund", 24, 48, 40, 3400, 36, 13, 3, 0),
                SeasonStats("2013-2014", "Dortmund", 25, 48, 40, 3350, 28, 12, 3, 0),
                SeasonStats("2014-2015", "Bayern", 26, 49, 42, 3550, 30, 7, 3, 0),
                SeasonStats("2015-2016", "Bayern", 27, 51, 44, 3700, 42, 7, 3, 0),
                SeasonStats("2016-2017", "Bayern", 28, 47, 40, 3350, 30, 10, 2, 0),
                SeasonStats("2017-2018", "Bayern", 29, 48, 42, 3550, 41, 7, 3, 0),
                SeasonStats("2018-2019", "Bayern", 30, 47, 40, 3350, 40, 11, 3, 0),
                SeasonStats("2019-2020", "Bayern", 31, 47, 40, 3350, 55, 10, 2, 0),
                SeasonStats("2020-2021", "Bayern", 32, 40, 35, 2950, 48, 9, 2, 0),
                SeasonStats("2021-2022", "Bayern", 33, 46, 40, 3400, 50, 7, 2, 0),
                SeasonStats("2022-2023", "Barcelona", 34, 46, 40, 3350, 33, 8, 2, 0),
                SeasonStats("2023-2024", "Barcelona", 35, 45, 40, 3300, 26, 9, 1, 0),
            ),
            world_cup_goals=6, world_cup_appearances=14,
            injuries=(
                Injury("2018-2019", "Knee", "2019-03-01", "2019-03-15", 14, 2),
                Injury("2021-2022", "Hamstring", "2022-01-15", "2022-02-05", 21, 3),
            ),
        ),
    ]
    for p in defaults:
        _SEARCH_DB[p.name.lower()] = p

    extras = [
        Player(
            name="Ronaldinho", full_name="Ronaldo de Assis Moreira",
            date_of_birth="1980-03-21", nationality="Brazil",
            position="Forward", current_team="Aposentado",
            sponsors=("Nike", "Pepsi", "Coca-Cola", "EA Sports"),
            career_seasons=(
                SeasonStats("1998-1999", "Gremio", 18, 27, 20, 1800, 15, 3, 3, 0),
                SeasonStats("2001-2002", "PSG", 21, 28, 20, 1750, 9, 5, 3, 0),
                SeasonStats("2002-2003", "PSG", 22, 36, 28, 2400, 12, 6, 4, 0),
                SeasonStats("2003-2004", "Barcelona", 23, 43, 35, 3050, 22, 12, 3, 0),
                SeasonStats("2004-2005", "Barcelona", 24, 51, 44, 3800, 26, 15, 3, 0),
                SeasonStats("2005-2006", "Barcelona", 25, 53, 46, 3950, 33, 18, 2, 0),
                SeasonStats("2006-2007", "Barcelona", 26, 49, 42, 3600, 28, 14, 3, 0),
                SeasonStats("2007-2008", "AC Milan", 27, 32, 25, 2150, 10, 8, 2, 0),
                SeasonStats("2008-2009", "AC Milan", 28, 38, 30, 2600, 12, 10, 3, 0),
                SeasonStats("2009-2010", "AC Milan", 29, 35, 28, 2350, 8, 7, 2, 0),
                SeasonStats("2010-2011", "Flamengo", 30, 22, 18, 1500, 5, 4, 2, 0),
                SeasonStats("2011-2012", "Atletico Mineiro", 31, 32, 28, 2350, 12, 10, 3, 0),
                SeasonStats("2012-2013", "Atletico Mineiro", 32, 30, 26, 2150, 10, 8, 2, 0),
            ),
            world_cup_goals=5, world_cup_appearances=18,
            injuries=(
                Injury("2006-2007", "Hamstring", "2007-02-01", "2007-03-10", 37, 5),
                Injury("2008-2009", "Knee", "2009-01-15", "2009-02-20", 36, 5),
            ),
        ),
        Player(
            name="Pele", full_name="Edson Arantes do Nascimento",
            date_of_birth="1940-10-23", nationality="Brazil",
            position="Forward", current_team="Aposentado",
            sponsors=("Adidas", "Pepsi", "Hublot", "Santander"),
            career_seasons=(
                SeasonStats("1956-1957", "Santos", 16, 30, 25, 2200, 17, 5, 2, 0),
                SeasonStats("1957-1958", "Santos", 17, 35, 30, 2600, 23, 8, 3, 0),
                SeasonStats("1958-1959", "Santos", 18, 40, 35, 3050, 32, 12, 3, 0),
                SeasonStats("1959-1960", "Santos", 19, 45, 40, 3400, 35, 15, 2, 0),
                SeasonStats("1960-1961", "Santos", 20, 46, 42, 3550, 47, 18, 2, 0),
                SeasonStats("1961-1962", "Santos", 21, 42, 38, 3200, 38, 14, 3, 0),
                SeasonStats("1962-1963", "Santos", 22, 44, 40, 3350, 42, 16, 2, 0),
                SeasonStats("1963-1964", "Santos", 23, 45, 42, 3500, 40, 15, 2, 0),
                SeasonStats("1964-1965", "Santos", 24, 44, 40, 3400, 38, 14, 2, 0),
                SeasonStats("1965-1966", "Santos", 25, 43, 38, 3200, 35, 12, 3, 0),
                SeasonStats("1966-1967", "Santos", 26, 42, 38, 3150, 32, 11, 2, 0),
                SeasonStats("1967-1968", "Santos", 27, 44, 40, 3350, 38, 14, 2, 0),
                SeasonStats("1968-1969", "Santos", 28, 45, 42, 3500, 42, 16, 2, 0),
                SeasonStats("1969-1970", "Santos", 29, 43, 40, 3350, 36, 12, 2, 0),
                SeasonStats("1970-1971", "Santos", 30, 42, 38, 3200, 30, 10, 2, 0),
                SeasonStats("1971-1972", "Santos", 31, 40, 36, 3000, 28, 9, 2, 0),
                SeasonStats("1972-1973", "Santos", 32, 38, 34, 2800, 25, 8, 2, 0),
                SeasonStats("1973-1974", "New York Cosmos", 33, 30, 28, 2350, 15, 7, 1, 0),
                SeasonStats("1974-1975", "New York Cosmos", 34, 32, 30, 2500, 18, 8, 1, 0),
                SeasonStats("1975-1976", "New York Cosmos", 35, 28, 25, 2100, 14, 6, 1, 0),
                SeasonStats("1976-1977", "New York Cosmos", 36, 25, 22, 1850, 12, 5, 1, 0),
            ),
            world_cup_goals=12, world_cup_appearances=14,
            injuries=(),
        ),
        Player(
            name="Maradona", full_name="Diego Armando Maradona",
            date_of_birth="1960-10-30", nationality="Argentina",
            position="Forward", current_team="Aposentado",
            sponsors=("Puma", "Adidas", "Joma"),
            career_seasons=(
                SeasonStats("1976-1977", "Argentinos Juniors", 16, 35, 28, 2500, 11, 5, 4, 0),
                SeasonStats("1977-1978", "Argentinos Juniors", 17, 40, 34, 2900, 18, 8, 5, 0),
                SeasonStats("1978-1979", "Argentinos Juniors", 18, 42, 36, 3100, 22, 10, 4, 0),
                SeasonStats("1979-1980", "Argentinos Juniors", 19, 45, 40, 3400, 26, 12, 3, 0),
                SeasonStats("1980-1981", "Argentinos Juniors", 20, 44, 40, 3350, 28, 14, 3, 0),
                SeasonStats("1981-1982", "Boca Juniors", 21, 40, 35, 3000, 18, 10, 4, 0),
                SeasonStats("1982-1983", "Barcelona", 22, 30, 24, 2050, 12, 8, 3, 0),
                SeasonStats("1983-1984", "Barcelona", 23, 32, 26, 2200, 14, 9, 3, 0),
                SeasonStats("1984-1985", "Napoli", 24, 34, 28, 2400, 14, 8, 4, 0),
                SeasonStats("1985-1986", "Napoli", 25, 36, 30, 2600, 12, 10, 3, 0),
                SeasonStats("1986-1987", "Napoli", 26, 40, 34, 2900, 18, 12, 3, 0),
                SeasonStats("1987-1988", "Napoli", 27, 38, 32, 2750, 15, 10, 3, 0),
                SeasonStats("1988-1989", "Napoli", 28, 36, 30, 2600, 12, 8, 3, 0),
                SeasonStats("1989-1990", "Napoli", 29, 35, 28, 2450, 10, 7, 3, 0),
                SeasonStats("1990-1991", "Napoli", 30, 32, 26, 2250, 8, 6, 3, 0),
                SeasonStats("1992-1993", "Sevilla", 32, 28, 22, 1850, 5, 4, 3, 0),
                SeasonStats("1993-1994", "Newell's Old Boys", 33, 20, 16, 1350, 3, 3, 2, 0),
                SeasonStats("1995-1996", "Boca Juniors", 35, 22, 18, 1500, 5, 3, 2, 0),
            ),
            world_cup_goals=8, world_cup_appearances=21,
            injuries=(
                Injury("1982-1983", "Knee", "1983-09-24", "1983-12-10", 77, 10),
                Injury("1990-1991", "Knee", "1990-09-01", "1990-10-15", 44, 6),
            ),
        ),
        Player(
            name="Zidane", full_name="Zinedine Yazid Zidane",
            date_of_birth="1972-06-23", nationality="France",
            position="Midfielder", current_team="Aposentado",
            sponsors=("Adidas", "Pepsi", "Konica Minolta", "Kia"),
            career_seasons=(
                SeasonStats("1988-1989", "Cannes", 16, 25, 18, 1550, 2, 3, 2, 0),
                SeasonStats("1989-1990", "Cannes", 17, 35, 28, 2400, 5, 6, 4, 0),
                SeasonStats("1990-1991", "Cannes", 18, 38, 32, 2700, 6, 8, 4, 0),
                SeasonStats("1991-1992", "Bordeaux", 19, 38, 32, 2700, 7, 9, 3, 0),
                SeasonStats("1992-1993", "Bordeaux", 20, 40, 34, 2900, 10, 10, 3, 0),
                SeasonStats("1993-1994", "Bordeaux", 21, 42, 36, 3050, 12, 12, 3, 0),
                SeasonStats("1994-1995", "Bordeaux", 22, 44, 38, 3250, 15, 14, 3, 0),
                SeasonStats("1995-1996", "Bordeaux", 23, 42, 36, 3050, 14, 12, 3, 0),
                SeasonStats("1996-1997", "Juventus", 24, 44, 38, 3250, 7, 14, 3, 0),
                SeasonStats("1997-1998", "Juventus", 25, 42, 36, 3050, 8, 12, 3, 0),
                SeasonStats("1998-1999", "Real Madrid", 26, 44, 38, 3250, 10, 12, 3, 0),
                SeasonStats("1999-2000", "Real Madrid", 27, 42, 36, 3050, 8, 10, 3, 0),
                SeasonStats("2000-2001", "Real Madrid", 28, 44, 38, 3250, 12, 14, 2, 0),
                SeasonStats("2001-2002", "Real Madrid", 29, 42, 36, 3050, 9, 12, 2, 0),
                SeasonStats("2002-2003", "Real Madrid", 30, 44, 38, 3250, 10, 14, 2, 0),
                SeasonStats("2003-2004", "Real Madrid", 31, 42, 36, 3050, 8, 10, 2, 0),
                SeasonStats("2004-2005", "Real Madrid", 32, 40, 34, 2850, 6, 8, 2, 0),
                SeasonStats("2005-2006", "Real Madrid", 33, 36, 30, 2500, 4, 6, 2, 0),
            ),
            world_cup_goals=5, world_cup_appearances=12,
            injuries=(
                Injury("1998-1999", "Hamstring", "1999-02-15", "1999-03-20", 33, 4),
                Injury("2001-2002", "Ankle", "2002-02-01", "2002-02-25", 24, 3),
            ),
        ),
        Player(
            name="Ronaldo9", full_name="Ronaldo Luís Nazário de Lima",
            date_of_birth="1976-09-18", nationality="Brazil",
            position="Forward", current_team="Aposentado",
            sponsors=("Nike", "Pepsi", "Coca-Cola", "EA Sports"),
            career_seasons=(
                SeasonStats("1992-1993", "Cruzeiro", 16, 30, 24, 2100, 12, 5, 3, 0),
                SeasonStats("1993-1994", "PSV", 17, 36, 28, 2450, 12, 6, 4, 0),
                SeasonStats("1994-1995", "PSV", 18, 38, 30, 2600, 18, 8, 3, 0),
                SeasonStats("1995-1996", "Barcelona", 19, 46, 38, 3250, 35, 16, 3, 0),
                SeasonStats("1996-1997", "Inter Milan", 20, 47, 40, 3450, 34, 12, 3, 0),
                SeasonStats("1997-1998", "Inter Milan", 21, 42, 35, 3000, 28, 10, 3, 0),
                SeasonStats("1998-1999", "Inter Milan", 22, 30, 24, 2050, 14, 6, 2, 0),
                SeasonStats("1999-2000", "Inter Milan", 23, 8, 6, 480, 3, 2, 0, 0),
                SeasonStats("2000-2001", "Inter Milan", 24, 0, 0, 0, 0, 0, 0, 0),
                SeasonStats("2001-2002", "Inter Milan", 25, 10, 8, 650, 5, 3, 1, 0),
                SeasonStats("2002-2003", "Real Madrid", 26, 42, 35, 3000, 29, 10, 3, 0),
                SeasonStats("2003-2004", "Real Madrid", 27, 42, 36, 3050, 24, 8, 3, 0),
                SeasonStats("2004-2005", "Real Madrid", 28, 40, 34, 2850, 22, 6, 3, 0),
                SeasonStats("2005-2006", "Real Madrid", 29, 34, 28, 2350, 14, 5, 2, 0),
                SeasonStats("2006-2007", "AC Milan", 30, 20, 16, 1350, 7, 4, 1, 0),
                SeasonStats("2007-2008", "AC Milan", 31, 18, 14, 1150, 6, 3, 1, 0),
                SeasonStats("2008-2009", "Corinthians", 32, 28, 24, 2000, 12, 5, 3, 0),
                SeasonStats("2009-2010", "Corinthians", 33, 25, 22, 1800, 8, 4, 2, 0),
                SeasonStats("2010-2011", "Corinthians", 34, 12, 10, 800, 3, 2, 1, 0),
            ),
            world_cup_goals=15, world_cup_appearances=19,
            injuries=(
                Injury("1998-1999", "Knee", "1999-11-21", "2000-04-20", 150, 18),
                Injury("2000-2001", "Knee", "2000-04-20", "2001-09-25", 523, 60),
                Injury("2007-2008", "Knee", "2008-02-15", "2008-04-10", 55, 7),
            ),
        ),
        Player(
            name="Henry", full_name="Thierry Daniel Henry",
            date_of_birth="1977-08-17", nationality="France",
            position="Forward", current_team="Aposentado",
            sponsors=("Adidas", "Pepsi", "Renault", "Gillette"),
            career_seasons=(
                SeasonStats("1994-1995", "Monaco", 17, 30, 18, 1550, 3, 4, 2, 0),
                SeasonStats("1995-1996", "Monaco", 18, 35, 25, 2150, 8, 7, 3, 0),
                SeasonStats("1996-1997", "Monaco", 19, 38, 30, 2550, 12, 10, 3, 0),
                SeasonStats("1997-1998", "Monaco", 20, 42, 35, 3000, 18, 12, 3, 0),
                SeasonStats("1998-1999", "Juventus", 21, 28, 18, 1450, 5, 4, 2, 0),
                SeasonStats("1999-2000", "Arsenal", 22, 48, 40, 3450, 22, 15, 4, 0),
                SeasonStats("2000-2001", "Arsenal", 23, 50, 44, 3750, 26, 12, 3, 0),
                SeasonStats("2001-2002", "Arsenal", 24, 52, 46, 3950, 32, 18, 3, 0),
                SeasonStats("2002-2003", "Arsenal", 25, 52, 46, 3950, 32, 14, 3, 0),
                SeasonStats("2003-2004", "Arsenal", 26, 52, 46, 3950, 30, 12, 2, 0),
                SeasonStats("2004-2005", "Arsenal", 27, 50, 44, 3750, 25, 14, 2, 0),
                SeasonStats("2005-2006", "Arsenal", 28, 46, 40, 3450, 22, 12, 2, 0),
                SeasonStats("2006-2007", "Barcelona", 29, 42, 35, 3000, 14, 10, 2, 0),
                SeasonStats("2007-2008", "Barcelona", 30, 40, 32, 2750, 12, 8, 2, 0),
                SeasonStats("2008-2009", "New York Red Bulls", 31, 28, 25, 2100, 8, 6, 1, 0),
                SeasonStats("2009-2010", "New York Red Bulls", 32, 30, 28, 2350, 10, 8, 1, 0),
                SeasonStats("2010-2011", "New York Red Bulls", 33, 25, 22, 1850, 8, 6, 1, 0),
                SeasonStats("2011-2012", "Arsenal", 34, 15, 8, 650, 3, 2, 0, 0),
            ),
            world_cup_goals=3, world_cup_appearances=13,
            injuries=(
                Injury("2001-2002", "Hamstring", "2002-01-10", "2002-02-05", 26, 3),
                Injury("2005-2006", "Hamstring", "2006-01-15", "2006-02-10", 26, 3),
            ),
        ),
        Player(
            name="Ibrahimovic", full_name="Zlatan Ibrahimović",
            date_of_birth="1981-10-03", nationality="Sweden",
            position="Forward", current_team="Aposentado",
            sponsors=("Nike", "Volvo", "A-Z Sportswear", "EA Sports"),
            career_seasons=(
                SeasonStats("1999-2000", "Malmo", 18, 30, 22, 1900, 5, 4, 3, 0),
                SeasonStats("2000-2001", "Malmo", 19, 32, 25, 2100, 12, 6, 3, 0),
                SeasonStats("2001-2002", "Ajax", 20, 38, 30, 2600, 15, 8, 3, 0),
                SeasonStats("2002-2003", "Ajax", 21, 38, 32, 2700, 18, 10, 3, 0),
                SeasonStats("2003-2004", "Ajax", 22, 38, 32, 2700, 16, 8, 3, 0),
                SeasonStats("2004-2005", "Juventus", 23, 42, 35, 3000, 16, 10, 3, 0),
                SeasonStats("2005-2006", "Juventus", 24, 42, 36, 3050, 12, 8, 3, 0),
                SeasonStats("2006-2007", "Inter Milan", 25, 42, 36, 3050, 15, 8, 3, 0),
                SeasonStats("2007-2008", "Inter Milan", 26, 42, 36, 3050, 18, 10, 3, 0),
                SeasonStats("2008-2009", "Barcelona", 27, 40, 32, 2750, 16, 9, 2, 0),
                SeasonStats("2009-2010", "AC Milan", 28, 40, 34, 2900, 22, 8, 3, 0),
                SeasonStats("2010-2011", "AC Milan", 29, 42, 36, 3050, 21, 10, 3, 0),
                SeasonStats("2011-2012", "AC Milan", 30, 42, 35, 3000, 20, 12, 2, 0),
                SeasonStats("2012-2013", "PSG", 31, 42, 36, 3050, 30, 10, 2, 0),
                SeasonStats("2013-2014", "PSG", 32, 42, 36, 3050, 26, 12, 2, 0),
                SeasonStats("2014-2015", "PSG", 33, 42, 36, 3050, 22, 10, 2, 0),
                SeasonStats("2015-2016", "Man United", 34, 42, 36, 3050, 22, 10, 2, 0),
                SeasonStats("2016-2017", "Man United", 35, 38, 32, 2700, 18, 8, 2, 0),
                SeasonStats("2017-2018", "LA Galaxy", 36, 28, 25, 2100, 22, 10, 1, 0),
                SeasonStats("2018-2019", "LA Galaxy", 37, 30, 28, 2350, 30, 12, 1, 0),
                SeasonStats("2019-2020", "AC Milan", 38, 25, 20, 1700, 15, 5, 2, 0),
                SeasonStats("2020-2021", "AC Milan", 39, 35, 28, 2350, 18, 8, 2, 0),
                SeasonStats("2021-2022", "AC Milan", 40, 28, 22, 1850, 12, 5, 2, 0),
            ),
            world_cup_goals=0, world_cup_appearances=0,
            injuries=(
                Injury("2012-2013", "Knee", "2013-03-01", "2013-04-15", 45, 6),
                Injury("2017-2018", "Knee", "2018-03-01", "2018-04-10", 40, 5),
                Injury("2019-2020", "Knee", "2020-01-01", "2020-02-15", 45, 6),
            ),
        ),
        Player(
            name="Benzema", full_name="Karim Mostafa Benzema",
            date_of_birth="1987-12-19", nationality="France",
            position="Forward", current_team="Al Ittihad",
            sponsors=("Adidas", "EA Sports", "Vivo", "Bocados"),
            career_seasons=(
                SeasonStats("2004-2005", "Lyon", 17, 12, 5, 520, 1, 0, 0, 0),
                SeasonStats("2005-2006", "Lyon", 18, 30, 18, 1550, 7, 4, 2, 0),
                SeasonStats("2006-2007", "Lyon", 19, 40, 30, 2600, 15, 8, 3, 0),
                SeasonStats("2007-2008", "Lyon", 20, 42, 35, 3000, 20, 12, 3, 0),
                SeasonStats("2008-2009", "Lyon", 21, 42, 36, 3050, 23, 14, 2, 0),
                SeasonStats("2009-2010", "Real Madrid", 22, 42, 32, 2750, 15, 8, 2, 0),
                SeasonStats("2010-2011", "Real Madrid", 23, 42, 32, 2750, 13, 8, 2, 0),
                SeasonStats("2011-2012", "Real Madrid", 24, 42, 35, 3000, 21, 10, 2, 0),
                SeasonStats("2012-2013", "Real Madrid", 25, 42, 35, 3000, 20, 12, 2, 0),
                SeasonStats("2013-2014", "Real Madrid", 26, 42, 35, 3000, 24, 12, 2, 0),
                SeasonStats("2014-2015", "Real Madrid", 27, 42, 35, 3000, 22, 10, 2, 0),
                SeasonStats("2015-2016", "Real Madrid", 28, 42, 35, 3000, 28, 10, 2, 0),
                SeasonStats("2016-2017", "Real Madrid", 29, 42, 35, 3000, 24, 10, 2, 0),
                SeasonStats("2017-2018", "Real Madrid", 30, 42, 35, 3000, 18, 8, 2, 0),
                SeasonStats("2018-2019", "Real Madrid", 31, 42, 35, 3000, 21, 8, 2, 0),
                SeasonStats("2019-2020", "Real Madrid", 32, 42, 35, 3000, 27, 8, 2, 0),
                SeasonStats("2020-2021", "Real Madrid", 33, 42, 35, 3000, 30, 8, 2, 0),
                SeasonStats("2021-2022", "Real Madrid", 34, 42, 35, 3000, 44, 15, 1, 0),
                SeasonStats("2022-2023", "Real Madrid", 35, 38, 30, 2600, 19, 10, 2, 0),
                SeasonStats("2023-2024", "Al Ittihad", 36, 30, 25, 2100, 12, 5, 2, 0),
            ),
            world_cup_goals=3, world_cup_appearances=13,
            injuries=(
                Injury("2018-2019", "Groin", "2019-01-05", "2019-02-05", 31, 4),
                Injury("2020-2021", "Knee", "2021-03-01", "2021-03-20", 19, 3),
            ),
        ),
    ]
    for p in extras:
        _SEARCH_DB[p.name.lower()] = p


_ALIASES: dict[str, str] = {
    "cr7": "ronaldo",
    "cristiano": "ronaldo",
    "ronaldo nazario": "ronaldo",
    "ronaldinho": "ronaldinho",
    "gaucho": "ronaldinho",
    "kaka": "kaka",
    "ricardo kaka": "kaka",
    "neymar jr": "neymar",
    "neymar junior": "neymar",
    "mbappe": "mbappe",
    "kylian": "mbappe",
    "haaland": "haaland",
    "erling": "haaland",
    "lewandowski": "lewandowski",
    "robert": "lewandowski",
    "lewy": "lewandowski",
    "messi": "messi",
    "leo": "messi",
    "lionel": "messi",
    "pelé": "pele",
    "pele": "pele",
    "maradona": "maradona",
    "diego": "maradona",
    "zidane": "zidane",
    "zinedine": "zidane",
    "ronaldo fenomeno": "ronaldo9",
    "fenomeno": "ronaldo9",
    "r9": "ronaldo9",
    "baggio": "baggio",
    "del piero": "delPiero",
    "henry": "henry",
    "thierry": "henry",
    "shevchenko": "shevchenko",
    "andriy": "shevchenko",
    "ibrahimovic": "ibrahimovic",
    "zlatan": "ibrahimovic",
    "brahimovic": "ibrahimovic",
    "benzema": "benzema",
    "karim": "benzema",
    "salah": "salah",
    "mohamed": "salah",
    "de bruyne": "deBruyne",
    "kevin": "deBruyne",
    "modric": "modric",
    "luka": "modric",
    "neuer": "neuer",
    "manuel": "neuer",
    "buffon": "buffon",
    "gianluigi": "buffon",
    "casillas": "casillas",
    "iker": "casillas",
    "ter stegen": "terStegen",
    "marc": "terStegen",
    "alisson": "alisson",
    "ederson": "ederson",
    "virgil": "vanDijk",
    "van dijk": "vanDijk",
    "ramos": "ramos",
    "sergio ramos": "ramos",
    "pique": "pique",
    "gerard": "pique",
    "marcelo": "marcelo",
    "dani alves": "daniAlves",
    "dani": "daniAlves",
    "xavi": "xavi",
    "xavier": "xavi",
    "iniesta": "iniesta",
    "andres": "iniesta",
    "pogba": "pogba",
    "paul": "pogba",
    "griezmann": "griezmann",
    "antoine": "griezmann",
    "cavani": "cavani",
    "edinson": "cavani",
    "suarez": "suarez",
    "luis": "suarez",
    "luis suarez": "suarez",
    "dybala": "dybala",
    "paulo": "dybala",
    "hazard": "hazard",
    "eden": "hazard",
    "kane": "kane",
    "harry": "kane",
    "son": "son",
    "heung-min": "son",
    "muller": "muller",
    "thomas": "muller",
    "reus": "reus",
    "marco": "reus",
    "kdb": "deBruyne",
    "silva": "silva",
    "bernardo": "silva",
    "david silva": "silva",
    "isco": "isco",
    "marco asensio": "asensio",
    "asensio": "asensio",
    "pedri": "pedri",
    "gavi": "gavi",
    "bellingham": "bellingham",
    "jude": "bellingham",
    "vinicius": "vinicius",
    "vinícius": "vinicius",
    "vini jr": "vinicius",
    "rodrygo": "rodrygo",
    "foden": "foden",
    "phil": "foden",
    "saka": "saka",
    "bukayo": "saka",
    "palmer": "palmer",
    "cole": "palmer",
    "yamal": "yamal",
    "lamine": "yamal",
}


def search_player(name: str) -> Player:
    key = name.strip().lower()

    direct = _SEARCH_DB.get(key)
    if direct is not None:
        return direct

    alias_target = _ALIASES.get(key)
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
    alias = _ALIASES.get(key)
    if alias and alias in _SEARCH_DB:
        return alias
    for db_key in _SEARCH_DB:
        if key in db_key or db_key in key:
            return db_key
    return key


_init_default_players()


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = app.config.get("SECRET_KEY") or "dev-fallback-key"

    @app.before_request
    def _generate_csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)

    @app.context_processor
    def inject_csrf_token():
        return {"csrf_token": session.get("csrf_token", "")}

    @app.route("/")
    def home():
        players_dict = {k: v for k, v in sorted(_SEARCH_DB.items())}
        html = render_template("index.html", players=players_dict)
        resp = make_response(html)
        resp.content_type = "text/html"
        return resp

    @app.route("/compare", methods=["GET", "POST"])
    def compare():
        if request.method == "GET":
            p1_name = request.args.get("p1", "").strip()
            p2_name = request.args.get("p2", "").strip()
            if not p1_name or not p2_name:
                players_dict = {k: v for k, v in sorted(_SEARCH_DB.items())}
                html = render_template("index.html", players=players_dict)
                resp = make_response(html)
                resp.content_type = "text/html"
                return resp
        else:
            if not app.config.get("TESTING"):
                csrf_token = request.form.get("csrf_token", "")
                if not csrf_token or csrf_token != session.get("csrf_token"):
                    players_dict = {k: v for k, v in sorted(_SEARCH_DB.items())}
                    html = render_template("index.html", players=players_dict, error="Token CSRF inválido.")
                    resp = make_response(html, 403)
                    resp.content_type = "text/html"
                    return resp

            p1_name = request.form.get("player1_selected", "").strip() or request.form.get("player1", "").strip()
            p2_name = request.form.get("player2_selected", "").strip() or request.form.get("player2", "").strip()

        if not p1_name or not p2_name:
            players_dict = {k: v for k, v in sorted(_SEARCH_DB.items())}
            html = render_template("index.html", players=players_dict, error="Selecione dois jogadores para comparar.")
            resp = make_response(html, 400)
            resp.content_type = "text/html"
            return resp

        try:
            p1 = search_player(p1_name)
            p2 = search_player(p2_name)
        except ValueError as e:
            players_dict = {k: v for k, v in sorted(_SEARCH_DB.items())}
            html = render_template("index.html", players=players_dict, error=str(e))
            resp = make_response(html, 404)
            resp.content_type = "text/html"
            return resp

        p1_key = _resolve_key(p1_name)
        p2_key = _resolve_key(p2_name)

        try:
            comparison = compare_players(p1, p2)
        except Exception:
            logger.exception("Error comparing players %s vs %s", p1_name, p2_name)
            players_dict = {k: v for k, v in sorted(_SEARCH_DB.items())}
            html = render_template("index.html", players=players_dict, error="Erro interno. Tente novamente.")
            resp = make_response(html, 500)
            resp.content_type = "text/html"
            return resp

        report = generate_report(comparison)

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
    def api_search(name: str):
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

    return app
