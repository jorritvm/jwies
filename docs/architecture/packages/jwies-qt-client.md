# jwies-qt-client

De desktopclient. Een renderer: tekent wat de server stuurt en schakelt de
opties in die de server aanbiedt. 

<!-- TOC -->
* [jwies-qt-client](#jwies-qt-client)
  * [Entrypoint](#entrypoint)
  * [Modules](#modules)
  * [Communicatieprotocol](#communicatieprotocol)
<!-- TOC -->

## Entrypoint
**Entrypoint:** `jwies` (console script) → `cli.py:main`

## Modules

| Module | Verantwoordelijkheid |
|---|---|
| `cli.py` | Entrypoint: leest `--username`/`--server`, start het Qt-event loop. |
| `net.py` | Websocketverbinding via `QWebSocket` (komt met PyQt mee, dus geen tweede event loop nodig). |
| `settings.py` | Clientinstellingen (server, gebruikersnaam) als YAML - de enige lokale staat. |
| `state.py` | Platte, regelloze store: een snapshot vervangt hem in zijn geheel, gebeurtenissen duwen hem bij. Los van de widgets, dus testbaar zonder Qt. |
| `lobby_page.py` | Alles voor je aan tafel zit: verbinden en de tafellijst. Praat met de rest via signals. |
| `main_window.py` | Het hoofdvenster: tekent de tafel en routeert binnenkomende berichten. |
| `table_scene.py` | Tekent de tafel vanuit de laatste snapshot en animeert de drie slagberichten. |
| `layout.py` | Scènegeometrie: stoelposities en afmetingen. |
| `widgets.py` | Graphics items en dialogen (kaarten, knoppen). |
| `cards.py` | Kaartcode → SVG-element-id. |

De kaartenset en de iconen staan in `jwies_qt_client/assets/`. Dat is bewust een
kopie van wat de webclient uitdeelt: `test_both_clients_ship_the_same_card_sheet`
faalt zodra de twee uiteenlopen.

## Communicatieprotocol

Eén websocketverbinding met `jwies-server`, JSON volgens
[`protocol.md`](../protocol.md) - met de hand opgebouwd en gelezen.
