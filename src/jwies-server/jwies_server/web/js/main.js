// Opstarten en schermbeheer.

import { cardElement, loadDeck, SUIT_SYMBOL } from "./cards.js";
import { LABELS, fill } from "./labels.js";
import { Connection } from "./net.js";
import { Store } from "./store.js";
import { TableView, bidLabel, escapeHtml } from "./table.js";

const store = new Store();
const connection = new Connection();

const screens = {
  connect: document.getElementById("screen-connect"),
  lobby: document.getElementById("screen-lobby"),
  table: document.getElementById("screen-table"),
};
const statusLine = document.getElementById("status-line");

const actions = {
  placeBid(option) {
    if (needsSuit(option)) {
      chooseSuit(option.type === "solo").then((suit) => {
        if (suit !== null) connection.send("place_bid", { bid: { ...option, suit } });
      });
      return;
    }
    connection.send("place_bid", { bid: option });
  },
  playCard(card) {
    connection.send("play_card", { card });
  },
  answerShuffle(shuffle) {
    connection.send("answer_shuffle", { shuffle });
  },
  answerCut(count) {
    connection.send("answer_cut", { count });
  },
};

const table = new TableView(store, actions);

// --- schermen ----------------------------------------------------------------

function showScreen(name) {
  for (const [key, node] of Object.entries(screens)) {
    node.hidden = key !== name;
  }
}

store.addEventListener("change", () => {
  const state = store.state;
  showScreen(state.screen);
  if (state.screen === "lobby") renderLobbies(state);
  if (state.screen === "table") table.render();
});

// --- verbinden ---------------------------------------------------------------

const usernameInput = document.getElementById("input-username");
const connectError = document.getElementById("connect-error");

document.getElementById("btn-connect").addEventListener("click", () => {
  const username = usernameInput.value.trim();
  if (!/^[A-Za-z0-9_\- ]{2,20}$/.test(username)) {
    connectError.textContent = LABELS.nameRequired;
    connectError.hidden = false;
    return;
  }
  connectError.hidden = true;
  statusLine.textContent = LABELS.connecting;
  connection.connect(username);
});

usernameInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") document.getElementById("btn-connect").click();
});

connection.addEventListener("closed", () => {
  statusLine.textContent = LABELS.disconnected;
});

connection.addEventListener("message", (event) => {
  const message = event.detail;
  store.applyMessage(message);

  switch (message.type) {
    case "hello_ok":
      statusLine.textContent = fill(LABELS.connected, { naam: message.username });
      fillSelect("select-ruleset", message.rulesets);
      fillSelect("select-scoring", message.scorings);
      if (!message.current_lobby) {
        store.update({ screen: "lobby" });
        connection.send("lobby_list", {});
      }
      break;

    case "error":
      handleError(message);
      break;

    case "player_joined":
    case "player_left":
    case "player_disconnected":
    case "player_reconnected":
      connection.send("lobby_list", {});
      break;

    default:
      break;
  }
});

function handleError(message) {
  if (message.code === "username_taken" || message.code === "username_invalid") {
    connection.disconnect();
    Connection.forget();
    connectError.textContent = message.text;
    connectError.hidden = false;
    store.update({ screen: "connect" });
    return;
  }
  // Alle andere fouten zijn al Nederlands en horen thuis in de chat.
  store.addChat({ kind: "system", text: message.text });
}

// --- lobby -------------------------------------------------------------------

function fillSelect(id, values) {
  const select = document.getElementById(id);
  select.replaceChildren();
  for (const value of values ?? []) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
}

document.getElementById("btn-create").addEventListener("click", () => {
  const name = document.getElementById("input-lobby-name").value.trim();
  if (!name) {
    store.addChat({ kind: "system", text: LABELS.lobbyNameRequired });
    return;
  }
  connection.send("lobby_create", {
    name,
    ruleset: document.getElementById("select-ruleset").value || null,
    scoring: document.getElementById("select-scoring").value || null,
  });
});

function renderLobbies(state) {
  const list = document.getElementById("lobby-list");
  const empty = document.getElementById("lobby-empty");
  list.replaceChildren();
  empty.hidden = state.lobbies.length > 0;

  for (const lobby of state.lobbies) {
    const row = document.createElement("div");
    row.className = "lobby-row";

    const info = document.createElement("div");
    info.className = "grow";
    info.innerHTML =
      `<div>${escapeHtml(lobby.name)}</div>` +
      `<div class="meta">${escapeHtml(lobby.ruleset)} · ${escapeHtml(lobby.scoring)} · ` +
      `${fill(LABELS.players, { aantal: lobby.players })} · ` +
      `${LABELS.status[lobby.status] ?? lobby.status}</div>`;

    const joinButton = document.createElement("button");
    joinButton.textContent = LABELS.join;
    joinButton.disabled = lobby.seats_free === 0;
    joinButton.addEventListener("click", () =>
      connection.send("lobby_join", { lobby_id: lobby.id }),
    );

    const deleteButton = document.createElement("button");
    deleteButton.textContent = LABELS.delete;
    deleteButton.addEventListener("click", () =>
      connection.send("lobby_delete", { lobby_id: lobby.id }),
    );

    row.append(info, joinButton, deleteButton);
    list.appendChild(row);
  }
}

// --- chat --------------------------------------------------------------------

document.getElementById("chat-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text) return;
  connection.send("chat_send", { text });
  input.value = "";
});

// --- troefkeuze --------------------------------------------------------------

function needsSuit(bid) {
  return bid.type === "abondance" || bid.type === "solo" || bid.type === "ask";
}

function chooseSuit(allowNoTrump) {
  const dialog = document.getElementById("suit-dialog");
  const holder = document.getElementById("suit-buttons");
  holder.replaceChildren();

  return new Promise((resolve) => {
    for (const suit of ["C", "D", "H", "S"]) {
      const button = document.createElement("button");
      button.type = "submit";
      button.value = suit;
      button.textContent = SUIT_SYMBOL[suit];
      if (suit === "D" || suit === "H") button.classList.add("red");
      holder.appendChild(button);
    }
    if (allowNoTrump) {
      const button = document.createElement("button");
      button.type = "submit";
      button.value = "none";
      button.textContent = LABELS.noTrump;
      holder.appendChild(button);
    }

    dialog.addEventListener(
      "close",
      () => {
        const value = dialog.returnValue;
        if (!value) resolve(null);
        else resolve(value === "none" ? null : value);
      },
      { once: true },
    );
    dialog.showModal();
  });
}

// --- opstarten ---------------------------------------------------------------

async function boot() {
  await loadDeck();
  const saved = Connection.restore();
  if (saved?.username) {
    usernameInput.value = saved.username;
    statusLine.textContent = LABELS.connecting;
    connection.connect(saved.username, saved.resumeToken);
  } else {
    statusLine.textContent = LABELS.notConnected;
  }
  store.update({});
}

boot();

// Voor de tests in tests/e2e: laat toe om de kaartrendering te controleren.
window.jwies = { store, connection, cardElement, bidLabel };
