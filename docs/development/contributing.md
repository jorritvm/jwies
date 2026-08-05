# Developer instructies

<!-- TOC -->
* [Developer instructies](#developer-instructies)
  * [Vereisten](#vereisten)
  * [Lokale versie opzetten](#lokale-versie-opzetten)
    * [jwies-server opzetten](#jwies-server-opzetten)
    * [jwies-qt-client opzetten](#jwies-qt-client-opzetten)
    * [jwies-web-client opzetten](#jwies-web-client-opzetten)
    * [Alles tegelijk opstarten](#alles-tegelijk-opstarten)
  * [Linting en formatting](#linting-en-formatting)
  * [Bumping](#bumping)
  * [Testing](#testing)
<!-- TOC -->

## Vereisten
- Je hebt [uv](https://docs.astral.sh/uv/) en Python 3.13 nodig.
- Je hebt een lokale kopie van de code nodig
    ```powershell
    git clone https://github.com/jorritvm/jwies
    cd jwies
    ```
- Server en client kunnen tegelijk draaien, maar in aparte vensters.

## Lokale versie opzetten

### jwies-server opzetten
- Kies je regelset:  
    Elke tafel speelt volgens een **regelset** en een **puntenschaal**. Beide zijn
    gewone YAML-bestanden waarin bij elke instelling staat wat ze doet en welke
    waarden toegelaten zijn. Kopieer een bestaand bestand onder een nieuwe naam en
    pas het aan:
    
    ```powershell
    copy config\ruleset\klassiek.yaml  config\ruleset\onze_club.yaml
    copy config\scoring\schaal_a.yaml  config\scoring\onze_punten.yaml
    ```

    Verwijs er dan naar vanuit `config\server.yaml` 

- Start de spelserver  
  ```powershell
  uv run --project jwies-server jwies-server --config config/server.yaml
  ```

- Open http://localhost:8000/healthz in een browser, je ziet dan een JSON-antwoord van de server

### jwies-qt-client opzetten
- start de client  
  ```powershell
  uv run --project jwies-qt-client jwies --username Jan --server ws://127.0.0.1:8000/ws
  ```

### jwies-web-client opzetten
- start de webserver die de browserclient uitdeelt  
  ```powershell
  uv run --project jwies-web-client jwies-web --game-server ws://127.0.0.1:8000/ws
  ```
- open http://localhost:8080 in vier browservensters


### Alles tegelijk opstarten
Als test kan je alles tegelijk opstarten dankzij:  
```powershell
.\scripts\run_dev.ps1              -> server + 4 PyQt-clients
.\scripts\run_dev.ps1 -Clients 2   -> server + 2 PyQt-clients (de rest via de browser)
.\scripts\run_dev.ps1 -ServerOnly  -> enkel de server
```

## Linting en formatting
Elk project draagt zijn eigen ruff-instellingen in zijn `pyproject.toml`, dus
lint je per project (of in één keer met `check_all.ps1` hierboven):

```powershell
cd jwies-server
uv run ruff check .
uv run ruff format .
uv run mypy jwies_core jwies_server
```

## Bumping
`bump-my-version` staat in geen enkel project als afhankelijkheid; draai het met
`uvx`. Zet eerst de output op UTF-8, anders struikelt het over de pijltjes in
zijn eigen uitvoer.

```powershell
$env:PYTHONIOENCODING = "utf-8"
uvx bump-my-version show-bump
uvx bump-my-version bump patch    # of minor / major
```

Dat past de versie in alle vier de `pyproject.toml`-bestanden tegelijk aan,
maakt een commit en zet een git-tag.

## Testing

Elk project heeft zijn eigen venv, dus je test per project:

```powershell
cd jwies-server
uv run pytest                  # alle serverkant-tests
uv run pytest tests/core       # enkel de spelregels
```

Alles in één keer (sync, ruff, pytest per project, en mypy):

```powershell
.\scripts\check_all.ps1
```

| Map | Wat |
|---|---|
| `jwies-server/tests/core` | kaarten, biedladder, troel, contracten, slagen, puntentelling, de state machine |
| `jwies-server/tests/config` | de meegeleverde configbestanden laden, en elke instelling heeft uitleg |
| `jwies-server/tests/server` | sessies, chatcommando's, de Nederlandse zinnen, en het berichtenschema |
| `jwies-server/tests/e2e` | volledige rondes, herverbinden, en of geen van beide clients achterloopt op het protocol |
| `jwies-qt-client/tests` | stoelafbeelding, de state reducer, en het venster offscreen |
| `jwies-web-client/tests` | de webclient |
| `tests` | checks die meer dan één project tegelijk nodig hebben, bv. kaart-ids die JS en Python delen |

De Qt-tests draaien met `QT_QPA_PLATFORM=offscreen`.