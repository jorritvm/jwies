# jwies_core

De spelregels en de puntentelling, zuiver en synchroon.
De spelregels zitten volledig hier.

## Entrypoint
Geen, wordt niet standalone gerund. `jwies_server` roept `GameEngine.apply()` aan en stuurt de resulterende
gebeurtenissen naar de clients.

## Modules

| Module | Verantwoordelijkheid |
|---|---|
| `engine.py` | De state machine (`GameEngine`). `apply(seat, action)` is de enige manier om iets te veranderen; het resultaat is een lijst gebeurtenissen. |
| `events.py` | De typed acties die een speler kan nemen en de gebeurtenissen die de engine teruggeeft. |
| `cards.py` | Het kaartmodel en de kaartcode (`"AH"`, `"10S"`) die ook het draadformaat is. |
| `bidding.py` | De biedladder: welke biedingen nog mogen, gegeven de regelset en wat al geboden is. |
| `troel.py` | Detectie van een troel (drie of meer azen bij één speler). |
| `resolution.py` | Zet een afgeronde biedronde om in een contract: wie speelt, met wie, en welke troef. |
| `contracts.py` | `CONTRACT_CATALOG`: per contract hoeveel slagen het belooft, wie declareert en waar de troef vandaan komt. Data, geen code. |
| `trick.py` | `legal_moves()` (welke kaarten mogen nu) en wie een slag wint. |
| `scoring.py` | De puntentelling, per ronde en cumulatief. |
| `seats.py` | Stoelrekenkunde: absolute posities 0-3, met de klok mee. |
| `config/` | De pydantic-modellen achter de regelset- en puntenschaal-YAML's (`ruleset.py`, `scoring_scale.py`), plus het laden ervan met Nederlandse foutmeldingen (`loader.py`). |

