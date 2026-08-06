// De volledige clienttoestand.
//
// Een momentopname (snapshot) vervangt de toestand in een keer, en de server
// stuurt er een na elke verandering. Dat is de enige weg waarlangs toestand
// binnenkomt - de rest van de berichten zijn mededelingen. Daardoor is
// herverbinden gratis, en kunnen deze client en de PyQt-client onmogelijk van
// mening verschillen over wat een gebeurtenis betekende.

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
      foldingOffered: false,
      payoutSettled: false,
      folded: [],
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
      foldingOffered: snapshot.folding_offered ?? false,
      payoutSettled: snapshot.payout_settled ?? false,
      folded: snapshot.folded ?? [],
      roundNumber: snapshot.round_number ?? 0,
      screen: "table",
    });
  }

  // Enkel deze berichten veranderen iets. Al de rest die de server stuurt is
  // een mededeling - wie de slag won, welk contract er ligt, dat het spel
  // gepauzeerd is - en de momentopname die erop volgt zegt dat allemaal al.
  // Diezelfde feiten hier een tweede keer afleiden is precies hoe twee clients
  // uit elkaar gaan lopen.
  applyMessage(message) {
    const state = this.state;
    switch (message.type) {
      case "snapshot":
        this.applySnapshot(message.snapshot);
        break;

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

      // De slag op tafel. De engine haalt een slag binnen zodra ze gewonnen is,
      // dus geen enkele momentopname kan de seconden beschrijven dat ze blijft
      // liggen om bekeken te worden; deze drie overbruggen dat gat.
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
