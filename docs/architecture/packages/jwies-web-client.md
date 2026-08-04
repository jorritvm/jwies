# jwies-web-client

De browserclient (HTML, CSS, ES-modules) plus de kleine webserver die hem
uitdeelt (wat in `static/` staat is wat de browser krijgt), inclusief de kaartenset. De browser is de runtime en praat rechtstreeks met de
spelserver over een websocket. 

<!-- TOC -->
* [jwies-web-client](#jwies-web-client)
  * [Entrypoint](#entrypoint)
  * [Python modules](#python-modules)
    * [server.py](#serverpy)
  * [JavaScript modules (`static/js/`)](#javascript-modules-staticjs)
  * [Communicatieprotocol](#communicatieprotocol)
<!-- TOC -->


## Entrypoint
**Entrypoint:** `jwies-web` (console script) → `cli.py:main`


## Python modules
### server.py

Serveert `static/` en een `/config.json` met `game_server_url`. De pagina
blijft laden terwijl de spelserver herstart of plat ligt.

## JavaScript modules (`static/js/`)

| Module | Verantwoordelijkheid |
|---|---|
| `net.js` | Websocketverbinding: reconnect met exponentiële wachttijd, biedt dezelfde naam en `resume_token` opnieuw aan. |
| `store.js` | De volledige clienttoestand. Een snapshot vervangt hem in zijn geheel; de rest van de berichten zijn mededelingen. |
| `table.js` | Tekent de tafel als zuivere functie van de toestand; rekent absolute stoelnummers om naar zuid/west/noord/oost vanuit het eigen gezichtspunt. |
| `cards.js` | Knipt kaartafbeeldingen uit `svg-cards.svg`. |
| `labels.js` | Nederlandse teksten van de widgets zelf (knoppen, koppen); spelzinnen komen van de server. |
| `main.js` | Opstarten en schermbeheer; verbindt de andere modules. |


## Communicatieprotocol
De browser opent zelf een websocket naar `jwies-server`, JSON volgens
[`protocol.md`](../protocol.md) met de hand opgebouwd en gelezen. De browser
vindt het adres via, in volgorde: wat de speler zelf invulde, `?server=...`,
`game_server_url` uit `/config.json`, en anders dezelfde host als de pagina.