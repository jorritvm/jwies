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
    this.serverUrl = null;
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
        JSON.stringify({
          username: this.username,
          resumeToken: this.resumeToken,
          serverUrl: this.serverUrl,
        }),
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

  /** Adres van dezelfde host als deze pagina. */
  static sameOriginUrl() {
    const scheme = location.protocol === "https:" ? "wss:" : "ws:";
    return `${scheme}//${location.host}/ws`;
  }

  /**
   * Waar draait de spelserver?
   *
   * Deze pagina wordt door een eigen webserver uitgeserveerd, los van de
   * spelserver, dus dat hoeft niet hetzelfde adres te zijn. In volgorde van
   * voorrang:
   *   1. wat de speler zelf invulde (bewaard in localStorage)
   *   2. ?server=... in de adresbalk
   *   3. game_server_url uit /config.json, gezet met jwies-web --game-server
   *   4. dezelfde host als deze pagina
   */
  static async resolveUrl() {
    const saved = Connection.restore();
    if (saved?.serverUrl) return saved.serverUrl;

    const fromQuery = new URLSearchParams(location.search).get("server");
    if (fromQuery) return fromQuery;

    try {
      const response = await fetch("./config.json", { cache: "no-store" });
      if (response.ok) {
        const config = await response.json();
        if (config.game_server_url) return config.game_server_url;
      }
    } catch {
      /* geen config.json: dan gewoon dezelfde host proberen */
    }
    return Connection.sameOriginUrl();
  }

  url() {
    return this.serverUrl || Connection.sameOriginUrl();
  }

  connect(username, resumeToken = null, serverUrl = null) {
    this.username = username;
    this.resumeToken = resumeToken ?? this.resumeToken;
    this.serverUrl = serverUrl ?? this.serverUrl;
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
