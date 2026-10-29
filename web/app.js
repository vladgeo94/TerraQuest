"use strict";

// ------------------------------------------------------------------ utilities
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const app = $("#app");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function toast(msg, ms = 2600) {
  const t = $("#toast");
  t.innerHTML = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), ms);
}

const PRACTICE_NOTE = `<div class="hintbox">🧪 <b>Practice run.</b> Practice mode opened this stage before you reached it, so XP, stars and answers here aren't saved. Your real progress is untouched.</div>`;
const starsHtml = (n, max = 3) => `<span class="stars">${"★".repeat(n)}<span class="off">${"★".repeat(max - n)}</span></span>`;

// ------------------------------------------------------------------ HCL highlighting + tiny markdown
const HCL_KEYWORDS = /^(resource|data|variable|output|module|provider|terraform|locals|backend|cloud|required_providers|required_version|lifecycle|provisioner|connection|dynamic|content|for_each|count|depends_on|source|version|for|in|if|import|moved|removed|check|assert|validation|precondition|postcondition|ephemeral)$/;
function highlight(code, lang) {
  const src = String(code);
  if (lang && !/^(hcl|tf|terraform|bash|sh|shell|console)$/.test(lang)) return esc(src);
  const shell = /^(bash|sh|shell|console)$/.test(lang || "");
  const re = shell
    ? /(#[^\n]*)|("(?:[^"\\]|\\.)*"|'[^']*')|(\bterraform\b)|(\s-{1,2}[\w-]+(?:=\S*)?)/g
    : /(#[^\n]*|\/\/[^\n]*|\/\*[\s\S]*?\*\/)|("(?:[^"\\\n]|\\.)*")|(\b\d+(?:\.\d+)?\b)|(\b(?:true|false|null)\b)|(\b[a-z_][\w-]*(?=\())|(\b[a-z_][\w-]*\b)/g;
  let out = "", last = 0, m;
  while ((m = re.exec(src))) {
    out += esc(src.slice(last, m.index));
    const [tok] = m;
    if (m[1]) out += `<span class="hl-c">${esc(tok)}</span>`;
    else if (m[2]) out += `<span class="hl-s">${esc(tok).replace(/\$\{([^}]*)\}/g, '<span class="hl-f">${$1}</span>')}</span>`;
    else if (shell) out += m[3] ? `<span class="hl-k">${esc(tok)}</span>` : `<span class="hl-n">${esc(tok)}</span>`;
    else if (m[3]) out += `<span class="hl-n">${tok}</span>`;
    else if (m[4]) out += `<span class="hl-b">${tok}</span>`;
    else if (m[5]) out += `<span class="hl-f">${tok}</span>`;
    else if (m[6]) out += HCL_KEYWORDS.test(tok) ? `<span class="hl-k">${tok}</span>` : esc(tok);
    last = m.index + tok.length;
  }
  return out + esc(src.slice(last));
}

function inline(s) {
  const codes = [];
  s = s.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  s = esc(s)
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>")
    .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${esc(codes[+i])}</code>`);
}

function md(text) {
  const lines = String(text || "").replace(/\r/g, "").split("\n");
  let html = "", i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const fence = line.match(/^```(\w*)/);
    if (fence) {
      const buf = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]);
      i++;
      html += `<pre><code>${highlight(buf.join("\n"), fence[1] || "hcl")}</code></pre>`;
      continue;
    }
    const h = line.match(/^(#{1,4})\s+(.*)/);
    if (h) { const lvl = Math.min(h[1].length + 1, 4); html += `<h${lvl}>${inline(h[2])}</h${lvl}>`; i++; continue; }
    if (/^\s*[-*]\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items = [];
      while (i < lines.length && (ordered ? /^\s*\d+\.\s+/ : /^\s*[-*]\s+/).test(lines[i])) {
        let item = lines[i].replace(/^\s*(?:[-*]|\d+\.)\s+/, "");
        i++;
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*(?:[-*]|\d+\.)\s+/.test(lines[i])) item += " " + lines[i++].trim();
        const sub = [];
        while (i < lines.length && /^\s{2,}\S/.test(lines[i])) sub.push(lines[i++].replace(/^\s{2,4}/, ""));
        items.push(`<li>${inline(item)}${sub.length ? md(sub.join("\n")) : ""}</li>`);
      }
      html += ordered ? `<ol>${items.join("")}</ol>` : `<ul>${items.join("")}</ul>`;
      continue;
    }
    if (line.startsWith(">")) {
      const buf = [];
      while (i < lines.length && lines[i].startsWith(">")) buf.push(lines[i++].replace(/^>\s?/, ""));
      html += `<blockquote>${md(buf.join("\n"))}</blockquote>`;
      continue;
    }
    if (/^\|.*\|\s*$/.test(line)) {
      const rows = [];
      while (i < lines.length && /^\|.*\|\s*$/.test(lines[i])) rows.push(lines[i++]);
      const cells = (r) => r.trim().slice(1, -1).split("|").map((c) => c.trim());
      const head = cells(rows[0]);
      const body = rows.slice(rows[1] && /^\|[\s:|-]+\|$/.test(rows[1].trim()) ? 2 : 1);
      html += `<table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${body.map((r) => `<tr>${cells(r).map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
      continue;
    }
    if (!line.trim()) { i++; continue; }
    const buf = [];
    while (i < lines.length && lines[i].trim() && !/^(```|#{1,4}\s|>|\s*[-*]\s+|\s*\d+\.\s+|\|)/.test(lines[i])) buf.push(lines[i++]);
    if (!buf.length) buf.push(lines[i++]);
    html += `<p>${inline(buf.join(" "))}</p>`;
  }
  return html;
}

// ------------------------------------------------------------------ HUD
let OV = null;
async function refreshHud() {
  OV = await api("/api/overview");
  const p = OV.player;
  const pct = Math.round(100 * (p.xp - p.level_xp) / Math.max(1, p.next_xp - p.level_xp));
  $("#hud").innerHTML = `
    <span class="pill" title="Level ${p.level}: ${esc(p.title)}">⚔️ Lv ${p.level} · ${esc(p.title)}</span>
    <span class="pill" title="${p.xp} XP — next level at ${p.next_xp}"><span class="xpbar"><i style="width:${pct}%"></i></span>${p.xp} XP</span>
    <span class="pill" title="Daily streak (best ${OV.streak.best})">🔥 ${OV.streak.count}</span>
    <span class="pill" title="Stars earned">⭐ ${OV.stars.earned}/${OV.stars.total}</span>
    <a class="pill link" href="#/review" title="Questions you missed come back here">♻️ Respawn ${OV.review_count ? `<span class="badge">${OV.review_count}</span>` : ""}</a>
    <a class="pill link" href="#/exam" title="Timed practice exam">🏁 Final Boss</a>
    <a class="pill link" href="#/settings" title="Settings and stats">⚙️</a>`;
  return OV;
}

// ------------------------------------------------------------------ router
const routes = [
  [/^#?\/?$/, viewMap],
  [/^#\/stage\/([^/]+)\/([^/]+)$/, viewStage],
  [/^#\/review$/, viewReview],
  [/^#\/exam$/, viewExamIntro],
  [/^#\/settings$/, viewSettings],
];
let cleanup = null;
async function route() {
  if (cleanup) { cleanup(); cleanup = null; }
  app.classList.remove("wide");
  const h = location.hash || "#/";
  for (const [re, fn] of routes) {
    const m = h.match(re);
    if (m) {
      try { await refreshHud(); await fn(...m.slice(1)); }
      catch (e) { app.innerHTML = `<div class="card"><h2>Something went wrong</h2><p class="muted">${esc(e.message)}</p><a class="btn" href="#/">Back to map</a></div>`; }
      window.scrollTo(0, 0);
      return;
    }
  }
  location.hash = "#/";
}
window.addEventListener("hashchange", route);

// ------------------------------------------------------------------ map
async function viewMap() {
  const ov = OV;
  const next = findNextStage(ov);
  const tfWarn = ov.terraform ? "" : `<p class="hintbox">⚠️ <b>terraform</b> was not found on your PATH. Quizzes work, but hands-on labs need Terraform installed (<a href="https://developer.hashicorp.com/terraform/install" target="_blank" rel="noopener">install guide</a>).</p>`;
  app.innerHTML = `
    <section class="hero">
      <div class="card">
        <h1>Welcome, adventurer 🏔️</h1>
        <p class="muted">Clear each world to unlock the next, from the basics all the way to HCP Terraform. Beat every boss to unlock the <b>Final Boss</b>: a timed practice exam built like the real <b>HashiCorp Certified: Terraform Associate (004)</b>.</p>
        ${next ? `<a class="btn" href="#/stage/${next.w}/${next.s}">▶ Continue: ${esc(next.title)}</a>` : `<a class="btn" href="#/exam">🏁 Take the Final Boss</a>`}
        ${tfWarn}
      </div>
      <div class="card stats">
        <div class="stat"><b>${ov.player.level}</b><span>Level · ${esc(ov.player.title)}</span></div>
        <div class="stat"><b>${ov.stars.earned}</b><span>of ${ov.stars.total} stars</span></div>
        <div class="stat"><b>${ov.accuracy ?? "–"}${ov.accuracy != null ? "%" : ""}</b><span>accuracy over ${ov.answered} answers</span></div>
        <div class="stat"><b>${ov.exam.best ?? "–"}${ov.exam.best != null ? "%" : ""}</b><span>best practice exam (70% to pass)</span></div>
      </div>
    </section>
    <div class="worlds">${ov.worlds.map(worldCard).join("")}
      <div class="world ${ov.exam.unlocked ? "" : "locked"}">
        <div class="world-head"><div class="world-icon">🏁</div><div><div class="obj">All objectives</div><h2>Final Boss: Practice Exam</h2>
        <div class="muted">${ov.exam.questions} questions · ${ov.exam.minutes} minutes · weighted like the official exam objectives</div></div>
        <span class="spacer"></span>${ov.exam.unlocked ? `<a class="btn" href="#/exam">Enter</a>` : `<span class="muted">🔒 Beat every world boss</span>`}</div>
      </div>
    </div>`;
}

function findNextStage(ov) {
  for (const w of ov.worlds) for (const s of w.stages) if (s.unlocked && !s.completed) return { w: w.id, s: s.id, title: `${w.title} · ${s.title}` };
  return null;
}

function worldCard(w) {
  const earned = w.stages.reduce((a, s) => a + s.stars, 0);
  return `<div class="world ${w.unlocked ? "" : "locked"} ${w.cleared ? "cleared" : ""}">
    <div class="world-head"><div class="world-icon">${w.icon}</div>
      <div><div class="obj">${esc(w.objective)}</div><h2>${esc(w.title)}</h2><div class="muted">${esc(w.subtitle)}</div></div>
      <span class="spacer"></span><span>${starsHtml(Math.round(3 * earned / Math.max(1, w.stages.length * 3)))} <small class="muted">${earned}/${w.stages.length * 3}</small></span>
    </div>
    <div class="stages">${w.stages.map((s) => `
      <a class="node ${s.unlocked ? "" : "locked"} ${s.completed ? "done" : ""} ${s.boss ? "boss" : ""}" href="#/stage/${w.id}/${s.id}">
        <span class="kind">${s.boss ? "👹 Boss" : s.kind === "lab" ? "🛠️ Lab" : "📘 Lesson"}${s.unlocked ? (s.practice ? " · 🧪" : "") : " · 🔒"}</span>
        <span class="title">${esc(s.title)}</span>
        ${starsHtml(s.stars)}
      </a>`).join("")}</div>
  </div>`;
}

function nextAfter(wid, sid) {
  let found = false;
  for (const w of OV.worlds) for (const s of w.stages) {
    if (found) return `#/stage/${w.id}/${s.id}`;
    if (w.id === wid && s.id === sid) found = true;
  }
  return "#/exam";
}

// ------------------------------------------------------------------ stage
async function viewStage(wid, sid) {
  const st = await api(`/api/stage?w=${encodeURIComponent(wid)}&s=${encodeURIComponent(sid)}`);
  if (!st.unlocked) {
    app.innerHTML = `<div class="card"><h2>🔒 Locked</h2><p class="muted">Finish the earlier stages first, or turn on practice mode in ⚙️ Settings.</p><a class="btn" href="#/">Back to map</a></div>`;
    return;
  }
  if (st.kind === "lab") return viewLab(st);
  const crumbs = `<div class="crumbs"><a href="#/">Map</a> › ${st.world.icon} ${esc(st.world.title)} › ${esc(st.title)}</div>`;
  if (!st.lesson) return runQuiz(st, crumbs);
  app.innerHTML = `${crumbs}
    <div class="card lesson">
      <h1>${st.boss ? "👹 " : "📘 "}${esc(st.title)}</h1>
      ${st.practice ? PRACTICE_NOTE : ""}
      ${md(st.lesson)}
      <div class="row" style="margin-top:20px">
        <button class="btn" id="go">${st.boss ? "Fight the boss" : "Start challenge"} → (${st.questions.length} questions)</button>
        ${st.record.stars ? `<span class="muted">Best: ${starsHtml(st.record.stars)} ${st.record.best}%</span>` : ""}
      </div>
    </div>`;
  $("#go").onclick = () => runQuiz(st, crumbs);
}

// Renders one question; returns { getAnswer(), lock(result) }.
function renderQuestion(box, q, onChange) {
  const typeLabel = { single: "Choose one", multi: `Choose ${q.pick}`, fill: "Type the answer", order: "Put in the right order" }[q.type];
  box.innerHTML = `
    <div class="qtype">${typeLabel}</div>
    <div class="qtext">${inline(q.q)}</div>
    ${q.code ? `<pre><code>${highlight(q.code, "hcl")}</code></pre>` : ""}
    <div class="answer"></div>`;
  const area = $(".answer", box);
  let sel = q.type === "multi" ? new Set() : null;
  if (q.type === "single" || q.type === "multi") {
    const keys = q.option_keys || q.options.map((_, i) => i);
    area.innerHTML = `<div class="options">${q.options.map((o, i) => `<button class="opt" data-i="${keys[i]}"><span class="key">${"ABCDEFGH"[i]}</span><span>${inline(o)}</span></button>`).join("")}</div>`;
    $$(".opt", area).forEach((b) => b.onclick = () => {
      const i = +b.dataset.i;
      if (q.type === "single") { sel = i; $$(".opt", area).forEach((x) => x.classList.toggle("sel", x === b)); }
      else { sel.has(i) ? sel.delete(i) : sel.add(i); b.classList.toggle("sel"); }
      onChange && onChange();
    });
  } else if (q.type === "fill") {
    area.innerHTML = `<input class="fill" placeholder="${esc(q.placeholder || "your answer")}" autocomplete="off" spellcheck="false">`;
    $("input", area).oninput = () => onChange && onChange();
    setTimeout(() => $("input", area)?.focus(), 30);
  } else if (q.type === "order") {
    area.innerHTML = `<ul class="orderlist">${q.items.map((it) => `<li draggable="true" data-k="${it.key}"><span class="num"></span><span class="txt">${inline(it.text)}</span><button class="mv up" title="Move up">↑</button><button class="mv dn" title="Move down">↓</button></li>`).join("")}</ul>`;
    const ul = $("ul", area);
    const renum = () => $$("li", ul).forEach((li, i) => $(".num", li).textContent = i + 1);
    renum();
    let drag = null;
    $$("li", ul).forEach((li) => {
      li.ondragstart = () => { drag = li; li.classList.add("dragging"); };
      li.ondragend = () => { li.classList.remove("dragging"); drag = null; renum(); onChange && onChange(); };
      li.ondragover = (e) => {
        e.preventDefault();
        if (!drag || drag === li) return;
        const r = li.getBoundingClientRect();
        ul.insertBefore(drag, e.clientY > r.top + r.height / 2 ? li.nextSibling : li);
      };
      $(".up", li).onclick = () => { if (li.previousElementSibling) ul.insertBefore(li, li.previousElementSibling); renum(); };
      $(".dn", li).onclick = () => { if (li.nextElementSibling) ul.insertBefore(li.nextElementSibling, li); renum(); };
    });
  }
  return {
    getAnswer() {
      if (q.type === "single") return sel;
      if (q.type === "multi") return [...sel].sort((a, b) => a - b);
      if (q.type === "fill") return $("input", area).value;
      return $$("li", area).map((li) => +li.dataset.k);
    },
    ready() {
      if (q.type === "single") return sel !== null;
      if (q.type === "multi") return sel.size > 0;
      if (q.type === "fill") return $("input", area).value.trim() !== "";
      return true;
    },
    lock(res, given) {
      $$("button, input", area).forEach((el) => el.disabled = true);
      if (q.type === "single" || q.type === "multi") {
        const right = new Set([].concat(res.answer));
        const picked = new Set([].concat(given));
        $$(".opt", area).forEach((b) => {
          const i = +b.dataset.i;
          if (right.has(i)) b.classList.add("right");
          else if (picked.has(i)) b.classList.add("wrong");
        });
      }
      $$("li", area).forEach((li) => li.draggable = false);
    },
  };
}

function feedbackHtml(res, q) {
  let correctTxt = "";
  if (!res.correct) {
    if (q.type === "fill") correctTxt = `<p>Correct answer: <code>${esc(res.answer)}</code></p>`;
    if (q.type === "order") correctTxt = `<p>Correct order:</p><ol>${res.answer.map((t) => `<li>${inline(t)}</li>`).join("")}</ol>`;
  }
  return `<div class="feedback ${res.correct ? "ok" : "no"}">
    <h4>${res.correct ? "✅ Correct!" : "❌ Not quite"} ${res.xp ? `<small class="muted">+${res.xp} XP</small>` : res.practice ? `<small class="muted">(practice, not saved)</small>` : res.xp_already ? `<small class="muted">(XP already earned)</small>` : ""}</h4>
    ${correctTxt}
    ${res.explain ? `<div class="lesson">${md(res.explain)}</div>` : ""}
    ${res.docs ? `<p><a href="${esc(res.docs)}" target="_blank" rel="noopener">📖 Read the docs</a></p>` : ""}
  </div>`;
}

function runQuiz(st, crumbs, opts = {}) {
  const qs = st.questions;
  let idx = 0, correct = 0, hints = 0;
  const review = !!opts.review;
  const show = () => {
    const q = qs[idx];
    app.innerHTML = `${crumbs}<div class="quiz">
      <div class="row"><b>${st.boss ? "👹 " : ""}${esc(st.title)}</b><span class="spacer"></span><span class="muted">Question ${idx + 1} / ${qs.length} · ✅ ${correct}</span></div>
      <div class="progressbar"><i style="width:${100 * idx / qs.length}%"></i></div>
      ${st.practice ? `<p class="muted">🧪 Practice run: nothing is saved</p>` : ""}
      <div class="card"><div id="q"></div><div id="hint"></div><div id="fb"></div>
        <div class="row" style="margin-top:16px">
          ${q.has_hint ? `<button class="btn ghost small" id="hintbtn">💡 Hint</button>` : ""}
          <span class="spacer"></span>
          <button class="btn" id="submit" disabled>Check</button>
        </div>
      </div></div>`;
    const submit = $("#submit");
    const r = renderQuestion($("#q"), q, () => submit.disabled = !r.ready());
    if (q.type === "order") submit.disabled = false;
    const doSubmit = async () => {
      if (submit.disabled) return;
      submit.disabled = true;
      const given = r.getAnswer();
      const res = await api("/api/answer", { qid: q.id, answer: given, review });
      if (res.correct) correct++;
      r.lock(res, given);
      $("#fb").innerHTML = feedbackHtml(res, q);
      submit.textContent = idx + 1 < qs.length ? "Next →" : "Finish";
      submit.disabled = false;
      submit.onclick = () => { idx++; idx < qs.length ? show() : finish(); };
      submit.focus();
    };
    submit.onclick = doSubmit;
    const fillInput = $("input.fill");
    if (fillInput) fillInput.onkeydown = (e) => { if (e.key === "Enter") doSubmit(); };
    const hb = $("#hintbtn");
    if (hb) hb.onclick = async () => {
      hb.disabled = true; hints++;
      const h = await api("/api/hint", { qid: q.id });
      $("#hint").innerHTML = `<div class="hintbox">💡 ${inline(h.hint)}</div>`;
    };
  };
  const finish = async () => {
    if (review) {
      await refreshHud();
      app.innerHTML = `<div class="results card"><h1>♻️ Respawn round done</h1><p class="bigstars pop">${correct}/${qs.length}</p>
        <p class="muted">Questions leave the respawn queue after you answer them right twice in a row.</p>
        <div class="row" style="justify-content:center">${OV.review_count ? `<button class="btn" id="again">Another round (${OV.review_count} left)</button>` : ""}<a class="btn ghost" href="#/">Back to map</a></div></div>`;
      const again = $("#again"); if (again) again.onclick = route;
      return;
    }
    const res = await api("/api/stage/finish", { w: st.world.id, s: st.id, correct, hints });
    await refreshHud();
    const next = nextAfter(st.world.id, st.id);
    app.innerHTML = `<div class="results card">
      <h1>${res.passed ? (st.boss ? "👹 Boss defeated!" : "Stage clear!") : "💀 Not this time"}</h1>
      <div class="bigstars pop">${"★".repeat(res.stars)}<span class="off">${"★".repeat(3 - res.stars)}</span></div>
      <p>${correct} / ${qs.length} correct (${res.score}%) · need ${Math.round(st.pass * 100)}% to pass${hints ? ` · ${hints} hint${hints > 1 ? "s" : ""} used` : ""}</p>
      ${res.bonus ? `<p class="muted">+${res.bonus} XP star bonus</p>` : ""}
      ${res.practice ? `<p class="muted">🧪 Practice run: these stars and XP weren't saved.</p>` : ""}
      ${res.passed || res.practice ? "" : `<p class="muted">Wrong answers were added to your ♻️ Respawn queue. Re-read the lesson and try again!</p>`}
      <div class="row" style="justify-content:center;margin-top:12px">
        <button class="btn ghost" id="retry">↻ Retry</button>
        ${res.passed ? `<a class="btn" href="${next}">Next →</a>` : ""}
        <a class="btn ghost" href="#/">Map</a>
      </div></div>`;
    $("#retry").onclick = route;
  };
  show();
}

// ------------------------------------------------------------------ review
async function viewReview() {
  const data = await api("/api/review");
  if (!data.questions.length) {
    app.innerHTML = `<div class="results card"><h1>♻️ Respawn queue is empty</h1><p class="muted">Questions you get wrong show up here so you can practice them again. Nothing to review right now. Nice work!</p><a class="btn" href="#/">Back to map</a></div>`;
    return;
  }
  const st = { title: `Respawn round (${data.questions.length} of ${data.total})`, questions: data.questions, boss: false, world: {} };
  runQuiz(st, `<div class="crumbs"><a href="#/">Map</a> › ♻️ Respawn</div>`, { review: true });
}

// ------------------------------------------------------------------ lab
async function viewLab(st) {
  app.classList.add("wide");
  const w = st.world, L = st.lab;
  app.innerHTML = `<div class="crumbs"><a href="#/">Map</a> › ${w.icon} ${esc(w.title)} › 🛠️ ${esc(st.title)}</div>
    <div class="loading">Preparing your lab sandbox… (the first time a provider is needed, Terraform downloads it)</div>`;
  const opened = await api("/api/lab/open", { w: w.id, s: st.id });
  let files = opened.files;
  let current = files.find((f) => f.path === "main.tf")?.path || files[0]?.path;
  const dirty = new Set();
  const history = [];
  let hpos = 0;
  let hintsShown = 0;

  app.innerHTML = `<div class="crumbs"><a href="#/">Map</a> › ${w.icon} ${esc(w.title)} › 🛠️ ${esc(st.title)}</div>
  <div class="lab">
    <div class="side card lesson">
      <h1>🛠️ ${esc(st.title)}</h1>
      ${st.practice ? PRACTICE_NOTE : ""}
      ${md(st.lesson)}
      <h3>🎯 Your mission</h3>
      ${md(L.goal)}
      <h3>✅ Checks</h3>
      <ul class="checks" id="checks">${L.checks.map((c) => `<li>${inline(c)}</li>`).join("")}</ul>
      <div class="row">
        <button class="btn good" id="check">Check my work</button>
        ${L.hints ? `<button class="btn ghost small" id="hint">💡 Hint (${L.hints})</button>` : ""}
        ${L.solution ? `<button class="btn ghost small" id="sol">🏳️ Show solution</button>` : ""}
      </div>
      <div id="hints"></div>
      ${L.actions.length ? `<h3>🎭 Events</h3><p class="muted">Things that happen outside Terraform:</p><div class="row">${L.actions.map((a) => `<button class="btn warn small" data-act="${a.id}">${esc(a.label)}</button>`).join("")}</div>` : ""}
      ${L.backend_panel ? `<h3>🗄️ Game's HTTP backend</h3><div class="backend" id="backend">…</div>` : ""}
      <h3>Lab folder</h3>
      <p class="muted" style="word-break:break-all"><code>${esc(opened.dir)}</code><br>You can also open this folder in your own editor and terminal.</p>
      <div class="row"><button class="btn danger small" id="reset">↺ Reset lab</button><a class="btn ghost small" href="#/">Map</a></div>
      ${st.record.stars ? `<p class="muted">Best: ${starsHtml(st.record.stars)}</p>` : ""}
    </div>
    <div>
      <div class="tabs" id="tabs"></div>
      <textarea class="editor" id="editor" spellcheck="false"></textarea>
      <div class="row" style="margin-top:8px">
        <button class="btn small" id="save">💾 Save (Ctrl+S)</button>
        <button class="btn ghost small" id="newfile">＋ New file</button>
        <button class="btn ghost small" id="delfile">🗑 Delete file</button>
        <span class="spacer"></span><span class="muted" style="font-size:12.5px">Files save automatically before each command.</span>
      </div>
      <div class="term">
        <div class="quick">${L.suggested.map((c) => `<button data-cmd="${esc(c)}">${esc(c)}</button>`).join("")}<button data-cmd="clear">clear</button></div>
        <pre id="out"></pre>
        <div class="prompt"><span>$</span><input class="cmd" id="cmd" placeholder="terraform init" autocomplete="off" spellcheck="false"></div>
      </div>
    </div>
  </div>`;

  const out = $("#out"), ed = $("#editor");
  const print = (html) => { out.innerHTML += html; out.scrollTop = out.scrollHeight; };
  if (opened.setup_output) print(`<span class="muted"># Lab setup ran these commands for you:\n${esc(opened.setup_output)}\n\n</span>`);
  print(`<span class="muted"># Type terraform commands below, or click a shortcut. apply/destroy get -auto-approve automatically.\n</span>`);

  const fileObj = (p) => files.find((f) => f.path === p);
  const drawTabs = () => {
    $("#tabs").innerHTML = files.map((f) => `<button class="tab ${f.path === current ? "active" : ""} ${dirty.has(f.path) ? "dirty" : ""} ${f.readonly ? "ro" : ""}" data-p="${esc(f.path)}">${esc(f.path)}</button>`).join("");
    $$(".tab").forEach((t) => t.onclick = () => { stash(); current = t.dataset.p; drawEditor(); drawTabs(); });
  };
  const drawEditor = () => {
    const f = fileObj(current);
    ed.value = f ? f.content : "";
    ed.readOnly = !f || f.readonly;
  };
  const stash = () => {
    const f = fileObj(current);
    if (f && !f.readonly && f.content !== ed.value) { f.content = ed.value; dirty.add(f.path); }
  };
  const saveAll = async () => {
    stash();
    for (const p of [...dirty]) {
      await api("/api/lab/save", { w: w.id, s: st.id, path: p, content: fileObj(p).content });
      dirty.delete(p);
    }
    drawTabs();
  };
  const mergeFiles = (fresh) => {
    // keep unsaved edits; refresh everything else (state files, generated files, logs)
    stash();
    const keep = new Map(files.filter((f) => dirty.has(f.path)).map((f) => [f.path, f.content]));
    files = fresh.map((f) => keep.has(f.path) ? { ...f, content: keep.get(f.path) } : f);
    if (!fileObj(current)) current = files[0]?.path;
    drawTabs(); drawEditor();
  };
  ed.addEventListener("input", () => { const f = fileObj(current); if (f && !f.readonly) { dirty.add(f.path); drawTabsLite(); } });
  const drawTabsLite = () => $$(".tab").forEach((t) => t.classList.toggle("dirty", dirty.has(t.dataset.p)));
  ed.addEventListener("keydown", (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const s = ed.selectionStart, en = ed.selectionEnd;
      ed.setRangeText("  ", s, en, "end");
      ed.dispatchEvent(new Event("input"));
    }
  });
  const onKey = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); saveAll().then(() => toast("💾 Saved")); }
  };
  document.addEventListener("keydown", onKey);
  cleanup = () => { document.removeEventListener("keydown", onKey); clearInterval(backendTimer); };

  let busy = false;
  const runCmd = async (cmd) => {
    cmd = cmd.trim();
    if (!cmd || busy) return;
    if (cmd === "clear") { out.innerHTML = ""; return; }
    if (!/^(terraform\b|echo\b|[A-Z_]+=)/.test(cmd)) cmd = "terraform " + cmd;
    history.push(cmd); hpos = history.length;
    busy = true;
    $("#cmd").disabled = true;
    print(`<span class="c-cmd">$ ${esc(cmd)}</span>\n<span class="muted" id="running">running…</span>`);
    try {
      await saveAll();
      const r = await api("/api/lab/run", { w: w.id, s: st.id, cmd });
      $("#running")?.remove();
      print(`${r.code ? `<span class="c-err">${esc(r.output)}</span>` : esc(r.output)}\n${r.code ? `<span class="c-err">(exit ${r.code})</span>\n` : ""}\n`);
      mergeFiles(r.files);
    } catch (e) {
      $("#running")?.remove();
      print(`<span class="c-err">${esc(e.message)}</span>\n\n`);
    }
    busy = false;
    $("#cmd").disabled = false;
    $("#cmd").focus();
    if (L.backend_panel) loadBackend();
  };
  $("#cmd").onkeydown = (e) => {
    if (e.key === "Enter") { const v = e.target.value; e.target.value = ""; runCmd(v); }
    else if (e.key === "ArrowUp" && hpos > 0) { e.target.value = history[--hpos]; e.preventDefault(); }
    else if (e.key === "ArrowDown") { hpos = Math.min(history.length, hpos + 1); e.target.value = history[hpos] || ""; }
  };
  $$(".quick button").forEach((b) => b.onclick = () => {
    // commands with a <PLACEHOLDER> go into the prompt for the player to complete
    if (b.dataset.cmd.includes("<")) { const c = $("#cmd"); c.value = b.dataset.cmd; c.focus(); c.setSelectionRange(c.value.indexOf("<"), c.value.length); }
    else runCmd(b.dataset.cmd);
  });
  $("#save").onclick = () => saveAll().then(() => toast("💾 Saved"));
  $("#newfile").onclick = async () => {
    const name = prompt("New file name (for example variables.tf or modules/greeter/main.tf):");
    if (!name) return;
    if (fileObj(name)) { current = name; drawTabs(); drawEditor(); return; }
    stash();
    files.push({ path: name, content: "", readonly: false });
    await api("/api/lab/save", { w: w.id, s: st.id, path: name, content: "" });
    current = name; drawTabs(); drawEditor(); ed.focus();
  };
  $("#delfile").onclick = async () => {
    const f = fileObj(current);
    if (!f || !confirm(`Delete ${f.path}?`)) return;
    await api("/api/lab/delete_file", { w: w.id, s: st.id, path: f.path });
    dirty.delete(f.path);
    files = files.filter((x) => x !== f);
    current = files[0]?.path;
    drawTabs(); drawEditor();
  };
  $("#reset").onclick = async () => {
    if (!confirm("Reset this lab?\n\nYour files and state are replaced with the starting version, and the lab's stars are cleared so you can earn them again. XP you've already earned is kept, but redoing the lab doesn't pay it twice.")) return;
    app.innerHTML = `<div class="loading">Resetting lab…</div>`;
    await api("/api/lab/reset", { w: w.id, s: st.id });
    route();
  };
  $$("[data-act]").forEach((b) => b.onclick = async () => {
    const r = await api("/api/lab/action", { w: w.id, s: st.id, action: b.dataset.act });
    print(`<span class="hl-n"># EVENT: ${esc(r.message)}</span>\n\n`);
    mergeFiles(r.files);
    if (L.backend_panel) loadBackend();
  });
  const hb = $("#hint");
  if (hb) hb.onclick = async () => {
    if (hintsShown >= L.hints) return;
    const h = await api("/api/lab/hint", { w: w.id, s: st.id, i: hintsShown });
    hintsShown++;
    $("#hints").innerHTML += `<div class="hintbox">💡 ${md(h.hint)}</div>`;
    hb.textContent = hintsShown < L.hints ? `💡 Next hint (${L.hints - hintsShown})` : "💡 No more hints";
    if (hintsShown >= L.hints) hb.disabled = true;
  };
  const sb = $("#sol");
  if (sb) sb.onclick = async () => {
    if (!confirm("Show the full solution? You can still pass the lab, but only for 1 star.")) return;
    const r = await api("/api/lab/solution", { w: w.id, s: st.id });
    $("#hints").innerHTML += `<div class="hintbox"><b>Solution</b>${md(r.solution)}</div>`;
    sb.disabled = true;
  };
  $("#check").onclick = async () => {
    const btn = $("#check");
    btn.disabled = true; btn.textContent = "Checking…";
    try {
      await saveAll();
      const r = await api("/api/lab/check", { w: w.id, s: st.id });
      $("#checks").innerHTML = r.results.map((c) => `<li class="${c.ok ? "ok" : "no"}">${inline(c.msg)}${!c.ok && c.detail ? `<span class="detail">${esc(c.detail)}</span>` : ""}</li>`).join("")
        + L.checks.slice(r.results.length).map((c) => `<li>${inline(c)}</li>`).join("");
      if (r.passed) {
        await refreshHud();
        const next = nextAfter(w.id, st.id);
        $("#hints").innerHTML = `<div class="feedback ok"><h4>🎉 Lab complete! ${starsHtml(r.stars)}</h4>
          ${r.practice ? `<p class="muted">🧪 Practice run: these stars and XP weren't saved.</p>` : ""}
          <p>${r.bonus ? `+${r.bonus} XP · ` : ""}checked ${r.attempts} time${r.attempts > 1 ? "s" : ""}${r.hints ? `, ${r.hints >= 99 ? "solution viewed" : r.hints + " hint(s)"}` : ""}.</p>
          <a class="btn" href="${next}">Next →</a></div>`;
        toast(`🎉 Lab complete! ${"★".repeat(r.stars)}`);
      } else toast("Not yet. Look at the ✘ checks for clues");
    } catch (e) { toast(esc(e.message)); }
    btn.disabled = false; btn.textContent = "Check my work";
  };

  let backendTimer = null;
  const loadBackend = async () => {
    const el = $("#backend"); if (!el) return;
    const list = await api("/api/backend");
    el.innerHTML = list.length ? `<table><tr><th>State</th><th>Resources</th><th>Serial</th><th>Lock</th></tr>${list.map((s) => `<tr><td><code>${esc(s.name)}</code></td><td>${s.resources}</td><td>${s.serial ?? "–"}</td><td>${s.lock ? `🔒 ${esc(s.lock.Who || "")}<br><small><code>${esc(s.lock.ID)}</code></small>` : "🔓"}</td></tr>`).join("")}</table>` : `<p class="muted">No states stored yet.</p>`;
  };
  if (L.backend_panel) { loadBackend(); backendTimer = setInterval(loadBackend, 3000); }

  drawTabs(); drawEditor();
  if (opened.passed) $("#hints").innerHTML = `<div class="feedback ok"><h4>✅ You already completed this lab</h4><p>Feel free to keep experimenting, or reset it to try again.</p></div>`;
}

// ------------------------------------------------------------------ exam
async function viewExamIntro() {
  const ex = OV.exam;
  if (!ex.unlocked) {
    app.innerHTML = `<div class="results card"><h1>🏁 Final Boss</h1><p>🔒 Defeat every world boss to unlock the practice exam.</p><p class="muted">Want to try it anyway? Turn on practice mode in ⚙️ Settings.</p><a class="btn" href="#/">Back to map</a></div>`;
    return;
  }
  app.innerHTML = `<div class="card lesson" style="max-width:820px;margin:0 auto">
    <h1>🏁 Final Boss: Terraform Associate (004) practice exam</h1>
    <ul>
      <li><b>${ex.questions} questions</b>, <b>${ex.minutes} minutes</b>. Questions are spread across the 8 official objectives.</li>
      <li>No feedback until you submit, just like the real exam. You can flag questions and jump around.</li>
      <li>Passing target: <b>70%</b>. HashiCorp doesn't publish the real passing score; 70% is a common, safe target.</li>
      <li>Every question you miss goes to your ♻️ Respawn queue.</li>
    </ul>
    ${ex.practice ? PRACTICE_NOTE : ""}
    ${ex.history.length ? `<h3>Previous attempts</h3><table><tr><th>Date</th><th>Score</th><th>Time</th><th></th></tr>${ex.history.slice().reverse().map((h) => `<tr><td>${esc(h.date)}</td><td>${h.score}% (${h.correct}/${h.total})</td><td>${Math.round(h.seconds / 60)} min</td><td>${h.passed ? "✅ Pass" : "❌"}${h.practice ? " 🧪" : ""}</td></tr>`).join("")}</table>` : ""}
    <button class="btn" id="start" style="margin-top:14px">Start the exam ⏱️</button>
  </div>`;
  $("#start").onclick = runExam;
}

async function runExam() {
  const ex = await api("/api/exam/start");
  const qs = ex.questions;
  const answers = {}, flags = new Set();
  let idx = 0, renderer = null;
  const deadline = Date.now() + ex.minutes * 60000;
  app.classList.add("wide");
  app.innerHTML = `<div class="exam">
    <div class="card"><div class="row"><b>Question <span id="qn"></span> / ${qs.length}</b><span class="spacer"></span><button class="btn ghost small" id="flag">🚩 Flag</button></div>
      <div id="q" style="margin-top:12px"></div>
      <div class="row" style="margin-top:18px"><button class="btn ghost" id="prev">← Prev</button><span class="spacer"></span><button class="btn" id="next">Next →</button></div>
    </div>
    <div class="nav card"><div class="timer" id="timer"></div><div class="muted" id="count"></div>
      <div class="qgrid" id="grid"></div>
      <p class="muted" style="font-size:12.5px">Purple = answered · yellow outline = flagged</p>
      <button class="btn good" id="submit" style="width:100%">Submit exam</button></div>
  </div>`;
  const store = () => {
    if (!renderer) return;
    const q = qs[idx];
    if (renderer.ready() && (q.type !== "order" || answers[q.id] !== undefined || renderer.touched)) answers[q.id] = renderer.getAnswer();
  };
  const drawGrid = () => {
    $("#grid").innerHTML = qs.map((q, i) => `<button class="${answers[q.id] !== undefined ? "ans" : ""} ${flags.has(i) ? "flag" : ""} ${i === idx ? "cur" : ""}" data-i="${i}">${i + 1}</button>`).join("");
    $$("#grid button").forEach((b) => b.onclick = () => go(+b.dataset.i));
    $("#count").textContent = `${Object.keys(answers).length} of ${qs.length} answered`;
  };
  const go = (i) => {
    store();
    idx = Math.max(0, Math.min(qs.length - 1, i));
    const q = qs[idx];
    $("#qn").textContent = idx + 1;
    renderer = renderQuestion($("#q"), q, () => { store(); drawGrid(); });
    if (q.type === "order") {
      renderer.touched = answers[q.id] !== undefined;
      const ul = $("#q .orderlist");
      if (answers[q.id]) answers[q.id].forEach((k) => ul.appendChild(ul.querySelector(`[data-k="${k}"]`)));
      $$("#q .orderlist li").forEach((li, n) => li.querySelector(".num").textContent = n + 1);
      $("#q .orderlist").addEventListener("click", () => { renderer.touched = true; store(); drawGrid(); });
      $("#q .orderlist").addEventListener("dragend", () => { renderer.touched = true; store(); drawGrid(); });
    } else if (answers[q.id] !== undefined) {
      const a = answers[q.id];
      if (q.type === "fill") $("#q input.fill").value = a;
      else [].concat(a).forEach((i) => $(`#q .opt[data-i="${i}"]`)?.click());
    }
    $("#flag").textContent = flags.has(idx) ? "🚩 Unflag" : "🚩 Flag";
    drawGrid();
  };
  $("#prev").onclick = () => go(idx - 1);
  $("#next").onclick = () => go(idx + 1);
  $("#flag").onclick = () => { flags.has(idx) ? flags.delete(idx) : flags.add(idx); go(idx); };
  let done = false;
  const submit = async (auto) => {
    if (done) return;
    store();
    const left = qs.length - Object.keys(answers).length;
    if (!auto && !confirm(left ? `${left} question(s) unanswered. Submit anyway?` : "Submit your exam?")) return;
    done = true;
    clearInterval(timer);
    const res = await api("/api/exam/submit", { id: ex.id, answers });
    showExamResults(res);
  };
  $("#submit").onclick = () => submit(false);
  const tick = () => {
    const s = Math.max(0, Math.round((deadline - Date.now()) / 1000));
    const t = $("#timer");
    if (!t) return;
    t.textContent = `⏱️ ${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
    t.classList.toggle("low", s < 300);
    if (s === 0) { toast("⏰ Time's up! Submitting…"); submit(true); }
  };
  const timer = setInterval(tick, 1000);
  tick();
  const beforeUnload = (e) => { if (!done) { e.preventDefault(); e.returnValue = ""; } };
  window.addEventListener("beforeunload", beforeUnload);
  cleanup = () => { clearInterval(timer); window.removeEventListener("beforeunload", beforeUnload); };
  go(0);
}

async function showExamResults(res) {
  await refreshHud();
  const color = (r) => r >= 0.8 ? "var(--good)" : r >= 0.7 ? "var(--warn)" : "var(--bad)";
  const fmtGiven = (d) => {
    if (d.given === undefined || d.given === null || (Array.isArray(d.given) && !d.given.length)) return "<i>no answer</i>";
    if (d.options) return [].concat(d.given).map((i) => inline(d.options[i] ?? "?")).join("; ");
    if (d.items) return d.given.map((i) => inline(d.items[i])).join(" → ");
    return `<code>${esc(d.given)}</code>`;
  };
  const fmtRight = (d) => d.options ? [].concat(d.answer).map((i) => inline(d.options[i])).join("; ") : d.items ? d.items.map(inline).join(" → ") : `<code>${esc(d.answer)}</code>`;
  app.innerHTML = `<div class="card" style="max-width:900px;margin:0 auto">
    <div class="results" style="margin:0 auto">
      <h1>${res.passed ? "🏆 Final Boss defeated!" : "💀 The Final Boss wins this round"}</h1>
      <div class="bigstars pop" style="font-size:64px">${res.score}%</div>
      <p>${res.correct} / ${res.total} correct in ${Math.round(res.seconds / 60)} min · ${res.practice ? "🧪 practice run, no XP or Respawn changes" : `+${res.xp} XP`}</p>
      <p class="muted">${res.passed ? "You're in passing range. Do a few more runs and book the real exam once you score 80% or more every time." : "Aim for 80% or higher. Work through the weakest objectives below, then come back."}</p>
    </div>
    <h2>By objective</h2>
    ${Object.entries(res.objectives).map(([k, o]) => { const r = o.correct / o.total; return `<div class="objbar"><span>${k}. ${esc(o.name)}</span><b>${o.correct}/${o.total}</b><div class="bar"><i style="width:${100 * r}%;background:${color(r)}"></i></div></div>`; }).join("")}
    <h2>Review your answers</h2>
    <div class="row"><label><input type="checkbox" id="onlywrong" checked> Show only wrong answers</label></div>
    <div id="rev">${res.details.map((d, i) => `<div class="review-item ${d.correct ? "is-ok" : "is-no"}" ${d.correct ? 'style="display:none"' : ""}>
      <div class="qtype">${i + 1}. ${d.correct ? "✅" : "❌"} objective ${esc(d.question.obj)}</div>
      <div class="qtext">${inline(d.question.q)}</div>
      ${d.question.code ? `<pre><code>${highlight(d.question.code, "hcl")}</code></pre>` : ""}
      <p><b>Your answer:</b> ${fmtGiven(d)}</p><p><b>Correct:</b> ${fmtRight(d)}</p>
      ${d.explain ? `<div class="lesson muted">${md(d.explain)}</div>` : ""}
    </div>`).join("")}</div>
    <div class="row" style="margin-top:18px"><a class="btn" href="#/exam">Back to exam page</a><a class="btn ghost" href="#/review">♻️ Practice missed questions</a></div>
  </div>`;
  $("#onlywrong").onchange = (e) => $$(".review-item.is-ok").forEach((el) => el.style.display = e.target.checked ? "none" : "");
}

// ------------------------------------------------------------------ settings
async function viewSettings() {
  const ov = OV;
  app.innerHTML = `<div class="card lesson" style="max-width:760px;margin:0 auto">
    <h1>⚙️ Settings & stats</h1>
    <table>
      <tr><th>Terraform on PATH</th><td>${ov.terraform ? `<code>v${esc(ov.terraform)}</code>` : "❌ not found. Labs won't work."}</td></tr>
      <tr><th>Level</th><td>${ov.player.level} · ${esc(ov.player.title)} (${ov.player.xp} XP)</td></tr>
      <tr><th>Answers</th><td>${ov.answered} answered, ${ov.accuracy ?? "–"}% correct</td></tr>
      <tr><th>Streak</th><td>${ov.streak.count} day(s), best ${ov.streak.best}</td></tr>
      <tr><th>Practice exams</th><td>${ov.exam.history.length} taken, best ${ov.exam.best ?? "–"}%</td></tr>
    </table>
    <h3>Practice mode</h3>
    <label class="row"><input type="checkbox" id="unlock" ${ov.settings.unlock_all ? "checked" : ""}> Unlock every world, stage and the Final Boss (good for reviewing before the exam)</label>
    <p class="muted">Stages you haven't reached yet are marked 🧪 and count as practice runs: no XP, stars or Respawn changes are saved. Stages you've already unlocked normally still count.</p>
    <h3>Content</h3>
    <p class="muted">Edited the TOML files in <code>content/worlds/</code>? Reload them without restarting the server.</p>
    <button class="btn ghost" id="reload">↻ Reload content</button>
    <h3>Danger zone</h3>
    <div class="row">
      <button class="btn danger" id="reset">Reset progress</button>
      <button class="btn danger" id="resetall">Reset progress + delete all labs</button>
    </div>
  </div>`;
  $("#unlock").onchange = async (e) => { await api("/api/settings", { unlock_all: e.target.checked }); toast(e.target.checked ? "🔓 Practice mode on" : "🔒 Practice mode off"); refreshHud(); };
  $("#reload").onclick = async () => { try { const r = await api("/api/reload", {}); toast(`✅ Reloaded: ${r.questions} questions`); } catch (e) { toast("❌ " + esc(e.message), 6000); } };
  $("#reset").onclick = async () => { if (confirm("Reset all XP, stars and history?")) { await api("/api/reset", {}); toast("Progress reset"); route(); } };
  $("#resetall").onclick = async () => { if (confirm("Reset progress AND delete every lab folder and the game's backend states?")) { await api("/api/reset", { labs: true }); toast("Everything reset"); route(); } };
}

route();
