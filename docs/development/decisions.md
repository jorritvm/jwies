# Beslissingen

<!-- TOC -->
* [Beslissingen](#beslissingen)
  * [Algemeen](#algemeen)
  * [Taal: Engelse code, Nederlands voor de speler](#taal-engelse-code-nederlands-voor-de-speler)
  * [Instellingenmodellen](#instellingenmodellen)
  * [Asynchroon](#asynchroon)
  * [JavaScript](#javascript)
  * [Hoofdlettergebruik](#hoofdlettergebruik)
  * [Vermijd afkortingen in namen](#vermijd-afkortingen-in-namen)
  * [Namen voor bestanden en mappen](#namen-voor-bestanden-en-mappen)
<!-- TOC -->

## Algemeen

Volg zoveel mogelijk de PEP8-stijlgids. `ruff` dwingt het mechanische deel
daarvan af; draai `uv run ruff check .` voor je commit.

## Taal: Engelse code, Nederlands voor de speler

Dit is de regel die de meeste beslissingen in de codebase bepaalt.

- **Identifiers, commentaar, docstrings, logberichten, commitberichten:
  Engels.**
- **Alles wat een speler leest: Nederlands.** UI-labels, chat, foutmeldingen,
  documentatie gericht op wie een spel host, en de instellingenbestanden.

Concreet:

- Servergezind Nederlands staat in `presenter.py` en `chat.py`, als letterlijke
  tekst op de plaats die ze verstuurt, plus de handvol foutzinnen bij hun
  raise-plaatsen. Er is geen tekstcatalogus: jwies is Vlaamse wies, er is geen
  tweede taal gepland, en een sleutel-indirectie kost telkens een
  bestandslookup als je wil weten wat een zin zegt. Wordt een tweede taal ooit
  echt, dan zijn die twee modules de extractiepunten.
- Elke client bezit Nederlands **enkel** voor zijn eigen widgets:
  `jwies_web_client/static/js/labels.js` en de labeltabellen in
  `jwies_qt_client/main_window.py`. Spelzinnen (biedaankondigingen,
  contractmeldingen, de afrekening) komen kant-en-klaar van de server, dus
  staan ze maar op één plaats geschreven.
- Berichttypes en gebeurtenisnamen op de draad blijven Engels (`play_card`,
  `trick_completed`): het zijn interne identifiers, geen speler-zichtbare
  tekst.

## Instellingenmodellen

Instellingenbestanden worden met de hand bewerkt door wie een spel host, dus
zijn hun sleutels Nederlands. De modellen houden Engelse veldnamen aan en
leveren Nederlandse aliassen:

```python
dealer_may_shuffle: Annotated[
    bool,
    Field(alias="deler_mag_schudden", description="Mag de deler schudden?"),
] = False
```

- Erf van `DutchModel`, dat `populate_by_name`, `frozen` en `extra="forbid"`
  instelt. Extra's verbieden maakt van een typfout van de host een
  opstartfout in plaats van een stilzwijgend genegeerde regel.
- De `description` weerspiegelt het commentaar boven diezelfde sleutel in de
  templates.
- **Elke sleutel in een template moet voorafgegaan worden door commentaar**
  dat uitlegt wat ze doet, en bij opsomming welke waarden toegelaten zijn. Dit
  wordt afgedwongen door `tests/config/test_templates.py`, niet overgelaten
  aan discipline.

## Asynchroon

- `jwies-core` is synchroon en blijft dat. Geen `async def`, geen
  `asyncio`-import, geen timers. `tests/core/test_purity.py` dwingt dit af.
- Alles wat async is zit in `jwies-server`. Elke mutatie van een `GameEngine`
  gebeurt binnen de ene taak van die lobby, dus is er nergens een lock nodig.

## JavaScript

De webclient heeft met opzet geen buildstap en geen framework: hij wordt
rechtstreeks vanuit het Python-pakket uitgeserveerd.

- ES-modules, geen bundler, geen npm, geen transpilatie.
- 2 spaties inspringen, puntkomma's, dubbele aanhalingstekens.
- `const` standaard, `let` bij herbruik, nooit `var`.
- Voeg nooit onvertrouwde tekst toe met `innerHTML`; gebruik `textContent` of
  de `escapeHtml`-helper in `table.js`.

## Hoofdlettergebruik

PyQt zijn automatisch gegenereerde Python-bindings voor het C++ Qt-framework.
In de C++-API wordt camelCase gebruikt.
Daardoor heeft PyQt camelCase-bindings...

Alle code die aan deze repository wordt toegevoegd, moet de PEP8-stijlgids van
Python volgen.
Enkele voorbeelden:

- klassen krijgen een naam in CamelCase
- functies en variabelen krijgen een naam in snake_case
- constanten krijgen een naam in ALL_CAPS_WITH_UNDERSCORES
- gebruik 4 spaties om in te springen
- gebruik spaties rond operatoren en na komma's

Er is één uitzondering op deze regel:

- Bij het overschrijven van of werken met Qt-API-methodes volg je camelCase.

Wanneer Qt Designer gebruikt wordt om UI-bestanden te maken, gebruikt de
gegenereerde Python-code standaard camelCase voor de widgets.
Voor elke widget waarmee de applicatie interageert (bv. knoppen, labels, ...)
moet de ontwikkelaar dit aanpassen naar snake_case-namen.

## Vermijd afkortingen in namen

Een afkorting lijkt op het moment van schrijven misschien duidelijk, maar is
dat later voor anderen niet noodzakelijk.
Bv. `fi` zou geïnterpreteerd kunnen worden als 'file', 'file_info', enz.

| Toegestane afkortingen | Afgeraden afkortingen |
|-------------------------|------------------------|
| app, i, j                | fi, pos, dir, d, f      |

`i` en `j` zijn toegelaten als lusvariabelen in for-lussen, maar mogen in
andere contexten niet gebruikt worden.

## Namen voor bestanden en mappen

Vermijd `dir, d, fi, f`
Gebruik in plaats daarvan:

- `file` voor bestanden (objecten)
- `file_name` voor bestandsnamen zonder pad (str)
- `file_path` voor volledige bestandspaden, absoluut of relatief (str)


- `folder` voor mappen (objecten)
- `folder_name` voor mapnamen zonder pad (str)
- `folder_path` voor volledige mappaden, absoluut of relatief (str)

Gebruik voorvoegsels om het specifieker te maken waar nodig. Bv.:

- `image_file` voor afbeeldingsbestanden
