// Tekent de speeltafel op basis van de toestand.
//
// Elke render is een zuivere functie van de toestand naar de DOM. De server
// stuurt absolute stoelnummers 0-3 plus jouw eigen stoel; de client rekent dat
// om naar zuid/west/noord/oost vanuit jouw gezichtspunt.

import { SUIT_SYMBOL, cardElement, suitLabel } from "./cards.js";
import { LABELS, fill } from "./labels.js";

const DIRECTIONS = ["south", "west", "north", "east"];

/** Stoelnummer -> richting op het scherm, vanuit jouw stoel gezien. */
export function directionOf(seat, yourSeat) {
  if (seat === null || seat === undefined || yourSeat === null || yourSeat === undefined) {
    return "south";
  }
  return DIRECTIONS[(seat - yourSeat + 4) % 4];
}

export class TableView {
  constructor(store, actions) {
    this.store = store;
    this.actions = actions;
    this.selected = null;

    this.felt = document.getElementById("felt");
    this.trickArea = document.getElementById("trick-area");
    this.trumpArea = document.getElementById("trump-area");
    this.counter = document.getElementById("trick-counter");
    this.contractBox = document.getElementById("contract-box");
    this.bidBar = document.getElementById("bid-bar");
    this.bidOptions = document.getElementById("bid-options");
    this.actionBox = document.getElementById("action-box");
    this.scoreboard = document.getElementById("scoreboard");
    this.chatLog = document.getElementById("chat-log");
    this.pauseOverlay = document.getElementById("pause-overlay");
    this.pauseText = document.getElementById("pause-text");
    this.lastTrickButton = document.getElementById("btn-last-trick");
    this.foldBox = document.getElementById("fold-box");

    this.lastTrickButton.addEventListener("click", () => {
      const showing = this.lastTrickButton.getAttribute("aria-pressed") === "true";
      this.lastTrickButton.setAttribute("aria-pressed", String(!showing));
      this.store.update({ showLastTrick: !showing });
    });
  }

  render() {
    const state = this.store.state;
    this.renderFold(state);
    this.renderSeats(state);
    this.renderTrick(state);
    this.renderTrump(state);
    this.renderCounter(state);
    this.renderContract(state);
    this.renderPrompt(state);
    this.renderScoreboard(state);
    this.renderChat(state);
    this.renderPause(state);
  }

  // --- tafel -------------------------------------------------------------

  renderSeats(state) {
    for (const direction of DIRECTIONS) {
      const node = this.felt.querySelector(`.seat--${direction}`);
      node.querySelector(".seat-name").textContent = "";
      node.querySelector(".seat-cards").replaceChildren();
    }

    for (const seat of state.seats) {
      const direction = directionOf(seat.seat, state.yourSeat);
      const node = this.felt.querySelector(`.seat--${direction}`);
      if (!node) continue;

      const nameNode = node.querySelector(".seat-name");
      nameNode.textContent = seat.username ?? "";
      nameNode.className = "seat-name";
      if (seat.is_dealer) nameNode.classList.add("dealer");
      if (state.contract) {
        nameNode.classList.add(
          state.contract.declarers.includes(seat.seat) ? "attacker" : "defender",
        );
      }
      if (state.pendingSeat === seat.seat) nameNode.classList.add("turn");
      if (seat.username && !seat.connected) nameNode.classList.add("offline");

      const cardsNode = node.querySelector(".seat-cards");
      if (direction === "south") {
        this.renderOwnHand(cardsNode, state);
      } else {
        const open = state.openHands?.[seat.seat];
        if (open && open.length) {
          for (const code of open) cardsNode.appendChild(cardElement(code));
        } else {
          const count = this.remainingCards(state, seat.seat);
          for (let i = 0; i < count; i += 1) {
            cardsNode.appendChild(cardElement("2C", { faceDown: true }));
          }
        }
      }
    }
  }

  remainingCards(state, seat) {
    // Iedereen speelt evenveel kaarten; wie in deze slag al gespeeld heeft,
    // heeft er eentje minder.
    const base = 13 - (state.trickCounts.declarers + state.trickCounts.defenders);
    const playedThisTrick = state.trick.some((entry) => entry.seat === seat) ? 1 : 0;
    return Math.max(0, base - playedThisTrick);
  }

  renderOwnHand(container, state) {
    const playable = new Set(
      state.prompt?.kind === "play" ? state.prompt.legal_cards : [],
    );
    for (const code of state.hand) {
      const card = cardElement(code);
      if (playable.has(code)) {
        card.classList.add("playable");
        card.addEventListener("click", () => this.selectCard(code));
      } else if (state.prompt?.kind === "play") {
        card.classList.add("dimmed");
      }
      if (this.selected === code) card.classList.add("selected");
      container.appendChild(card);
    }
  }

  selectCard(code) {
    this.selected = this.selected === code ? null : code;
    this.render();
  }

  renderTrick(state) {
    this.trickArea.replaceChildren();
    const cards = state.showLastTrick && state.lastTrick ? state.lastTrick : state.trick;
    for (const entry of cards) {
      const card = cardElement(entry.card);
      card.classList.add(`pos-${directionOf(entry.seat, state.yourSeat)}`);
      this.trickArea.appendChild(card);
    }
  }

  renderTrump(state) {
    this.trumpArea.replaceChildren();
    if (state.turnedTrump) {
      const label = document.createElement("div");
      label.textContent = LABELS.trump;
      this.trumpArea.append(label, cardElement(state.turnedTrump));
    } else if (state.trump) {
      const label = document.createElement("div");
      label.innerHTML = `${LABELS.trump}<br><span style="font-size:1.6rem">${
        SUIT_SYMBOL[state.trump]
      }</span>`;
      this.trumpArea.appendChild(label);
    }
  }

  renderCounter(state) {
    if (!state.contract) {
      this.counter.textContent = "";
      return;
    }
    this.counter.textContent =
      `${LABELS.attack}: ${state.trickCounts.declarers}\n` +
      `${LABELS.defence}: ${state.trickCounts.defenders}`;
  }

  renderContract(state) {
    if (!state.contract) {
      this.contractBox.textContent = state.roundNumber
        ? fill(LABELS.round, { nummer: state.roundNumber })
        : "";
      return;
    }
    const trump = state.contract.trump
      ? suitLabel(state.contract.trump)
      : LABELS.noTrumpShort;
    this.contractBox.innerHTML =
      `<h3>${LABELS.contract}</h3>${state.contract.name} ` +
      `(${state.contract.tricks_required})<br>${LABELS.trump}: ${trump}`;
  }

  // --- wat er van jou verwacht wordt -------------------------------------

  renderPrompt(state) {
    this.bidBar.hidden = true;
    this.bidOptions.replaceChildren();
    this.actionBox.replaceChildren();

    const prompt = state.prompt;
    if (!prompt || state.paused) return;

    if (prompt.kind === "bid") {
      this.bidBar.hidden = false;
      for (const option of prompt.bid_options) {
        const button = document.createElement("button");
        button.textContent = bidLabel(option);
        button.addEventListener("click", () => this.actions.placeBid(option));
        this.bidOptions.appendChild(button);
      }
      return;
    }

    if (prompt.kind === "shuffle") {
      this.actionBox.append(
        heading(LABELS.shuffleQuestion),
        actionButton(LABELS.yes, () => this.actions.answerShuffle(true)),
        actionButton(LABELS.no, () => this.actions.answerShuffle(false)),
      );
      return;
    }

    if (prompt.kind === "cut") {
      const input = document.createElement("input");
      input.type = "number";
      input.min = String(prompt.cut_minimum);
      input.max = String(prompt.cut_maximum);
      input.value = String(Math.floor((prompt.cut_minimum + prompt.cut_maximum) / 2));
      this.actionBox.append(
        heading(
          fill(LABELS.cutQuestion, { min: prompt.cut_minimum, max: prompt.cut_maximum }),
        ),
        input,
        actionButton(LABELS.cut, () => this.actions.answerCut(Number(input.value))),
      );
      return;
    }

    if (prompt.kind === "play") {
      const button = actionButton(LABELS.playCard, () => {
        if (this.selected) {
          this.actions.playCard(this.selected);
          this.selected = null;
        }
      });
      button.disabled = !this.selected;
      this.actionBox.append(heading(LABELS.yourTurn), button);
    }
  }

  /** De knop om een verloren ronde vroegtijdig te stoppen.
   *
   * Bewust een knop naast de tafel en geen dialoogvenster: een ronde die
   * niemand nog kan winnen is precies het verkeerde moment om de tafel te
   * onderbreken. De server beslist of opgeven uberhaupt aan de orde is.
   */
  renderFold(state) {
    this.foldBox.replaceChildren();
    if (!state.foldingOffered || state.paused) return;

    const folded = state.folded ?? [];
    const mine = folded.includes(state.yourSeat);
    const button = actionButton(
      fill(mine ? LABELS.foldWaiting : LABELS.fold, { aantal: folded.length }),
      () => this.actions.fold(!mine),
    );
    button.classList.toggle("pressed", mine);
    this.foldBox.appendChild(button);
  }

  renderScoreboard(state) {
    const entries = Object.entries(state.totals ?? {});
    if (!entries.length) {
      this.scoreboard.replaceChildren();
      return;
    }
    entries.sort((a, b) => Number(b[1]) - Number(a[1]));
    const rows = entries
      .map(([name, total]) => `<tr><td>${escapeHtml(name)}</td><td>${total}</td></tr>`)
      .join("");
    this.scoreboard.innerHTML = `<h3>${LABELS.score}</h3><table>${rows}</table>`;
  }

  renderChat(state) {
    const atBottom =
      this.chatLog.scrollTop + this.chatLog.clientHeight >= this.chatLog.scrollHeight - 20;
    this.chatLog.replaceChildren();
    for (const entry of state.chat) {
      const line = document.createElement("div");
      line.className = entry.kind;
      if (entry.sender) {
        line.innerHTML =
          `<span class="who">${escapeHtml(entry.sender)}:</span> ${escapeHtml(entry.text)}`;
      } else {
        line.textContent = entry.text;
      }
      this.chatLog.appendChild(line);
    }
    if (atBottom) this.chatLog.scrollTop = this.chatLog.scrollHeight;
  }

  renderPause(state) {
    this.pauseOverlay.hidden = !state.paused;
    if (state.paused) {
      this.pauseText.textContent = fill(LABELS.waitingFor, {
        naam: state.missing.join(", "),
      });
    }
  }
}

export function bidLabel(bid) {
  const template = LABELS.bid[bid.type] ?? bid.type;
  return fill(template, { slagen: bid.tricks ?? "" });
}

function heading(text) {
  const node = document.createElement("div");
  node.textContent = text;
  return node;
}

function actionButton(text, onClick) {
  const button = document.createElement("button");
  button.textContent = text;
  button.addEventListener("click", onClick);
  return button;
}

export function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (character) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character],
  );
}
