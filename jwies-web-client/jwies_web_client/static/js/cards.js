// Kaarten tekenen uit svg-cards.svg.
//
// Dat bestand is een grote plaat met 53 <g>-groepen zonder eigen transform.
// Externe <use href="bestand.svg#id"> werkt niet betrouwbaar in alle browsers,
// dus halen we de plaat een keer op, verbergen we ze, en knippen we per kaart
// exact de juiste rechthoek uit via getBBox() + viewBox.

const SUIT_SVG = { C: "club", D: "diamond", H: "heart", S: "spade" };
const RANK_SVG = {
  2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "10",
  J: "jack", Q: "queen", K: "king", A: "1",
};

const boxes = new Map();
let ready = false;

export function svgElementId(code) {
  const rank = code.slice(0, -1);
  const suit = code.slice(-1);
  return `${RANK_SVG[rank]}_${SUIT_SVG[suit]}`;
}

export async function loadDeck() {
  if (ready) return;
  const response = await fetch("/assets/svg-cards.svg");
  const markup = await response.text();
  const host = document.getElementById("card-sprite");
  // Zero-sized met overflow:hidden, niet display:none - getBBox() heeft een
  // daadwerkelijk gerenderd element nodig om te kunnen meten.
  host.setAttribute(
    "style",
    "position:absolute;width:0;height:0;overflow:hidden;",
  );
  host.innerHTML = markup;
  ready = true;
}

function boxOf(elementId) {
  if (boxes.has(elementId)) return boxes.get(elementId);
  const node = document.getElementById(elementId);
  if (!node) return null;
  const box = node.getBBox();
  const value = `${box.x} ${box.y} ${box.width} ${box.height}`;
  boxes.set(elementId, value);
  return value;
}

/** Bouwt een <svg> dat exact een kaart uit de plaat toont. */
export function cardElement(code, { faceDown = false } = {}) {
  const elementId = faceDown ? "back" : svgElementId(code);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.classList.add("card");
  svg.dataset.card = faceDown ? "back" : code;
  const viewBox = boxOf(elementId);
  if (viewBox) svg.setAttribute("viewBox", viewBox);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  if (!faceDown) svg.setAttribute("aria-label", cardLabel(code));

  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#${elementId}`);
  svg.appendChild(use);
  return svg;
}

const RANK_NL = {
  2: "twee", 3: "drie", 4: "vier", 5: "vijf", 6: "zes", 7: "zeven",
  8: "acht", 9: "negen", 10: "tien", J: "boer", Q: "dame", K: "heer", A: "aas",
};
const SUIT_NL = { C: "klaveren", D: "koeken", H: "harten", S: "schoppen" };

export function cardLabel(code) {
  const rank = code.slice(0, -1);
  const suit = code.slice(-1);
  return `${SUIT_NL[suit]} ${RANK_NL[rank]}`;
}

export function suitLabel(suit) {
  return SUIT_NL[suit] ?? "zonder troef";
}

export const SUIT_SYMBOL = { C: "♣", D: "♦", H: "♥", S: "♠" };
