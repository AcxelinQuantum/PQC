"use strict";
// The film stage: every layer is a pure function of time, so a frame can be rendered at any t, in any order, and the
// same t always gives the same picture. render.py calls load(spec) once and then seek(t) for each frame.
const FRAME = document.getElementById("frame");
const W = 1920, H = 1080, BAR = 40;

function bezier(x1, y1, x2, y2) {
  const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx, cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
  return (t) => {
    if (t <= 0) return 0;
    if (t >= 1) return 1;
    let u = t;
    for (let i = 0; i < 10; i++) {
      const x = ((ax * u + bx) * u + cx) * u - t, d = (3 * ax * u + 2 * bx) * u + cx;
      if (Math.abs(x) < 1e-6 || Math.abs(d) < 1e-6) break;
      u = Math.min(1, Math.max(0, u - x / d));
    }
    return ((ay * u + by) * u + cy) * u;
  };
}
const OUT = bezier(0.2, 0, 0, 1), INOUT = bezier(0.45, 0, 0.2, 1);
const ramp = (t, a, d, e = OUT) => (d <= 0 ? (t >= a ? 1 : 0) : e(Math.min(1, Math.max(0, (t - a) / d))));
const lerp = (a, b, k) => a + (b - a) * k;
const r2 = (v) => Math.round(v * 100) / 100;
let SIG = [], PENDING = [];

function set(el, prop, value) {
  value = String(value);
  if (el.style[prop] !== value) el.style[prop] = value;
  SIG.push(value);
}
function h(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}
let LOGOS = 0;
const logo = () => { const k = ++LOGOS; return (window.SPEC.logo || "").replace(/(["(#])logo-([a-z])/g, `$1logo${k}-$2`); };
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
// `code` in the script's text becomes monospaced type
const rich = (s) => esc(s).replace(/`([^`]+)`/g, '<span style="font-family:var(--mono);font-size:.9em">$1</span>');

function fades(spec, el, t, fin = 0.35, fout = 0.35) {
  const k = Math.min(spec.fadeIn === 0 ? 1 : ramp(t, spec.start, spec.fadeIn ?? fin), spec.fadeOut === 0 ? 1 : 1 - ramp(t, spec.end - (spec.fadeOut ?? fout), spec.fadeOut ?? fout, INOUT));
  set(el, "opacity", r2(k));
}
function rise(el, k, px = 16) {
  set(el, "opacity", r2(k));
  set(el, "transform", `translateY(${r2((1 - k) * px)}px)`);
}

// A camera: keys are states {t, s, fx, fy, dur}; the move into a key happens over `dur` seconds ending at its t.
function camera(keys, local) {
  if (!keys || !keys.length) return {s: 1, fx: W / 2, fy: H / 2};
  let cur = keys[0];
  for (let i = 1; i < keys.length; i++) {
    const k = keys[i], dur = k.dur ?? 1.5;
    if (local >= k.t) { cur = k; continue; }
    const m = ramp(local, k.t - dur, dur, INOUT);
    return {s: lerp(cur.s, k.s, m), fx: lerp(cur.fx, k.fx, m), fy: lerp(cur.fy, k.fy, m)};
  }
  return cur;
}
function camTransform(el, s, px, py) {
  const k = Math.min(1, Math.max(0, (s - 1) / 0.4));
  const cx = px + (W / 2 - px) * k, cy = py + (H / 2 - py) * k;
  set(el, "transform", `translate(${r2(cx - s * px)}px, ${r2(cy - s * py)}px) scale(${r2(s * 1000) / 1000})`);
}

const MAKERS = {
  title(spec) {
    const el = h("div", "layer " + (spec.bg ?? "dark")), box = h("div", "title"), words = [];
    for (const line of spec.lines) {
      const ln = h("span", "line" + (line.cls ? " " + line.cls : ""));
      ln.style.fontSize = (line.size || 104) + "px";
      line.text.split(" ").forEach((w, j) => {
        const span = h("span", "w", rich(w));
        if (line.rule === j) { const r = h("span", "rule"); span.appendChild(r); words.push({el: r, rule: true, at: line.ruleAt ?? line.at + 1}); }
        ln.append(span, " ");
        words.push({el: span, at: line.at + j * (line.stagger ?? 0.14), out: line.out});
      });
      box.appendChild(ln);
    }
    el.appendChild(box);
    return {el, update(t) {
      const local = t - spec.start;
      fades(spec, el, t);
      for (const w of words) {
        if (w.rule) { set(w.el, "transform", `scaleX(${r2(ramp(local, w.at, 0.8, INOUT))})`); continue; }
        let k = ramp(local, w.at, 0.45);
        if (w.out != null) k *= 1 - ramp(local, w.out, 0.35, INOUT);
        rise(w.el, k, 14);
      }
    }};
  },

  diagram(spec) {
    const el = h("div", "layer " + (spec.bg || "paper")), cam = h("div", "cam"), items = [];
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "lines");
    cam.appendChild(svg);
    for (const it of spec.items) {
      if (it.kind === "line") {
        const ln = document.createElementNS("http://www.w3.org/2000/svg", "line");
        Object.entries({x1: it.x1, y1: it.y1, x2: it.x2, y2: it.y2, stroke: it.color || "#9eabb6", "stroke-width": it.width || 4, "stroke-linecap": "round"})
          .forEach(([k, v]) => ln.setAttribute(k, v));
        const len = Math.hypot(it.x2 - it.x1, it.y2 - it.y1);
        ln.style.strokeDasharray = len;
        svg.appendChild(ln);
        items.push({it, el: ln, len});
        continue;
      }
      const e = h("div", it.kind, rich(it.text) + (it.sub ? `<small>${rich(it.sub)}</small>` : ""));
      if (it.cls) e.classList.add(...it.cls.split(" "));
      if (it.style) Object.assign(e.style, it.style);
      Object.assign(e.style, {left: it.x + "px", top: it.y + "px", width: it.w ? it.w + "px" : ""});
      cam.appendChild(e);
      items.push({it, el: e});
    }
    el.appendChild(cam);
    return {el, update(t) {
      const local = t - spec.start;
      fades(spec, el, t);
      const c = camera(spec.camera, local);
      camTransform(cam, c.s, c.fx, c.fy);
      for (const {it, el: e, len} of items) {
        let k = ramp(local, it.at, it.dur ?? 0.6);
        const gone = it.out != null ? 1 - ramp(local, it.out, 0.4, INOUT) : 1;
        if (it.kind === "line") {
          set(e, "strokeDashoffset", r2(len * (1 - ramp(local, it.at, it.dur ?? 0.8, INOUT))));
          set(e, "opacity", r2(gone));
          if (it.recolor) e.setAttribute("stroke", local >= it.recolor[0] ? it.recolor[1] : it.color || "#9eabb6");
          SIG.push(e.getAttribute("stroke"));
          continue;
        }
        k *= gone;
        if (it.dim != null) k *= 1 - 0.65 * ramp(local, it.dim, 0.8, INOUT);
        if (it.dx) { set(e, "opacity", r2(k)); set(e, "transform", `translate(${r2((1 - ramp(local, it.at, it.dur ?? 1.2, INOUT)) * it.dx)}px, 0)`); }
        else rise(e, k, it.kind === "tag" ? 8 : 18);
      }
    }};
  },

  section(spec) {
    const el = h("div", "layer dark"), i = h("div", "index", esc(spec.index)), s = h("div", "stitle", esc(spec.title));
    el.append(i, s);
    return {el, update(t) {
      const local = t - spec.start;
      fades(spec, el, t, 0.25, 0.3);
      rise(i, ramp(local, 0.1, 0.4), 10);
      rise(s, ramp(local, 0.2, 0.5), 18);
    }};
  },

  window(spec) {
    const el = h("div", spec.overlay ? "layer" : "layer dark"), cam = h("div", "cam"), win = h("div", "win"), bar = h("div", "bar", "<i></i>" + esc(spec.title || ""));
    const w = spec.scene ? spec.scene.w : spec.w, ht = spec.scene ? spec.scene.h : spec.h;
    const content = h("div", "content" + (spec.term ? " term" : ""));
    Object.assign(content.style, {width: w + "px", height: ht + "px"});
    const box = spec.box || {x: (W - w) / 2, y: (H - ht - BAR) / 2, w};
    const sc = box.w / w;
    Object.assign(win.style, {left: box.x + "px", top: box.y + "px", width: w + "px", transformOrigin: "0 0"});
    win.append(bar, content);
    let img, cursor, ring;
    if (spec.scene) {
      img = h("img");
      cursor = h("div", "cursor", '<svg viewBox="0 0 30 30" width="30" height="30"><path d="M4 2 L4 24 L10 18.5 L14.5 28 L18.5 26.2 L14 17 L22 17 Z" fill="#fff" stroke="#111c26" stroke-width="2" stroke-linejoin="round"/></svg>');
      ring = h("div", "ring");
      content.append(img, ring, cursor);
    }
    cam.appendChild(win);
    if (!spec.noMark && window.SPEC.logo) cam.appendChild(h("div", "mark", logo()));
    el.appendChild(cam);
    let shown = null, termHTML = null;
    return {el, update(t) {
      const local = t - spec.start, st = local + (spec.offset || 0);
      if (spec.layerFade !== false) fades(spec, el, t, spec.bgFade ?? 0.3, 0.3);
      const k = spec.enter === "rise" ? ramp(local, 0, 0.9) : 1;
      set(win, "transform", `translateY(${r2((1 - k) * 70)}px) scale(${r2(sc * 10000) / 10000})`);
      set(win, "opacity", r2(spec.enter === "rise" ? Math.min(1, k * 1.4) : 1));
      const c = camera(spec.camera, local);
      camTransform(cam, c.s, box.x + c.fx * sc, box.y + (BAR + c.fy) * sc);
      if (spec.scene) {
        const frames = spec.scene.frames;
        let f = frames[0];
        for (const x of frames) { if (x.t <= st) f = x; else break; }
        if (shown !== f.src) { shown = f.src; img.src = f.src; PENDING.push(img.decode().catch(() => {})); }
        SIG.push(f.src);
        const keys = spec.scene.cursor || [];
        let pos = null, click = null;
        for (let i = 0; i < keys.length; i++) {
          const key = keys[i];
          if (key.click != null && st >= key.t) click = key.t;
          if (st >= key.t) { pos = key; continue; }
          if (pos && key.move && st >= key.t - key.move) {
            const m = ramp(st, key.t - key.move, key.move, INOUT);
            pos = {x: lerp(pos.x, key.x, m), y: lerp(pos.y, key.y, m), hide: false};
          }
          break;
        }
        if (!pos || pos.hide) set(cursor, "opacity", 0);
        else { set(cursor, "opacity", 1); set(cursor, "transform", `translate(${r2(pos.x - 4)}px, ${r2(pos.y - 2)}px)`); }
        const rk = click == null ? 1 : ramp(st, click, 0.5);
        set(ring, "opacity", r2(click == null || !pos ? 0 : (1 - rk) * 0.95));
        if (pos) set(ring, "transform", `translate(${r2(pos.x)}px, ${r2(pos.y)}px) scale(${r2(0.4 + rk * 0.8)})`);
      } else {
        let out = "";
        for (const line of spec.lines) {
          if (st < line.t) break;
          if (line.kind === "cmd") {
            const n = Math.min(line.text.length, Math.floor((st - line.t) * (line.cps || 16)));
            const typing = n < line.text.length;
            const blink = Math.floor(st * 2) % 2 === 0;
            const last = !spec.lines.some((l) => l !== line && l.kind === "cmd" && l.t > line.t && st >= l.t);
            out += `<div class="cmd">${esc(line.text.slice(0, n))}${typing || (last && blink) ? '<span class="caret"></span>' : ""}</div>`;
            if (typing) break;
          } else out += `<div class="${line.kind || ""}">${esc(line.text)}</div>`;
        }
        if (termHTML !== out) { termHTML = out; content.innerHTML = out; }
        SIG.push(out);
      }
    }};
  },

  lower(spec) {
    const el = h("div", "layer"), card = h("div", "lower", rich(spec.text));
    el.appendChild(card);
    return {el, update(t) {
      const k = ramp(t, spec.start, 0.5) * (1 - ramp(t, spec.end - 0.4, 0.4, INOUT));
      rise(card, k, 20);
    }};
  },

  trust(spec) {
    const el = h("div", "layer dark"), box = h("div", "trust"), lines = [];
    for (const l of spec.lines) { const d = h("div", l.cls || "t", rich(l.text)); box.appendChild(d); lines.push({el: d, at: l.at}); }
    el.appendChild(box);
    return {el, update(t) {
      const local = t - spec.start;
      fades(spec, el, t, 0.4, 0.3);
      for (const l of lines) rise(l.el, ramp(local, l.at, 0.6), 16);
    }};
  },

  close(spec) {
    const el = h("div", "layer dark"), box = h("div", "close");
    const parts = [h("div", "logo", logo()), h("div", "name", esc(spec.name)), h("div", "sig", esc(spec.sig)), h("div", "url", esc(spec.url))];
    const rule = h("div", "crule");
    box.append(...parts.slice(0, 3), rule, parts[3]);
    el.appendChild(box);
    const black = h("div", "black");
    el.appendChild(black);
    return {el, update(t) {
      const local = t - spec.start;
      fades(spec, el, t, 0.5, 0);
      parts.forEach((p, i) => rise(p, ramp(local, 0.3 + i * 0.6, 0.7), 14));
      set(rule, "transform", `scaleX(${r2(ramp(local, 2.6, 1.0, INOUT))})`);
      set(black, "opacity", r2(ramp(t, spec.end - 1.4, 1.4, INOUT)));
    }};
  },

  marker(spec) {
    const el = h("div", "layer"), m = h("div", "marker", spec.html);
    el.appendChild(m);
    return {el, update(t) { rise(m, ramp(t, spec.start, 0.4) * (1 - ramp(t, spec.end - 0.3, 0.3)), 8); }};
  },

  black(spec) {
    const el = h("div", "layer"), b = h("div", "black");
    el.appendChild(b);
    return {el, update(t) { set(b, "opacity", r2(lerp(spec.from, spec.to, ramp(t, spec.start, spec.end - spec.start, INOUT)))); }};
  },

  draft(spec) {
    const el = h("div", "layer"), d = h("div", "draft", "DRAFT" + (spec.note ? " · " + esc(spec.note) : ""));
    el.appendChild(d);
    return {el, update() {}};
  },
};

let LAYERS = [];
window.load = async (spec) => {
  window.SPEC = spec;
  // A window that opens while another is on screen (a split frame) is laid over it, without a background of its own.
  spec.layers.forEach((l, i) => {
    if (l.type === "window" && spec.layers.slice(0, i).some((o) => o.type === "window" && o.start < l.end && l.start < o.end && o.start <= l.start)) l.overlay = true;
  });
  LAYERS = spec.layers.map((s) => ({spec: s, ...MAKERS[s.type](s)}));
  for (const l of LAYERS) FRAME.appendChild(l.el);
  await document.fonts.ready;
  return LAYERS.length;
};
window.seek = async (t) => {
  SIG = [];
  PENDING = [];
  for (const l of LAYERS) {
    const on = t >= l.spec.start && t < l.spec.end;
    set(l.el, "visibility", on ? "visible" : "hidden");
    if (on) l.update(t);
  }
  await Promise.all(PENDING);
  return SIG.join("|");
};
// Text outside the title-safe area (5% in from each edge) at time t: words a television or a cropped player could cut off.
window.offscreen = (t) => {
  const bad = [];
  for (const l of LAYERS) {
    if (!(t >= l.spec.start && t < l.spec.end) || l.spec.type === "window") continue;
    for (const e of l.el.querySelectorAll(".w, .lower, .stitle, .index, .t, .m, .last, .name, .sig, .url, .quote, .box, .tag, .note, .marker")) {
      const r = e.getBoundingClientRect();
      if (!r.width || getComputedStyle(e).opacity === "0") continue;
      if (r.left < 96 || r.right > W - 96 || r.top < 54 || r.bottom > H - 54) bad.push(`${e.innerText.trim().slice(0, 40)} (${Math.round(r.left)},${Math.round(r.top)}–${Math.round(r.right)},${Math.round(r.bottom)})`);
    }
  }
  return bad;
};
// The texts on screen at time t, for the review: what a viewer can read, and nothing else.
window.texts = (t) => LAYERS.filter((l) => t >= l.spec.start && t < l.spec.end).map((l) => l.el.innerText.trim()).filter(Boolean);
