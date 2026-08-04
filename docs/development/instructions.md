# Installatie instructies

<!-- TOC -->
* [Installatie instructies](#installatie-instructies)
  * [Development](#development)
    * [Vereisten](#vereisten)
    * [jwies-server opzetten](#jwies-server-opzetten)
    * [jwies-qt-client opzetten](#jwies-qt-client-opzetten)
    * [jwies-web-client opzetten](#jwies-web-client-opzetten)
    * [Alles tegelijk opstarten](#alles-tegelijk-opstarten)
    * [Testing](#testing)
    * [Linting en formatting](#linting-en-formatting)
    * [Bumping](#bumping)
  * [Production](#production)
    * [jwies-server](#jwies-server)
    * [jwies-qt-client](#jwies-qt-client)
    * [jwies-web-client](#jwies-web-client)
<!-- TOC -->

## Development
### Vereisten
- Je hebt [uv](https://docs.astral.sh/uv/) en Python 3.13 nodig.
- Je hebt een lokale kopie van de code nodig
    ```powershell
    git clone https://github.com/jorritvm/jwies
    cd jwies
    ```
- Server en client kunnen tegelijk draaien, maar in aparte vensters.


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

- Open http://localhost:8000 in een browser, je ziet dan een JSON-antwoord van de server

### jwies-qt-client opzetten
- start de client  
  ```powershell
  uv run --project jwies-qt-client jwies --username Jan --server ws://127.0.0.1:8000/ws
  ```

### jwies-web-client opzetten
- start de spelserver   
  ```powershell
  uv run --project jwies-web-client jwies-web --game-server ws://127.0.0.1:8000/ws
  ```
- open http://localhost:8080 in vier browservensters


### Alles tegelijk opstarten
Als test kan je alles tegelijk opstarten dankzij:  
```powershell
.\scripts\run_dev.ps1
```

### Testing

```powershell
cd jwies-server
uv run pytest                  # alle serverkant-tests
uv run pytest tests/core       # enkel de spelregels
```

| Map | Wat |
|---|---|
| `jwies-server/tests/core` | kaarten, biedladder, troel, contracten, slagen, puntentelling, de state machine |
| `jwies-server/tests/config` | de meegeleverde configbestanden laden, en elke instelling heeft uitleg |
| `jwies-server/tests/server` | sessies, chatcommando's, de Nederlandse zinnen, en het berichtenschema |
| `jwies-server/tests/e2e` | volledige rondes, herverbinden, en of geen van beide clients achterloopt op het protocol |
| `jwies-qt-client/tests` | stoelafbeelding, de state reducer, en het venster offscreen |
| `jwies-web-client/tests` | de webclient |
| `integration-tests` | checks die meer dan één project tegelijk nodig hebben, bv. kaart-ids die JS en Python delen |

De Qt-tests draaien met `QT_QPA_PLATFORM=offscreen`.

### Linting en formatting
```powershell
uv run ruff check .
uv run ruff format .
cd jwies-server; uv run mypy jwies_core jwies_server; cd ..
```

### Bumping
```powershell
uv run bump-my-version show-bump
uv run bump-my-version bump patch    # of minor / major
```

Dat past de versie in alle vier de `pyproject.toml`-bestanden tegelijk aan,
maakt een commit en zet een git-tag.


## Production
### jwies-server
De server is een gewone ASGI-toepassing en blijft onbeperkt draaien.

```powershell
uv run --package jwies-server jwies-server `
    --config /etc/jwies/server.yaml `
    --log-file /var/log/jwies.log
```

Om online te spelen zonder netwerkproblemen zijn meerdere mogelijkheden:
- open poort 8000 in je firewall
- zet een reverse proxy op

> todo: docker

### jwies-qt-client
> todo
 
### jwies-web-client
> todo
