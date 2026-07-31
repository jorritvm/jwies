// De volledige clienttoestand.
//
// Een momentopname (snapshot) vervangt de toestand in een keer; de losse
// gebeurtenissen werken ze bij voor de animatie. Daardoor is herverbinden
// gratis: er komt gewoon een nieuwe snapshot binnen.

export class Store extends EventTarget {
  constructor() {
    super();
    this.state = Store.empty();
  }

  static empty() {
    return {
      screen: "connect",
      username: null,
      lobbies: [],
      lobby: null,
      rulesets: [],
      scorings: [],
      seats: [],
      yourSeat: null,
      dealerSeat: null,
      hand: [],
      openHands: {},
      trick: [],
      lastTrick: null,
      trump: null,
      turnedTrump: null,
      contract: null,
      trickCounts: { declarers: 0, defenders: 0 },
      totals: {},
      prompt: null,
      pendingSeat: null,
      paused: false,
      missing: [],
      chat: [],
      showLastTrick: false,
      roundNumber: 0,
    };
  }

  update(changes) {
    Object.assign(this.state, changes);
    this.dispatchEvent(new CustomEvent("change"));
  }

  addChat(entry) {
    this.state.chat.push(entry);
    if (this.state.chat.length > 300) this.state.chat.shift();
    this.dispatchEvent(new CustomEvent("change"));
  }

  applySnapshot(snapshot) {
    this.update({
      lobby: snapshot.lobby,
      seats: snapshot.seats,
      yourSeat: snapshot.your_seat,
      dealerSeat: snapshot.dealer_seat,
      hand: snapshot.your_hand ?? [],
      openHands: snapshot.open_hands ?? {},
      trick: snapshot.current_trick ?? [],
      lastTrick: snapshot.last_trick,
      trump: snapshot.trump,
      turnedTrump: snapshot.turned_trump,
      contract: snapshot.contract,
      trickCounts: snapshot.trick_counts ?? { declarers: 0, defenders: 0 },
      totals: snapshot.totals ?? {},
      prompt: snapshot.prompt,
      pendingSeat: snapshot.pending_seat,
      paused: snapshot.paused,
      missing: snapshot.missing_players ?? [],
      roundNumber: snapshot.round_number ?? 0,
      screen: "table",
    });
  }

  // Elke servergebeurtenis werkt de toestand bij. De teksten zijn al
  // Nederlands: de server rendert ze, de client toont ze alleen.
  applyMessage(message) {
    const state = this.state;
    switch (message.type) {
      case "hello_ok":
        this.update({ username: message.username, rulesets: message.rulesets,
                      scorings: message.scorings });
        break;

      case "lobby_list":
        this.update({ lobbies: message.lobbies });
        break;

      case "lobby_state":
        this.update({
          lobby: message.lobby,
          screen: state.screen === "table" ? "table" : "lobby",
        });
        break;

      case "game_started":
        this.update({ screen: "table", seats: message.seats, yourSeat: message.your_seat });
        break;

      case "snapshot":
        this.applySnapshot(message.snapshot);
        break;

      case "hand_dealt":
        this.update({ hand: message.cards, trick: [], lastTrick: null });
        break;

      case "round_started":
        this.update({
          roundNumber: message.round_number,
          dealerSeat: message.dealer_seat,
          contract: null,
          trump: null,
          turnedTrump: null,
          trick: [],
          lastTrick: null,
          trickCounts: { declarers: 0, defenders: 0 },
        });
        break;

      case "trump_turned":
        this.update({ turnedTrump: message.card });
        break;

      case "trump_hidden":
        this.update({ turnedTrump: null });
        break;

      case "contract_established":
        this.update({ contract: message.contract, trump: message.contract.trump });
        break;

      case "card_played":
        this.update({
          trick: [...state.trick, { seat: message.seat, card: message.card }],
          hand:
            message.seat === state.yourSeat
              ? removeOnce(state.hand, message.card)
              : state.hand,
        });
        break;

      case "trick_completed":
        this.update({ trickCounts: message.trick_counts, lastTrick: message.cards });
        break;

      case "table_cleared":
        this.update({ trick: [] });
        break;

      case "prompt":
        this.update({ prompt: message.prompt });
        break;

      case "prompt_cleared":
        this.update({ prompt: null });
        break;

      case "round_finished":
        this.update({ totals: message.totals, prompt: null });
        break;

      case "game_paused":
        this.update({ paused: true, missing: message.missing, prompt: null });
        break;

      case "game_resumed":
        this.update({ paused: false, missing: [] });
        break;

      case "player_disconnected":
      case "player_reconnected":
      case "player_joined":
      case "player_left":
        // De lobbytoestand volgt zo; hier enkel de systeemregel in de chat.
        break;

      default:
        break;
    }

    if (message.type === "chat") {
      this.addChat({ kind: message.kind, text: message.text, sender: message.sender });
    }
  }
}

function removeOnce(list, value) {
  const index = list.indexOf(value);
  if (index < 0) return list;
  const copy = list.slice();
  copy.splice(index, 1);
  return copy;
}
