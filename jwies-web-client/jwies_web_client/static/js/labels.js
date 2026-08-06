// Nederlandse teksten van de client zelf.
//
// Enkel de eigen knoppen en koppen staan hier. Alles wat over het spel gaat -
// biedaankondigingen, contractmeldingen, de eindafrekening - komt kant-en-klaar
// in het Nederlands van de server, zodat die zinnen maar op een plaats staan.

export const LABELS = {
  connecting: "Verbinden...",
  connected: "Verbonden als {naam}",
  disconnected: "Verbinding verbroken - opnieuw proberen...",
  notConnected: "Niet verbonden",

  nameRequired:
    "Vul een naam in van 2 tot 20 tekens: letters, cijfers, spaties, " +
    "en '.', '-', '_' of een apostrof.",
  serverRequired: "Vul het adres van de spelserver in (ws://... of wss://...).",
  serverUnreachable:
    "Geen verbinding met de spelserver op {adres}. Draait hij, en klopt het adres?",
  lobbyNameRequired: "Geef de tafel een naam.",

  join: "Deelnemen",
  delete: "Verwijderen",
  seatsFree: "{aantal} plaats(en) vrij",
  full: "vol",
  players: "{aantal}/4 spelers",

  status: {
    waiting: "wacht op spelers",
    running: "bezig",
    paused: "gepauzeerd",
    finished: "afgelopen",
    broken: "fout",
  },

  playCard: "Speel kaart",
  fold: "Ronde opgeven ({aantal}/4)",
  foldWaiting: "Opgegeven - wachten op de rest ({aantal}/4)",
  shuffleQuestion: "Wil je de kaarten schudden?",
  yes: "Ja",
  no: "Nee",
  cutQuestion: "Hoeveel kaarten neem je af? ({min} t.e.m. {max})",
  cut: "Couperen",
  chooseSuit: "Kies een troefkleur",
  noTrump: "Geen troef",
  cancel: "Annuleren",

  yourTurn: "Jij bent aan zet",
  waitingFor: "Wachten op {naam}",

  tricks: "Slagen",
  attack: "Aanval",
  defence: "Verdediging",
  trump: "Troef",
  noTrumpShort: "geen",
  contract: "Contract",
  score: "Stand",
  round: "Ronde {nummer}",

  bid: {
    pass: "Passen",
    ask: "Vragen",
    join: "Meegaan",
    alone: "Alleen gaan ({slagen})",
    abondance: "Abondance {slagen}",
    misere: "Miserie",
    misere_ouverte: "Miserie bloot",
    troel: "Troel",
    solo: "Solo",
    solo_slim: "Solo slim",
    pico: "Pico",
  },
};

/** Vult {plaatshouders} in een label in. */
export function fill(template, values = {}) {
  return template.replace(/\{(\w+)\}/g, (match, key) =>
    key in values ? String(values[key]) : match,
  );
}
