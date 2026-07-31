# jwies

Vlaamse wies (traditioneel wiezen) om online te spelen met vier man.

Een headless server host meerdere tafels tegelijk. Spelers sluiten aan met de
**browser** of met de **PyQt-client**, door elkaar aan dezelfde tafel. Valt
iemands verbinding weg, dan pauzeert het spel en wacht het op hem.

De code is Engels, alles wat je op je scherm ziet is Nederlands.

---

## Snel starten

Je hebt [uv](https://docs.astral.sh/uv/) en Python 3.13 nodig.

```powershell
# clone en installeer
git clone https://github.com/jorritvm/jwies
cd jwies
uv sync --all-packages

# start de spelserver
uv run --package jwies-server jwies-server --config templates/server.yaml

# start, in een tweede venster, de webclient
uv run --package jwies-web-client jwies-web --game-server ws://127.0.0.1:8000/ws

# spelen: open http://localhost:8080 in vier browservensters
```

Twee processen dus: de **spelserver** (poort 8000, enkel websockets) en de
**webclient** (poort 8080, enkel bestanden). Ze staan los van elkaar, zodat de
pagina blijft laden terwijl je de spelserver herstart.

Liever de desktopclient?

```powershell
uv run --package jwies-qt-client jwies --username Jan --server ws://127.0.0.1:8000/ws
```

Voor een testpotje op je eigen computer start dit script een server plus vier
clients ineens:

```powershell
.\scripts\run_dev.ps1
```

---

## Zelf de regels bepalen

Elke tafel speelt volgens een **regelset** en een **puntenschaal**. Beide zijn
gewone YAML-bestanden waarin bij elke instelling staat wat ze doet en welke
waarden toegelaten zijn. Kopieer een template en pas hem aan:

```powershell
mkdir config
copy templates\server.yaml            config\server.yaml
copy templates\ruleset\klassiek.yaml  config\onze_club.yaml
copy templates\scoring\schaal_a.yaml  config\onze_punten.yaml
```

Verwijs er dan naar vanuit `config\server.yaml` en herstart de server.

Meegeleverd:

| Bestand | Wat |
|---|---|
| `templates/ruleset/klassiek.yaml` | De traditionele regels uit `docs/game_rules.md` (4-4-5 delen). |
| `templates/ruleset/jwies_v0.yaml` | De regels zoals jwies ze voor de refactor speelde (3-3-3-4). |
| `templates/scoring/schaal_a.yaml` | Kleine schaal: elke tegenstander betaalt het volle bedrag. |
| `templates/scoring/schaal_b.yaml` | Grote schaal (o.a. Sporza): het bedrag wordt gedeeld. |
| `templates/scoring/jwies_v0.yaml` | De bedragen uit de oude `controller.ini`. |

Had je een `controller.ini` van voor de refactor met eigen aanpassingen?

```powershell
uv run python scripts\convert_ini_to_yaml.py pad\naar\controller.ini config\
```

Een typfout in een instelling geeft een duidelijke Nederlandse foutmelding bij
het opstarten, in plaats van stilzwijgend genegeerd te worden.

---

## Chatcommando's

Iedereen aan tafel kan in de chat commando's aan de server geven:

| Commando | Wat het doet |
|---|---|
| `!help` | toont alle commando's |
| `!ruleset` | toont de spelregels die aan deze tafel gelden |
| `!score` | toont de huidige stand |
| `!counting` | toont hoe de punten geteld worden |
| `!seats` | toont wie waar zit |
| `!version` | toont de serverversie |

---

## Hoe het in elkaar zit

```
              statische bestanden
browser ──────→ jwies-web (poort 8080)
   │              HTML, CSS, JS, kaarten
   │
   └──┐
      ├─ websockets (JSON) ─→  jwies-server (poort 8000)  ─→  jwies-core
PyQt6 ┘                        lobby's, sessies, chat          spelregels,
                                                               puntentelling
```

De webclient wordt door zijn eigen webserver uitgedeeld, niet door de
spelserver. Die twee weten niets van elkaar: `jwies-web` deelt enkel bestanden
uit, `jwies-server` enkel spel. Ligt de spelserver even plat, dan laadt de
pagina nog altijd.

Vier losse pakketten onder `packages/`, elk met hun eigen afhankelijkheden:

| Pakket | Rol | Hangt af van |
|---|---|---|
| `jwies-core` | De spelregels en de puntentelling. Geen I/O, geen GUI, geen async. | pydantic, pyyaml |
| `jwies-web-client` | De browserclient plus de webserver die hem uitdeelt. | starlette, uvicorn |
| `jwies-server` | Lobby's, sessies, websockets, en het berichtenschema. Deelt geen bestanden uit. | core, fastapi, pydantic |
| `jwies-qt-client` | De desktopclient. Tekent enkel wat de server stuurt. | pyqt6, pyyaml |

De server draait **nooit** PyQt en de desktopclient **nooit** FastAPI. Ze delen
zelfs geen Python: beide clients bouwen hun JSON met de hand op, dus het
draadformaat is het enige contract. Wil je ze in aparte omgevingen installeren:

```powershell
$env:UV_PROJECT_ENVIRONMENT=".venv-server"; uv sync --package jwies-server
$env:UV_PROJECT_ENVIRONMENT=".venv-qt";     uv sync --package jwies-qt-client
```

De spelregels zitten volledig in `jwies-core` en nergens anders. **Beide clients
zijn thin clients**: ze weten niet eens wat kleur volgen is. De server stuurt bij
elke beurt mee welke kaarten of biedingen toegelaten zijn. Daardoor kunnen een
browser en een PyQt-venster nooit van mening verschillen over de regels. Een
test faalt wanneer er toch spellogica in een client verschijnt.

`jwies-web-client` heeft geen buildstap: gewoon HTML, CSS en ES-modules, plus een
kleine webserver om ze uit te delen. De browser is de runtime; er komt geen npm
of bundler aan te pas. Het pakket kent de spelregels niet en praat zelf nooit met
de spelserver - dat doet de browser.

De browser vindt de spelserver via, in volgorde: wat de speler zelf invulde,
`?server=...` in de adresbalk, `--game-server` (uitgeserveerd als
`/config.json`), en anders dezelfde host als de pagina. Die laatste is handig
wanneer je beide achter één reverse proxy zet.

---

## Ontwikkelen

```powershell
uv run pytest                      # alle tests
uv run pytest tests/core           # enkel de spelregels
uv run ruff check .                # stijlcontrole
uv run mypy packages/jwies-core    # typecontrole
```

Meer in [`docs/developer_documentation.md`](docs/developer_documentation.md) en
[`docs/architecture/overview.md`](docs/architecture/overview.md).

De spelregels zelf staan uitgebreid beschreven in
[`docs/game_rules.md`](docs/game_rules.md).

---

## Licenties

De code staat onder de licentie in [`LICENSE`](LICENSE).

De kaartafbeeldingen zijn **SVG-cards 2.0.1** van David Bellot, onder de LGPL.
Elke client draagt zijn eigen kopie, samen met de licentietekst:
`packages/jwies-web-client/jwies_web_client/static/assets/` (uitgeserveerd op
`/assets/svg-cards.svg`) en `packages/jwies-qt-client/jwies_qt_client/assets/`.

## Auteur

Jorrit Vander Mynsbrugge
