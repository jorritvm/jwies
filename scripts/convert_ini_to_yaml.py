"""Zet een oude config/controller.ini om naar de nieuwe YAML-bestanden.

    uv run python scripts/convert_ini_to_yaml.py oude/controller.ini uitvoer/

Schrijft een regelset en een puntenschaal die precies de instellingen van de
oude applicatie overnemen. Handig wanneer je een controller.ini van voor de
refactor hebt liggen en dezelfde huisregels wil blijven spelen.

De meegeleverde templates/ruleset/jwies_v0.yaml en
templates/scoring/jwies_v0.yaml zijn het resultaat van dit script op de
standaard-ini, dus je hebt het alleen nodig als je zelf iets had aangepast.
"""

from __future__ import annotations

import argparse
import configparser
import sys
from pathlib import Path

BEATS_TROEL = {
    "soloslim_beats_trull": "solo_slim",
    "solo_beats_trull": "solo",
    "misere_ouverte_beats_trull": "misere_ouverte",
}


def convert(ini_path: Path, out_dir: Path) -> tuple[Path, Path]:
    parser = configparser.ConfigParser()
    if not parser.read(ini_path, encoding="utf-8"):
        raise SystemExit(f"Kan '{ini_path}' niet lezen.")

    deal = parser["deal"]
    bid = parser["bid"]
    points = parser["points"]

    packets = [
        int(deal.get(f"deal_{index}", 0))
        for index in (1, 2, 3, 4)
        if int(deal.get(f"deal_{index}", 0)) > 0
    ]
    beaten_by = [
        contract for key, contract in BEATS_TROEL.items() if bid.getboolean(key, fallback=False)
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    ruleset_path = out_dir / "ruleset_uit_ini.yaml"
    scoring_path = out_dir / "scoring_uit_ini.yaml"

    ruleset_path.write_text(
        _ruleset_yaml(
            packets=packets,
            dealer_may_shuffle=deal.getboolean("dealer_can_shuffle", fallback=True),
            cut_minimum=int(deal.get("minimum_cards_to_cut", 1)),
            cut_maximum=int(deal.get("maximum_cards_to_cut", 51)),
            troel_above_all=bid.getboolean("trull_above_all_else", fallback=True),
            beaten_by=beaten_by,
            troel_tricks=int(points.get("trulltricks", 8)),
            lead_flags={
                "abondance": bid.getboolean("abondance_plays_first", fallback=True),
                "misere": bid.getboolean("misere_plays_first", fallback=True),
                "misere_ouverte": bid.getboolean("misere_ouverte_plays_first", fallback=True),
                "solo": bid.getboolean("solo_plays_first", fallback=True),
                "solo_slim": bid.getboolean("soloslim_plays_first", fallback=True),
            },
            all_pass_doubles=points.getboolean("when_all_pass_points_are_double", fallback=False),
        ),
        encoding="utf-8",
    )

    scoring_path.write_text(
        _scoring_yaml(
            base=points.get("exact_amount_of_tricks", "1"),
            per_overtrick=points.get("extra_trick", "0"),
            abondance=points.get("abundance", "5"),
            misere=points.get("misere", "5"),
            misere_ouverte=points.get("misere_ouverte", "10"),
            solo=points.get("solo", "20"),
            solo_slim=points.get("solo_slim", "40"),
            losing_is_double=points.getboolean("losing_is_double", fallback=False),
            all_pass_doubles=points.getboolean("when_all_pass_points_are_double", fallback=False),
        ),
        encoding="utf-8",
    )
    return ruleset_path, scoring_path


def _ruleset_yaml(**values: object) -> str:
    lead = values["lead_flags"]
    assert isinstance(lead, dict)
    beaten = values["beaten_by"]
    assert isinstance(beaten, list)
    beaten_text = "[" + ", ".join(beaten) + "]"
    all_passed = "volgende_ronde_dubbel" if values["all_pass_doubles"] else "herdelen"
    return f"""\
# Omgezet uit een oude controller.ini door scripts/convert_ini_to_yaml.py.
# Alle instellingen staan uitgelegd in templates/ruleset/klassiek.yaml.

# Versie van het bestandsformaat. Toegelaten waarden: 1
schema_versie: 1

# Naam die spelers zien in de lobby en bij het commando !ruleset.
naam: "Omgezet uit controller.ini"

delen:
  # Grootte van elk pakje dat de deler uitdeelt. De som moet 13 zijn.
  pakjes: {values["packets"]}

  # Mag de deler schudden? Toegelaten waarden: true, false
  deler_mag_schudden: {str(values["dealer_may_shuffle"]).lower()}

  # Minimum aantal kaarten dat de coupeur afneemt (1 t.e.m. 51).
  coupeer_minimum: {values["cut_minimum"]}

  # Maximum aantal kaarten dat de coupeur afneemt (1 t.e.m. 51).
  coupeer_maximum: {values["cut_maximum"]}

bieden:
  # Welke contracten mogen geboden worden, van laag naar hoog.
  volgorde:
    - alliance
    - alone
    - abondance_9
    - misere
    - abondance_10
    - abondance_11
    - abondance_12
    - troel
    - misere_ouverte
    - solo
    - solo_slim

  # Staat troel boven alles? Toegelaten waarden: true, false
  troel_boven_alles: {str(values["troel_above_all"]).lower()}

  # Welke contracten mogen een troel overtroeven?
  troel_kan_overboden_worden_door: {beaten_text}

  # Hoeveel slagen belooft wie alleen gaat? Toegelaten waarden: 5, 6
  slagen_bij_alleen_gaan: 5

  # Hoeveel slagen belooft een troelduo? Toegelaten waarden: 8, 9
  slagen_bij_troel: {values["troel_tricks"]}

  # Wat gebeurt er als iedereen past?
  # Toegelaten waarden: herdelen, volgende_ronde_dubbel
  iedereen_past: {all_passed}

uitkomen:
  # Komt de abondancespeler zelf uit? Toegelaten waarden: true, false
  abondance: {str(lead["abondance"]).lower()}

  # Komt de miseriespeler zelf uit? Toegelaten waarden: true, false
  misere: {str(lead["misere"]).lower()}

  # Komt de speler van miserie bloot zelf uit? Toegelaten waarden: true, false
  misere_ouverte: {str(lead["misere_ouverte"]).lower()}

  # Komt de solospeler zelf uit? Toegelaten waarden: true, false
  solo: {str(lead["solo"]).lower()}

  # Komt de solo slim-speler zelf uit? Toegelaten waarden: true, false
  solo_slim: {str(lead["solo_slim"]).lower()}

  # Komt bij troel de partner uit? Toegelaten waarden: true, false
  troel: true

spel:
  # Hoogste troef verplicht bij troel-8? Toegelaten waarden: true, false
  hoogste_troef_verplicht_bij_troel: true

  # Seconden dat een volle slag blijft liggen. Toegelaten waarden: 0 t.e.m. 15
  pauze_na_slag_seconden: 2

  # Aantal rondes; 0 = eindeloos.
  aantal_rondes: 0
"""


def _scoring_yaml(**values: object) -> str:
    contracts = "\n".join(
        f"""\
  # {comment}
  {key}:
    basis: {base}
    per_overslag: {over}"""
        for key, base, over, comment in [
            ("alliance", values["base"], values["per_overtrick"], "Vragen en meegaan."),
            ("alone", values["base"], values["per_overtrick"], "Alleen gaan."),
            ("troel", values["base"], values["per_overtrick"], "Troel."),
            ("abondance_9", values["abondance"], 0, "Abondance 9 slagen."),
            ("abondance_9_trump", values["abondance"], 0, "Abondance in troef."),
            ("abondance_10", values["abondance"], 0, "Abondance 10 slagen."),
            ("abondance_11", values["abondance"], 0, "Abondance 11 slagen."),
            ("abondance_12", values["abondance"], 0, "Abondance 12 slagen."),
            ("misere", values["misere"], 0, "Miserie."),
            ("misere_ouverte", values["misere_ouverte"], 0, "Miserie op tafel."),
            ("solo", values["solo"], 0, "Solo."),
            ("solo_slim", values["solo_slim"], 0, "Solo slim."),
        ]
    )
    return f"""\
# Omgezet uit een oude controller.ini door scripts/convert_ini_to_yaml.py.
# Alle instellingen staan uitgelegd in templates/scoring/schaal_a.yaml.
#
# Let op: de oude applicatie had de puntentelling nooit geimplementeerd. Deze
# bedragen stonden dus wel in je ini, maar werden niet toegepast.

# Versie van het bestandsformaat. Toegelaten waarden: 1
schema_versie: 1

# Naam die spelers zien bij het commando !counting.
naam: "Omgezet uit controller.ini"

# Hoe wordt een speler tegen drie afgerekend?
# Toegelaten waarden: per_tegenstander, gedeeld
betaling_solospel: per_tegenstander

# Kost een mislukt contract het dubbele? Toegelaten waarden: true, false
verliezen_is_dubbel: {str(values["losing_is_double"]).lower()}

# Verdubbelt de volgende ronde als iedereen past? Toegelaten waarden: true, false
iedereen_past_verdubbelt: {str(values["all_pass_doubles"]).lower()}

# Per contract: basis, per_overslag, per_slag_tekort (optioneel),
# alle_dertien (optioneel).
contracten:

{contracts}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ini", type=Path, help="pad naar de oude controller.ini")
    parser.add_argument("out", type=Path, help="map waar de YAML-bestanden komen")
    args = parser.parse_args(argv)

    ruleset, scoring = convert(args.ini, args.out)
    print(f"regelset geschreven naar   {ruleset}")
    print(f"puntenschaal geschreven naar {scoring}")
    print("\nControleer de bestanden en verwijs ernaar vanuit je server.yaml.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
