# Het jwies-protocol

Alles wat over de websocket gaat tussen een client en de spelserver. Versie **2**.

Dit document is het contract. De server dwingt het af met pydantic-modellen in
`jwies-server/jwies_server/protocol.py`. Beide clients bouwen hun JSON met de
hand op en lezen ze met de hand terug, wat de browserclient buildstap-vrij
houdt en de desktopclient los van de server. De *waarden* hieronder liggen dus
vast; de klassenamen zijn een implementatiedetail.

Twee tests bewaken dit document: `tests/server/test_protocol_docs.py` faalt als
een bericht of veld hier ontbreekt, en `tests/e2e/test_client_protocol_drift.py`
faalt als een client een naam gebruikt die niet meer bestaat.

## Twee soorten berichten

**Toestand.** Een momentopname (`snapshot`) is het enige wat een client in zijn
eigen toestand opneemt. De server stuurt er een naar elke stoel na elke
verandering - je vraagt er dus niet om, het is gewoon hoe de tafel eruitziet.
Voor het spel begint doen `lobby_state` en `lobby_list` hetzelfde voor de
lobbyschermen.

**Mededelingen.** Al de rest vertelt wat er net gebeurd is en draagt niets dat
een client moet onthouden. De zin staat er al in het Nederlands in; de server
rendert hem, de client toont hem.

Er zijn precies drie uitzonderingen: `card_played`, `trick_completed` en
`table_cleared`. Tussen het winnen en het oprapen van een slag liggen er vier
kaarten op tafel die de engine al binnengehaald heeft, en geen enkele
momentopname kan dat moment beschrijven. Die drie berichten overbruggen het gat,
en het zijn de enige drie die een client zelf verwerkt.

Eén mededeling draagt wel unieke gegevens: `round_finished`. De verrekening per
speler (`deltas`) staat in geen enkele momentopname.

## De envelop

Elk bericht zit in een envelop.

```json
{"v": 2, "msg": {"type": "play_card", "card": "AH"}}
```

De server antwoordt met:

```json
{"v": 2, "seq": 42, "msg": {"type": "chat", "kind": "server", "text": "Jan wint de slag."}}
```

#### `ClientEnvelope`

| veld | type | betekenis |
|---|---|---|
| `v` | int | Protocolversie. Klopt hij niet, dan weigert de server de verbinding met een `error` van code `protocol_version`. |
| `msg` | object | Het bericht zelf; `type` bepaalt de rest. |

De server leest `v` rechtstreeks uit de JSON, nog voor hij iets valideert. Dat
is met opzet: een client die een versie achterloopt stuurt ook velden die
intussen verdwenen zijn, dus eerst valideren zou "onbegrijpelijk bericht"
antwoorden op het moment dat "werk je client bij" het nuttige antwoord is. Laat
je `v` weg, dan gaat de server ervan uit dat je de huidige versie spreekt.

#### `ServerEnvelope`

| veld | type | betekenis |
|---|---|---|
| `v` | int | Protocolversie van de server. |
| `seq` | int | Loopt op per verbinding. Een gat betekent dat je iets gemist hebt; vraag dan `request_snapshot`. |
| `msg` | object | Het bericht zelf. |

## Client → server

#### `hello`

Het eerste bericht op elke verbinding. De gebruikersnaam *is* de identiteit: er
is geen login, en je komt met dezelfde naam terug aan je stoel.

| veld | type | betekenis |
|---|---|---|
| `username` | string | 2 tot 20 tekens: letters, cijfers en `_` uit gelijk welk schrift, plus de spatie, `.`, `-` en de apostrof. Minstens één letter of cijfer. Wordt genormaliseerd (NFC, zonder spaties ervoor of erna) voor hij bewaard wordt. |
| `resume_token` | string of null | Wat je bij het eerste `hello_ok` kreeg. Mag weg blijven: is de oude verbinding dood, dan volstaat de naam. |

#### `lobby_list`

Vraagt de lijst met tafels op. Geen velden.

#### `lobby_create`

| veld | type | betekenis |
|---|---|---|
| `name` | string | 1 tot 40 tekens. Moet uniek zijn op de server. |
| `ruleset` | string of null | Naam van een regelset die de server kent; `null` = de standaard. |
| `scoring` | string of null | Idem voor de puntenschaal. |
| `rng_seed` | int of null | Legt het schudden vast, zodat een spel herhaalbaar is. Voor tests en foutzoeken. |

#### `lobby_join`

| veld | type | betekenis |
|---|---|---|
| `lobby_id` | string | Uit `lobby_list` of `lobby_state`. Zit de tafel vol, dan volgt `lobby_full`. |

Het spel start vanzelf zodra de vierde speler binnen is. Er is geen apart
startbericht.

#### `lobby_leave`

Verlaat je huidige tafel. Geen velden.

#### `lobby_delete`

| veld | type | betekenis |
|---|---|---|
| `lobby_id` | string | Enkel wie de tafel aanmaakte mag ze verwijderen; een lege tafel mag iedereen opruimen. |

#### `request_snapshot`

Vraagt een verse momentopname. Geen velden. Normaal niet nodig - de server
stuurt er vanzelf een na elke verandering - maar wel na een gat in `seq`.

#### `chat_send`

| veld | type | betekenis |
|---|---|---|
| `text` | string | 1 tot 500 tekens. Begint hij met `!`, dan is het een commando; `!help` toont de lijst. |

#### `answer_shuffle`

Antwoord op een `prompt` van soort `shuffle`.

| veld | type | betekenis |
|---|---|---|
| `shuffle` | bool | Wil de deler schudden? |

#### `answer_cut`

Antwoord op een `prompt` van soort `cut`. Die prompt komt er enkel op een pak dat
geschud is: is er niet geschud, dan wordt er ook niet gecoupeerd en volgt de deal
meteen. Ga er dus niet van uit dat er na `answer_shuffle` altijd een `cut` komt.

| veld | type | betekenis |
|---|---|---|
| `count` | int | Hoeveel kaarten je afneemt, tussen `cut_minimum` en `cut_maximum` uit de prompt. |

#### `place_bid`

Antwoord op een `prompt` van soort `bid`. Stuur een van de `bid_options` terug
die je gekregen hebt - eventueel met `suit` ingevuld als het bod een kleur nodig
heeft.

| veld | type | betekenis |
|---|---|---|
| `bid` | `BidInfo` | Het bod. |

#### `play_card`

Antwoord op een `prompt` van soort `play`.

| veld | type | betekenis |
|---|---|---|
| `card` | string | Een kaartcode uit `legal_cards`. De server rekent kleur-volgen uit, niet jij. |

#### `fold`

Een verloren ronde opgeven, of dat weer intrekken. Het enige bericht dat niet op
je beurt wacht.

Enkel de **spelende partij** mag dit sturen, en enkel zolang
`snapshot.folding_offered` aan staat. Bij twee spelers moeten ze het allebei
zenden - opgeven kost de partner ook punten. Zodra de hele spelende partij
akkoord is, wordt de ronde afgerekend zoals ze er op dat moment voor staat en
begint de volgende. Zie [Opgeven](#opgeven).

| veld | type | betekenis |
|---|---|---|
| `fold` | bool | `true` = opgeven, `false` = toch doorspelen. |

## Server → client

### Toestand

#### `hello_ok`

| veld | type | betekenis |
|---|---|---|
| `username` | string | Zoals de server hem opgeslagen heeft. |
| `resume_token` | string | Bewaar dit; het maakt herverbinden ondubbelzinnig. |
| `current_lobby` | string of null | Zat je al aan een tafel? Dan volgen `lobby_state` en `snapshot` vanzelf. |
| `rulesets` | lijst van string | Welke regelsets deze server kent. |
| `scorings` | lijst van string | Welke puntenschalen deze server kent. |

#### `snapshot`

Alles wat één speler mag weten. Per ontvanger opgebouwd, nooit rondgestuurd -
hij bevat immers je hand en jouw toegelaten zetten.

| veld | type | betekenis |
|---|---|---|
| `snapshot` | `Snapshot` | Zie hieronder bij Structuren. |

#### `lobby_state`

| veld | type | betekenis |
|---|---|---|
| `lobby` | `LobbyState` | De tafel waar je nu aan zit. |

#### `lobby_list`

| veld | type | betekenis |
|---|---|---|
| `lobbies` | lijst van `LobbySummary` | Alle tafels op de server. |

### De slag op tafel

#### `card_played`

| veld | type | betekenis |
|---|---|---|
| `seat` | int | Stoel 0 tot 3. |
| `card` | string | De gespeelde kaart. |

#### `trick_completed`

| veld | type | betekenis |
|---|---|---|
| `winner_seat` | int | Wie de slag binnenhaalt. |
| `cards` | lijst van `PlayedCardInfo` | De vier kaarten, in speelvolgorde. |
| `trick_counts` | `TrickCounts` | De nieuwe stand in slagen. |

#### `table_cleared`

De slag is bekeken en mag van tafel. Geen velden. Hoe lang de slag blijft
liggen, staat in de regelset (`pauze_na_slag_seconden`).

### Mededelingen

#### `chat`

| veld | type | betekenis |
|---|---|---|
| `kind` | string | `player`, `server` of `system`. |
| `text` | string | Al Nederlands; toon hem zoals hij is. |
| `sender` | string of null | Wie het typte, of `null` als de server spreekt. |

#### `error`

| veld | type | betekenis |
|---|---|---|
| `code` | string | Zie Foutcodes. |
| `text` | string | Al Nederlands; toon hem zoals hij is. |

#### `game_started`

| veld | type | betekenis |
|---|---|---|
| `seats` | lijst van `SeatInfo` | Wie waar zit. |
| `your_seat` | int | Jouw stoel. Staat ook in elke momentopname. |

#### `round_finished`

De verrekening. Het enige bericht met gegevens die nergens anders staan.

| veld | type | betekenis |
|---|---|---|
| `tricks_made` | int | Hoeveel slagen de spelende partij haalde. |
| `made` | bool | Was dat genoeg? |
| `deltas` | object | Naam → punten deze ronde, als string. Telt op tot nul. |
| `totals` | object | Naam → totaal na deze ronde, als string. |
| `text` | string | De volledige afrekening in het Nederlands. |

Bedragen zijn strings, geen getallen: zo kan er geen komma-afronding insluipen.

#### `player_joined`, `player_disconnected`, `player_reconnected`

Drie mededelingen met dezelfde vorm.

| veld | type | betekenis |
|---|---|---|
| `username` | string | Over wie het gaat. |
| `seat` | int of null | Zijn stoel, als hij er een heeft. |

#### `player_left`

Wie de tafel verlaat, laat ook zijn stoel achter - vandaar geen `seat`.

| veld | type | betekenis |
|---|---|---|
| `username` | string | Wie weg is. |

#### `game_paused`

| veld | type | betekenis |
|---|---|---|
| `missing` | lijst van string | Op wie gewacht wordt. |
| `text` | string | Al Nederlands. |

#### `game_resumed`

| veld | type | betekenis |
|---|---|---|
| `text` | string | Al Nederlands. |

## Structuren

#### `Snapshot`

| veld | type | betekenis |
|---|---|---|
| `phase` | string | `waiting_for_shuffle`, `waiting_for_cut`, `bidding`, `playing`, `round_finished` of `game_finished`. |
| `round_number` | int | De hoeveelste ronde. |
| `multiplier` | string | Telt deze ronde dubbel? Meestal `"1"`. |
| `your_seat` | int of null | Jouw stoel, of `null` als je enkel toekijkt. |
| `dealer_seat` | int of null | Wie deelt. |
| `seats` | lijst van `SeatInfo` | Alle vier de stoelen, ook de lege. |
| `your_hand` | lijst van string | Jouw kaarten. Van niemand anders staat de hand hier. |
| `open_hands` | object | Stoel → kaarten, enkel bij miserie bloot. |
| `turned_trump` | string of null | De geblekte kaart, enkel tijdens het bieden. |
| `trump` | string of null | De troefkleur, of `null` bij zonder troef. |
| `bids` | lijst van `BidRecord` | De biedgeschiedenis van deze ronde. |
| `contract` | `ContractInfo` of null | Wat er gespeeld wordt. |
| `current_trick` | lijst van `PlayedCardInfo` | Wat er nu op tafel ligt. |
| `last_trick` | lijst van `PlayedCardInfo` of null | De vorige slag, om te tonen. |
| `trick_counts` | `TrickCounts` | De stand in slagen. |
| `totals` | object | Naam → totaal in punten, als string. |
| `pending_seat` | int of null | Wie aan zet is. |
| `prompt` | `Prompt` of null | Wat er van *jou* verwacht wordt. Alleen ingevuld als jij aan zet bent. |
| `paused` | bool | Wacht de tafel op iemand? |
| `missing_players` | lijst van string | Op wie dan. |
| `folding_offered` | bool | Mag **jij** nu opgeven? Enkel aan bij de spelende partij. Zie [Opgeven](#opgeven). |
| `payout_settled` | bool | Kost opgeven niets? `false` = de boete loopt per ontbrekende slag. |
| `folded` | lijst van int | Welke stoelen al opgegeven hebben. Zodra de hele spelende partij er staat, stopt de ronde. |

#### `Prompt`

Wat de server van jou verwacht, mét de toegelaten zetten erbij. Geen enkele
client hoeft zelf uit te rekenen wat kleur volgen betekent of welke biedingen
nog mogen.

| veld | type | betekenis |
|---|---|---|
| `kind` | string | `shuffle`, `cut`, `bid` of `play`. |
| `bid_options` | lijst van `BidInfo` | Bij `bid`: precies wat je mag zeggen. |
| `legal_cards` | lijst van string | Bij `play`: precies wat je mag leggen. |
| `cut_minimum` | int | Bij `cut`: ondergrens. |
| `cut_maximum` | int | Bij `cut`: bovengrens. |

#### `SeatInfo`

| veld | type | betekenis |
|---|---|---|
| `seat` | int | 0 tot 3. |
| `username` | string of null | `null` bij een lege stoel. |
| `connected` | bool | Is die speler online? |
| `is_dealer` | bool | Deelt hij deze ronde? |

#### `BidInfo`

| veld | type | betekenis |
|---|---|---|
| `type` | string | `pass`, `ask`, `join`, `alone`, `abondance`, `misere`, `misere_ouverte`, `troel`, `solo`, `solo_slim` of `pico`. |
| `tricks` | int of null | Hoeveel slagen beloofd worden, waar dat van toepassing is. |
| `suit` | string of null | `C`, `D`, `H` of `S`, of `null` voor zonder troef. |

#### `BidRecord`

| veld | type | betekenis |
|---|---|---|
| `seat` | int | Wie bood. |
| `bid` | `BidInfo` | Wat hij bood. |
| `announcement` | string | De Nederlandse zin, bv. `"Jan: IK GA HARTEN VRAGEN"`. |

#### `ContractInfo`

| veld | type | betekenis |
|---|---|---|
| `key` | string | Machinenaam, bv. `abondance_10`. |
| `name` | string | Nederlandse naam om te tonen. |
| `tricks_required` | int | Hoeveel slagen er gehaald moeten worden. |
| `declarers` | lijst van int | De spelende partij; de rest verdedigt. |
| `trump` | string of null | Troefkleur, of `null` bij zonder troef. |

#### `PlayedCardInfo`

| veld | type | betekenis |
|---|---|---|
| `seat` | int | Wie de kaart legde. |
| `card` | string | Welke kaart. |

#### `TrickCounts`

| veld | type | betekenis |
|---|---|---|
| `declarers` | int | Slagen voor de spelende partij. |
| `defenders` | int | Slagen voor de verdediging. |

#### `LobbyState`

| veld | type | betekenis |
|---|---|---|
| `id` | string | Sleutel voor `lobby_join` en `lobby_delete`. |
| `name` | string | Zoals de speler hem noemde. |
| `host` | string of null | Wie de tafel aanmaakte. |
| `ruleset` | string | Welke regelset er geldt. |
| `scoring` | string | Welke puntenschaal er geldt. |
| `status` | string | `waiting`, `running`, `paused`, `finished` of `broken`. |
| `members` | lijst van `LobbyMember` | Wie er aan tafel zit. |

#### `LobbyMember`

| veld | type | betekenis |
|---|---|---|
| `username` | string | Wie. |
| `seat` | int of null | Welke stoel. |
| `connected` | bool | Online? |
| `is_host` | bool | Heeft hij de tafel aangemaakt? |

#### `LobbySummary`

Eén regel in de tafellijst.

| veld | type | betekenis |
|---|---|---|
| `id` | string | Sleutel voor `lobby_join`. |
| `name` | string | Naam van de tafel. |
| `ruleset` | string | Welke regelset. |
| `scoring` | string | Welke puntenschaal. |
| `status` | string | Zie `LobbyState.status`. |
| `players` | int | Hoeveel spelers er zitten. |
| `seats_free` | int | Hoeveel stoelen nog vrij zijn. |

## Opgeven

De spelende partij kan een verloren ronde opgeven. De kaarten worden dan
opgeraapt zoals ze liggen en de volgende ronde begint.

Opgeven betekent: **alle resterende slagen gaan naar de tegenpartij**. De ronde
wordt dus afgerekend op de slagen die de spelende partij op dat moment heeft,
en dat is het slechtste resultaat dat ze nog kon halen. Daarom hoeft de
tegenpartij niets goed te keuren - zij kan er nooit op achteruitgaan.

`folding_offered` staat aan wanneer deze drie dingen kloppen:

1. de regelset laat het toe (`opgeven_toegelaten`, standaard aan),
2. het contract kan niet meer gehaald worden, en
3. jij hoort bij de spelende partij.

Of opgeven ook *gratis* is, staat los daarvan, in `payout_settled`. De
solocontracten (solo, solo slim, miserie, miserie op tafel, abondance) kosten
bij verlies een **vast** bedrag - zie de kolom "Mislukt" in hoofdstuk 7.2 van
[de spelregels](../game/rules.md) - dus daar verandert opgeven niets aan de
afrekening. De duocontracten (vragen & meegaan, alleen gaan, troel) betalen per
ontbrekende slag: daar kost elke weggegeven slag punten, en `payout_settled`
staat op `false` zodat de client kan waarschuwen. Een tafel die dat verschil
niet wil, zet `per_slag_tekort: 0` bij die contracten.

Bij een contract met twee spelers moeten ze het **allebei** sturen: opgeven kost
de partner ook punten. `folded` bevat de stoelen die al opgegeven hebben en is
geen geheim - iedereen ziet dezelfde stand van zaken. Een stem kan ingetrokken
worden met `fold: false` zolang de ronde loopt.

## Kaartcodes

Waarde plus kleur, zonder scheidingsteken: `2` tot en met `10`, of `J`, `Q`,
`K`, `A`, gevolgd door `C` (klaveren), `D` (koeken), `H` (harten) of `S`
(schoppen). Dus `AH`, `10S`, `QD`. De server weigert alles wat daar niet aan
voldoet.

## Foutcodes

Elke `error` draagt een code én een Nederlandse `text`. Toon de tekst; schakel
op de code alleen als je er iets bijzonders mee doet.

| code | wanneer |
|---|---|
| `protocol_version` | Je `v` klopt niet met die van de server. De verbinding gaat dicht. |
| `username_taken` | Die naam is in gebruik door iemand die online is. |
| `username_invalid` | De naam voldoet niet aan de regels hierboven. De tekst zegt welke. De verbinding gaat dicht. |
| `not_in_lobby` | Je stuurde iets dat een tafel veronderstelt. |
| `lobby_full` | Alle vier de stoelen zijn bezet. |
| `lobby_not_found` | Die tafel bestaat niet (meer). |
| `lobby_exists` | Er is al een tafel met die naam. |
| `not_host` | Alleen wie de tafel aanmaakte mag dat. |
| `illegal_move` | De zet mag niet volgens de regels of de fase. |
| `game_paused` | Er wordt op een speler gewacht. Chat en `request_snapshot` blijven wel werken. |
| `game_not_running` | Er is nog geen spel bezig aan deze tafel. |
| `unknown_ruleset` | Die regelset kent de server niet. |
| `unknown_scoring` | Die puntenschaal kent de server niet. |
| `bad_message` | Onleesbaar of onbekend bericht. |
| `internal` | Er ging iets mis aan de serverkant. |

## Een ronde, van begin tot eind

```
→ hello {username}
← hello_ok {resume_token, rulesets, scorings}
← chat "Welkom Jan!"

→ lobby_list
← lobby_list {lobbies}

→ lobby_create {name, ruleset, scoring}
← lobby_state
   ... drie andere spelers doen lobby_join ...
← chat "Iedereen zit klaar. Het spel begint!"
← game_started {seats, your_seat}
← chat "Ronde 1. De deler is Korneel."
← chat "Korneel, wil je de kaarten schudden?"
← snapshot        (de deler krijgt prompt {kind: shuffle}, de rest niet)

→ answer_shuffle {shuffle: false}
← snapshot        (het openingspak is geschud, dus toch een prompt {kind: cut}
                   voor wie rechts van de deler zit; op een ongeschud pak wordt
                   er niet gecoupeerd en volgt de deal meteen)
→ answer_cut {count: 12}
← chat "De geblekte troefkaart is AH."
← snapshot        (prompt {kind: bid, bid_options: [...]})

→ place_bid {bid}
← chat "Jan: IK GA HARTEN VRAGEN"
← snapshot
   ... tot het contract rond is ...
← chat "Jan en Piet spelen samen vragen en meegaan (8 slagen) met harten als troef."
← snapshot        (prompt {kind: play, legal_cards: [...]})

→ play_card {card}
← card_played
   ... vier keer ...
← trick_completed + chat "Piet wint de slag."
   ... pauze ...
← table_cleared
← snapshot
   ... dertien slagen ...
← round_finished + chat met de puntentelling
← snapshot        (de volgende ronde is al begonnen)
```
