// Tooltips: every `title` in the app shows as the app's own tooltip (after a short rest, in its type and colours,
// wrapped) instead of the system's. A title moves to data-tip the first time its element is hovered or focused, and
// to aria-label when the element has no text of its own (an icon button).
let bubble = null, on = null, timer = 0, watch = 0, lastHide = 0;

function adopt(el) {
  const t = el.getAttribute("title");
  if (!t) return;
  el.dataset.tip = t;
  if (!el.getAttribute("aria-label") && !el.textContent.trim()) el.setAttribute("aria-label", t);
  el.removeAttribute("title");
}
function hide() {
  clearTimeout(timer);
  clearInterval(watch);
  if (bubble) { bubble.remove(); bubble = null; lastHide = Date.now(); }
  on = null;
}
function show(el) {
  if (!el.isConnected || !el.dataset.tip) return;
  bubble = document.createElement("div");
  bubble.className = "tip";
  bubble.textContent = el.dataset.tip;
  document.body.appendChild(bubble);
  const r = el.getBoundingClientRect(), w = bubble.offsetWidth, h = bubble.offsetHeight;
  bubble.style.left = Math.max(6, Math.min(window.innerWidth - w - 6, r.left + r.width / 2 - w / 2)) + "px";
  bubble.style.top = (r.bottom + h + 10 > window.innerHeight ? r.top - h - 6 : r.bottom + 6) + "px";
  watch = setInterval(() => { if (!el.isConnected) hide(); }, 250);   // its element was redrawn or the page changed
}
function over(e) {
  const el = e.target.closest?.("[title], [data-tip]");
  if (el === on) return;
  hide();
  if (!el) return;
  adopt(el);
  if (!el.dataset.tip) return;
  on = el;
  timer = setTimeout(() => show(el), Date.now() - lastHide < 400 ? 60 : 480);   // moving along a row of buttons: at once
}
document.addEventListener("mouseover", over);
document.addEventListener("focusin", (e) => { if (e.target.matches?.(":focus-visible")) over(e); });
for (const ev of ["mousedown", "keydown", "wheel", "focusout"]) document.addEventListener(ev, hide, true);
document.addEventListener("mouseleave", hide);
window.addEventListener("hashchange", hide);
