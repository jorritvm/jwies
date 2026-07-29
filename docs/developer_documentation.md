# Ontwikkelaarsdocumentatie

## Opzet

Dit is een [uv](https://docs.astral.sh/uv/)-workspace met vijf pakketten onder
`src/`. Zie [`architecture/overview.md`](architecture/overview.md) voor wat ze
doen en waarom.

```powershell
git clone https://github.com/jorritvm/jwies
cd jwies
uv sync --all-packages
```

`uv` installeert ook de juiste Pythonversie uit `.python-version`.

### Gescheiden omgevingen

De server mag nooit PyQt binnentrekken en de client nooit FastAPI. Wil je dat
ook fysiek scheiden:

```powershell
$env:UV_PROJECT_ENVIRONMENT=".venv-server"; uv sync --package jwies-server
$env:UV_PROJECT_ENVIRONMENT=".venv-qt";     uv sync --package jwies-qt-client
```

De echte garantie is de gedeclareerde afhankelijkheidsgraaf, niet de venv. Dat
wordt getest (`tests/qt/test_qt_client.py`) en kan je zelf nakijken:

```powershell
uv tree --package jwies-server --no-dev     # mag geen pyqt bevatten
uv tree --package jwies-qt-client --no-dev  # mag geen fastapi bevatten
```

## Draaien

```powershell
# server
uv run --package jwies-server jwies-server --config templates/server.yaml

# desktopclient
uv run --package jwies-qt-client jwies --username Jan

# server + vier clients ineens, voor een testpotje
.\scripts\run_dev.ps1
```

Nuttige serveropties: `--host`, `--port`, `--log-level`, `--log-file`.

## Testen

```powershell
uv run pytest                  # alles
uv run pytest tests/core       # spelregels en puntentelling (snel)
uv run pytest tests/e2e        # vier echte clients over echte websockets
uv run pytest tests/qt         # de PyQt-client
```

De testmappen volgen de pakketten:

| Map | Wat |
|---|---|
| `tests/core` | kaarten, biedladder, troel, contracten, slagen, puntentelling, de state machine |
| `tests/config` | de meegeleverde templates laden, en elke instelling heeft uitleg |
| `tests/protocol` | berichten serialiseren, en de enums lopen gelijk met de engine |
| `tests/server` | sessies, chatcommando's, de Nederlandse tekstcatalogus |
| `tests/e2e` | volledige rondes, herverbinden, en de webclient |
| `tests/qt` | stoelafbeelding, de state reducer, en het venster offscreen |

De Qt-tests draaien met `QT_QPA_PLATFORM=offscreen` en hebben dus geen scherm
nodig.

## Stijl

```powershell
uv run ruff check .
uv run ruff format .
uv run mypy src/jwies-core src/jwies-protocol
```

Zie [`style_guide/style_guide.md`](style_guide/style_guide.md).

## Iets aan de spelregels veranderen

Alle regels zitten in `src/jwies-core/`. Het is de bedoeling dat je daar kan
werken zonder ooit een server te starten: de engine is zuiver en synchroon.

- **Een instelling toevoegen**: veld in `config/ruleset.py` (Engelse naam,
  Nederlandse `alias`), commentaar in de templates, en een test in
  `tests/config`. De test `test_every_template_key_is_preceded_by_a_comment`
  faalt als je de uitleg vergeet.
- **Een contract toevoegen**: een regel in `CONTRACT_CATALOG`
  (`jwies_core/contracts.py`) en een plaats in `bieden.volgorde`. Meestal is
  daar geen enginewijziging voor nodig.
- **De puntentelling aanpassen**: `jwies_core/scoring.py`. Elke wijziging moet
  de nulsomtest overleven.

Voeg je een speler-zichtbare zin toe, dan hoort die in
`src/jwies-server/jwies_server/texts/nl.yaml`; een test controleert dat elke
sleutel die de code gebruikt ook echt bestaat, en omgekeerd.

## Een nieuw berichttype

1. Model toevoegen in `jwies_protocol/client_messages.py` of
   `server_messages.py` en opnemen in de union onderaan.
2. Afhandelen in `jwies_server/connection.py` (lobbyniveau) of
   `jwies_server/lobby.py` (spelniveau).
3. Verwerken in beide clients: `jwies_web_client/static/js/store.js` en
   `jwies_qt_client/state.py`.

Het protocol heeft een versienummer (`PROTOCOL_VERSION` in
`jwies_protocol/common.py`). Breek je de compatibiliteit, verhoog het dan; de
server weigert clients met een ander nummer met een nette Nederlandse melding.

## Afhankelijkheden

```powershell
uv add --package jwies-server <pakket>   # afhankelijkheid van een specifiek pakket
uv lock --upgrade                        # lockfile bijwerken
uv sync --all-packages                   # alles synchroniseren
```

## Versies

```powershell
uv run bump-my-version show-bump
uv run bump-my-version bump patch    # of minor / major
```

Dat past de versie in alle vijf de `pyproject.toml`-bestanden tegelijk aan,
maakt een commit en zet een git-tag.

## Op een homeserver zetten

De server is een gewone ASGI-toepassing en blijft onbeperkt draaien.

```powershell
uv run --package jwies-server jwies-server `
    --config /etc/jwies/server.yaml `
    --log-file /var/log/jwies.log
```

Zet er een reverse proxy voor als je van buitenaf wil spelen, en gebruik dan
`https`/`wss`: de webclient kiest zijn schema op basis van de pagina waarop hij
geladen is.
