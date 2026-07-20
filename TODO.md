# TODO
- set up best practice runtime configuration in pycharm
- revise architecture and architecture documentation
- align codebase with the style guide
- fix issues listed on GH
- implement score keeping (see todo in controller_table.process_game)

# DONE (2026-07-19)
- feature: "Toon laatste slag" (show last trick) toggle button
- feature: per-team trick counter in the top left corner of the playing field
- fix: dealer's own trump card is elevated in hand instead of drawn as a duplicate
- add installation instructions using 'uv' in the README.md file
- verify relative path resolution (relative to project root via src/paths.py)
- verify import resolution (relative to src/)
- upgrade to pyqt6 (enums, exec_, QAction/QtSvgWidgets moves, errorOccurred)
- add type hints
- feature: color player names per team once teams are formed
- feature: GM chat message on invalid move
- bugfix: dealer + first bidder now advance after each completed round

# info from fable
  Things I deliberately did not touch (local-rules territory)                                                                                         
                                                                                                                                                      
  - Trull partner selection: with two players each holding exactly one ace, the last one iterated becomes trull2 — you may want "first ace left of the
  trull player" or the heart-ace holder.                                                                                                              
  - "Alone" wins at ≥5 tricks and trull at ≥8 regardless of the trull-8/9 setting in process_game — plausible, but variant-dependent.                 
  - Trull-8 first card: if the forced starter holds no trump at all, the "highest trump" check falls back to their highest card overall — I don't know
  the correct local rule there.                                                                                                                       
  - Score keeping is still # todo: implement — the points settings exist but are never applied, and "Toon laatste slag" is a dead button.             
                                                                                                                                                      
  My assessment, and a take on v2                                                                                                                     
                                                                                                                                                      
  Honestly: for a hobby project this is a reasonable design. Server-authoritative game state with thin clients and need-to-know information flow is   
  the correct architecture for a card game, and many amateur implementations get that wrong. The code reads fine; its problems are concentration of   
  state and protocol fragility, not structure.                                                                                                        
                                                                                                                                                      
  On HTTP/REST: no — REST would be a step backwards. A card game is stateful, session-based, and server-push-driven ("it's your turn", "X played a    
  card"); REST is stateless request/response, so you'd end up polling or bolting on webhooks. The thing actually worth replacing is not the transport 
  but the framing: hand-rolled QDataStream uint16-framed messages with stringly-typed "IPLAY"/"CUT" payloads and manual split(",") parsing is the most
  fragile part of the codebase (a version-pinned binary format that even ties your protocol to Qt). For v2 I'd use WebSockets carrying JSON (or       
  msgpack): still push-based and connection-oriented, but self-describing, debuggable with any tooling, language-agnostic, and it opens the door to a 
  browser client — which is a big deal, because "install this PyQt app" is the main obstacle to actually playing with four friends.                   
                                                                                                                                                      
  Concretely for v2:                                                                                                                                  
                                                                                                                                                      
  1. Extract the game engine from Qt entirely. The biggest issue today is that all whist logic lives inside GUI classes wired to sockets — Table needs
  a Controller for chat, Player (client) needs a QGraphicsScene to exist. Make a pure-Python jwies-core package (game state machine, bid ladder,      
  trick rules, scoring) with zero Qt imports. That instantly makes the rules unit-testable — the absence of tests is why bugs like the seat_to_bid    
  drift and the soloslim crash survived; every rule variant in controller.ini is a test case waiting to be written.                                   
  2. Model the domain with types instead of strings. "abon10"/"Hearts"/["ask", suit, player] triples spread across three parallel lists is where most 
  of the current bugs came from. Use enums + dataclasses (Bid(action=BidAction.ABONDANCE, tricks=10, suit=Suit.HEARTS, player=…)) and the 100-line    
  divide_teams if-ladder collapses into a table. I'd also drop pydealer (unmaintained since ~2015) for a 50-line Card/Deck of your own.               
  3. Server: plain asyncio + websockets (or FastAPI if you want a lobby/join-by-code page too). No Qt on the server — it doesn't need a GUI; a log
  file beats the current textbox.
  4. Client: keep PyQt6 if you enjoy it (the QGraphicsScene card table is genuinely nice), or go browser-based to eliminate installation friction.
  Either way the client should be a dumb renderer of server state snapshots rather than mirroring game logic (amount_of_aces_on_hand client-side is a
  smell).
  5. Repo structure: src/jwies/{core,server,client} as a proper installable package with [project.scripts] entry points (uv run jwies-server), pytest
  for core, and ruff + mypy in pre-commit — the type hints we just added will start paying for themselves there.
  6. Protocol hygiene: version field in the handshake, and an explicit message schema module shared by both sides instead of string literals scattered
  through two files.
  
  If you want, next steps I'd suggest: implement scoring (the settings are all there), or turn my scratchpad integration test into a proper tests/
  file so the game loop stays verifiable.
