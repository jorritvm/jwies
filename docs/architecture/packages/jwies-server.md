# jwies-server

De headless spelserver: spelregels ([`jwies_core`](jwies-core.md)), lobby's,
sessies, chat, websockets en het berichtenschema. `jwies-web-client` deelt de
statische bestanden uit. 

De clients zijn thin clients. De server stuurt bij elke beurt mee welke kaarten of biedingen
toegelaten zijn, en de clients tekenen wat binnenkomt.

<!-- TOC -->
* [jwies-server](#jwies-server)
  * [Entrypoint](#entrypoint)
  * [Modules](#modules)
  * [Communicatieprotocol](#communicatieprotocol)
  * [Wegvallen en terugkomen](#wegvallen-en-terugkomen)
  * [Iets aan de spelregels veranderen](#iets-aan-de-spelregels-veranderen)
  * [Een nieuw berichttype](#een-nieuw-berichttype)
  * [Ruimte voor een AI-speler](#ruimte-voor-een-ai-speler)
<!-- TOC -->

## Entrypoint
**Entrypoint:** `jwies-server` (console script) → `cli.py:main`

## Modules

| Module | Verantwoordelijkheid |
|---|---|
| `cli.py` | Entrypoint: leest de CLI-argumenten en `server.yaml`, start `app.py`. |
| `app.py` | De FastAPI-applicatie: het `/ws`-endpoint plus read-only HTTP voor health checks en de lobbylijst. |
| `config.py` | Het serverconfiguratiemodel (`server.yaml`). |
| `connection.py` | Eén websocketverbinding: leestaak, schrijftaak, en de `hello`-handshake. |
| `sessions.py` | Identiteit en herverbinden: de gebruikersnaam is de sleutel, een `resume_token` maakt de normale reconnect ondubbelzinnig. |
| `lobby_manager.py` | Lobby's aanmaken, joinen, oplijsten en opruimen. |
| `lobby.py` | Eén lobby (`LobbyRuntime`): tafel, spelers en het lopende spel. Alle enginemutatie gebeurt in één asyncio-taak gevoed door één inbox-queue. |
| `agents.py` | De `PlayerAgent`-abstractie: een websocketverbinding is één producent op de inbox-queue, een toekomstige AI zou een tweede zijn. |
| `snapshot.py` | Bouwt de per-stoel `Snapshot` - een zuivere functie van tafel, bezetting, engine en presenter. |
| `presenter.py` | Zet engine-gebeurtenissen om in protocolberichten met Nederlandse tekst. Samen met `chat.py` de enige plek die speler-zichtbare zinnen maakt. |
| `chat.py` | Chatcommando's (`!help`, `!score`, ...), zelfregistrerend zodat `!help` nooit achterloopt. |
| `protocol.py` | De pydantic-modellen voor elk bericht dat over de socket gaat - het contract, gedocumenteerd in [`protocol.md`](../protocol.md). |

## Communicatieprotocol

Websockets met JSON, aan beide clients identiek: zie
[`protocol.md`](../protocol.md) voor elk bericht en veld. Roept
`jwies_core.GameEngine` rechtstreeks aan (in-process, geen netwerk ertussen).

## Wegvallen en terugkomen

De gebruikersnaam is de sleutel. Bij het eerste contact krijgt een speler een
`resume_token`; komt hij terug met dezelfde naam, dan krijgt hij zijn stoel
terug.

```
VERBONDEN --(socket dicht)--> WEG
    de engine wordt NIET aangeraakt: pending() wijst nog naar wie moet
    lobby.status = PAUSED, iedereen krijgt game_paused + een nieuwe snapshot
WEG --(hello, zelfde naam)--> VERBONDEN
    hello_ok -> lobby_state -> snapshot   (volledige resync)
    is niemand meer weg: game_resumed + iedereen een nieuwe snapshot
WEG --(lobby_leave, of de lobby wordt opgeruimd)--> stoel vrij
```

Een stoel komt niet vanzelf vrij: het spel blijft wachten. Wie weg is, blijft
zijn stoel houden zolang de lobby bestaat.

Omdat `pending()` idempotent is, staat de openstaande beurt gewoon weer in de
volgende momentopname. De server houdt nooit bij dat hij iemand al iets gevraagd
heeft, en hoeft dus ook niets te herstellen.

Tijdens een pauze blijven chat, `request_snapshot` en `ping` werken; al de rest
antwoordt met `game_paused`.

## Iets aan de spelregels veranderen

Alle regels zitten in `jwies-server/jwies_core/`. De engine is zuiver en
synchroon: je kan er werken zonder een server te starten.

- **Een instelling toevoegen**: veld in `config/ruleset.py` (Engelse naam,
  Nederlandse `alias`), commentaar in de configbestanden, en een test in
  `tests/config`. De test `test_every_template_key_is_preceded_by_a_comment`
  faalt als je de uitleg vergeet.
- **Een contract toevoegen**: een regel in `CONTRACT_CATALOG`
  (`jwies_core/contracts.py`) en een plaats in `bieden.volgorde`.
- **De puntentelling aanpassen**: `jwies_core/scoring.py`. Elke wijziging moet
  de nulsomtest overleven.

Voeg je een speler-zichtbare zin toe, dan schrijf je die gewoon uit in
`presenter.py` of `chat.py` - dat zijn de enige twee plaatsen die zinnen maken.
Zie [decisions.md](decisions.md) voor de afweging.

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
3. Beschrijven in [`architecture/protocol.md`](../architecture/protocol.md),
   met een `#### `naam``-kop en een tabelrij per veld.
   `tests/server/test_protocol_docs.py` faalt tot je dat doet - dat is de
   bedoeling.
4. Tonen in beide clients. Alleen de drie slagberichten mogen toestand
   veranderen; al de rest hoort in de chat of in een melding thuis.

Verwijder je iets, of hernoem je een veld, dan is
`tests/e2e/test_client_protocol_drift.py` wat merkt dat een client is blijven
staan. Breek je de compatibiliteit, verhoog dan `PROTOCOL_VERSION` op alle drie
de plaatsen (zie hieronder).

Het versienummer staat op drie plaatsen, elk project houdt zijn eigen kopie
bij: `PROTOCOL_VERSION` in `jwies_server/protocol.py`, en als los getal in
`jwies_qt_client/net.py` en `js/net.js`. Vergeet je er een, dan weigert de
server die client met een nette Nederlandse melding - de envelop zelf negeert
onbekende velden juist zodat een oude client tot aan die melding geraakt.
Vergeet je [`architecture/protocol.md`](../architecture/protocol.md), dan faalt
`test_the_documented_version_matches_the_code`.


## Ruimte voor een AI-speler

`LobbyRuntime` haalt berichten uit een wachtrij zonder onderscheid te maken
tussen producenten (`agents.py`). Een `WebsocketAgent` is een producent op die
wachtrij; een AI-speler zou het `PlayerAgent`-protocol implementeren en op
diezelfde wachtrij produceren. Een fabriek, entry point of instelling volgt
zodra er een eerste echte agent is om op te ontwerpen.
