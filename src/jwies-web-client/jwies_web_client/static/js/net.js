// Websocket-verbinding met de server.
//
// Stuurt en ontvangt gewone JSON: geen enkele bibliotheek nodig. Bij verlies
// van de verbinding wordt automatisch opnieuw verbonden met exponentiele
// wachttijd, en wordt dezelfde naam plus resume_token opnieuw aangeboden -
// dat is wat de server aan je stoel terugbindt.

const PROTOCOL_VERSION = 1;
const STORAGE_KEY = "jwies.session";
const MAX_BACKOFF_MS = 30000;

export class Connection extends EventTarget {
  constructor() {
    super();
    this.socket = null;
    this.username = null;
    this.resumeToken = null;
    this.counter = 0;
    this.backoff = 1000;
    this.lastSeq = 0;
    this.wanted = false;
  }

  static restore() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    } catch {
      return null;
    }
  }

  remember() {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ username: this.username, resumeToken: this.resumeToken }),
      );
    } catch {
      /* private mode: niet erg, we verbinden dan gewoon met enkel de naam */
    }
  }

  static forget() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* niets aan te doen */
    }
  }

  url() {
    const scheme = location.protocol === "https:" ? "wss:" : "ws:";
    return `${scheme}//${location.host}/ws`;
  }

  connect(username, resumeToken = null) {
    this.username = username;
    this.resumeToken = resumeToken ?? this.resumeToken;
    this.wanted = true;
    this._open();
  }

  disconnect() {
    this.wanted = false;
    if (this.socket) this.socket.close();
  }

  _open() {
    this.socket = new WebSocket(this.url());

    this.socket.addEventListener("open", () => {
      this.backoff = 1000;
      this.lastSeq = 0;
      this.send("hello", {
        username: this.username,
        client: "web",
        client_version: "1",
        resume_token: this.resumeToken,
      });
      this.dispatchEvent(new CustomEvent("open"));
    });

    this.socket.addEventListener("message", (event) => {
      let envelope;
      try {
        envelope = JSON.parse(event.data);
      } catch {
        return;
      }
      // Een gat in de volgnummers betekent dat we iets gemist hebben; vraag
      // dan een verse momentopname in plaats van scheef te blijven staan.
      if (envelope.seq && envelope.seq > this.lastSeq + 1 && this.lastSeq !== 0) {
        this.send("request_snapshot", {});
      }
      if (envelope.seq) this.lastSeq = envelope.seq;

      const message = envelope.msg;
      if (message.type === "hello_ok") {
        this.resumeToken = message.resume_token;
        this.remember();
      }
      this.dispatchEvent(new CustomEvent("message", { detail: message }));
    });

    this.socket.addEventListener("close", () => {
      this.dispatchEvent(new CustomEvent("closed"));
      if (!this.wanted) return;
      setTimeout(() => this._open(), this.backoff);
      this.backoff = Math.min(this.backoff * 2, MAX_BACKOFF_MS);
    });

    this.socket.addEventListener("error", () => {
      /* 'close' volgt altijd; daar zit de herverbindlogica */
    });
  }

  send(type, fields = {}) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
    this.counter += 1;
    this.socket.send(
      JSON.stringify({
        v: PROTOCOL_VERSION,
        id: String(this.counter),
        msg: { type, ...fields },
      }),
    );
  }
}
