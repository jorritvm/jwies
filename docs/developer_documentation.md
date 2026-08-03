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
# spelserver (websockets, poort 8000)
uv run --package jwies-server jwies-server --config templates/server.yaml

# browserclient (statische bestanden, poort 8080)
uv run --package jwies-web-client jwies-web --game-server ws://127.0.0.1:8000/ws

# desktopclient
uv run --package jwies-qt-client jwies --username Jan

# alles ineens, voor een testpotje
.\scripts\run_dev.ps1
```

Twee servers, met opzet gescheiden: `jwies-server` speelt het spel en deelt geen
bestanden uit, `jwies-web` deelt bestanden uit en kent het spel niet. Zo blijft
de pagina laden terwijl je de spelserver herstart, en hoeft de webclient niet
mee opnieuw uitgerold te worden wanneer de spelregels veranderen.

Nuttige opties: `--host`, `--port`, `--log-level`, `--log-file` (spelserver);
`--host`, `--port`, `--game-server`, `--log-level` (webclient).

Zet je beide achter één reverse proxy op hetzelfde adres, laat `--game-server`
dan weg: de pagina valt dan terug op zijn eigen host.

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
| `tests/server` | sessies, chatcommando's, de Nederlandse zinnen, en het berichtenschema |
| `tests/e2e` | ook: of geen van beide clients achterloopt op het protocol |
| `tests/e2e` | volledige rondes, herverbinden, en de webclient |
| `tests/qt` | stoelafbeelding, de state reducer, en het venster offscreen |

De Qt-tests draaien met `QT_QPA_PLATFORM=offscreen` en hebben dus geen scherm
nodig.

## Stijl

```powershell
uv run ruff check .
uv run ruff format .
uv run mypy packages/jwies-core packages/jwies-server
```

Zie [`style_guide/style_guide.md`](style_guide/style_guide.md).

## Iets aan de spelregels veranderen

Alle regels zitten in `packages/jwies-core/`. Het is de bedoeling dat je daar kan
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

Voeg je een speler-zichtbare zin toe, dan schrijf je die gewoon uit in
`presenter.py` of `chat.py` - dat zijn de enige twee plaatsen die zinnen mogen
maken. Er is bewust geen tekstcatalogus: zie de [stijlgids](style_guide/style_guide.md).

## Een nieuw berichttype

Vraag eerst of je er wel een nodig hebt. Draagt het bericht toestand, dan hoort
het in `Snapshot` en niet in een nieuw berichttype: de momentopname is de enige
weg waarlangs toestand bij een client komt, en een veld erbij is werk op een
plaats in plaats van drie.

Is het echt een mededeling:

1. Model toevoegen in `jwies_server/protocol.py` en opnemen in de union
   onderaan. Een zet van een speler erft van `GameAction` en vertaalt zichzelf
   via `to_action()`.
2. Afhandelen in `jwies_server/connection.py` (lobbyniveau) of
   `jwies_server/lobby.py` (spelniveau).
3. Beschrijven in [`protocol.md`](protocol.md), met een `#### `naam``-kop en een
   tabelrij per veld. `tests/server/test_protocol_docs.py` faalt tot je dat doet
   - dat is de bedoeling.
4. Tonen in beide clients. Alleen de drie slagberichten mogen toestand
   veranderen; al de rest hoort in de chat of in een melding thuis.

Verwijder je iets, of hernoem je een veld, dan is
`tests/e2e/test_client_protocol_drift.py` wat merkt dat een client is blijven
staan. Breek je de compatibiliteit, verhoog dan `PROTOCOL_VERSION` op alle drie
de plaatsen (zie hieronder).

Het versienummer staat op drie plaatsen, want de clients importeren niets van de
server: `PROTOCOL_VERSION` in `jwies_server/protocol.py`, en als los getal in
`jwies_qt_client/net.py` en `js/net.js`. Vergeet je er een, dan weigert de
server die client met een nette Nederlandse melding - de envelop zelf negeert
onbekende velden juist zodat een oude client tot aan die melding geraakt. Vergeet
je `docs/protocol.md`, dan faalt `test_the_documented_version_matches_the_code`.

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
