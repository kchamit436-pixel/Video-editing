/* vidkit — Zeitleiste zum Bearbeiten der edit.json. Kein Framework, mit Absicht. */
(() => {
  const $ = (s) => document.querySelector(s);
  const KINDS = ["captions", "overlays", "zooms", "motion_graphics", "broll", "sfx"];
  const LABEL = { captions: "Captions", overlays: "Overlays", zooms: "Zooms",
                  motion_graphics: "Motion", broll: "B-Roll", sfx: "Sound" };
  const state = { doc: null, info: null, sel: null, pxPerSec: 90, dirty: false };

  const video = $("#video");
  const lanes = $("#lanes");
  const ruler = $("#ruler");

  const dur = () => (state.doc?.segments?.length
    ? Math.max(...state.doc.segments.map((s) => s.t_out)) : (state.doc?.duration || 0));
  const px = (t) => t * state.pxPerSec;
  const sec = (x) => x / state.pxPerSec;
  const round3 = (v) => Math.round(v * 1000) / 1000;

  function setStatus(text, isError) {
    const el = $("#status");
    el.textContent = text;
    el.style.color = isError ? "#ff8b8b" : "";
  }

  // --- Laden / Speichern ---------------------------------------------------
  async function load() {
    state.info = await (await fetch("/api/info")).json();
    $("#project").textContent = `Projekt „${state.info.project}"`;
    $("#videolabel").textContent = "Video: " + state.info.video_label;
    if (state.info.video) video.src = state.info.video;
    const res = await fetch("/api/edit");
    const doc = await res.json();
    if (doc.error) { setStatus(doc.error, true); return; }
    state.doc = doc;
    render();
    setStatus("geladen");
  }

  let saveTimer = null;
  function markDirty() {
    state.dirty = true;
    setStatus("ungespeichert");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, 1200);   // automatisch, aber nicht bei jedem Pixel
  }

  async function save() {
    if (!state.doc) return;
    clearTimeout(saveTimer);
    setStatus("speichere …");
    const res = await fetch("/api/edit", {
      method: "POST", headers: { "Content-Type": "application/json" },
      // Felder mit _ sind reine UI-Hilfen und haben in der edit.json nichts verloren
      body: JSON.stringify(state.doc, (k, v) => (k.startsWith("_") ? undefined : v)),
    });
    const out = await res.json();
    if (out.error) { setStatus(out.error, true); return; }
    state.dirty = false;
    setStatus("gespeichert");
  }

  // --- Zeitleiste ----------------------------------------------------------
  function render() {
    const total = dur();
    const width = Math.max(px(total) + 40, 400);

    ruler.innerHTML = "";
    ruler.style.width = width + "px";
    const stepSec = state.pxPerSec > 200 ? 0.25 : state.pxPerSec > 110 ? 0.5
      : state.pxPerSec > 55 ? 1 : 2;
    for (let t = 0; t <= total + 1e-6; t += stepSec) {
      const tick = document.createElement("i");
      tick.style.left = px(t) + "px";
      ruler.appendChild(tick);
      const lab = document.createElement("span");
      lab.style.left = px(t) + "px";
      lab.textContent = t.toFixed(stepSec < 1 ? 1 : 0) + "s";
      ruler.appendChild(lab);
    }

    lanes.innerHTML = "";
    lanes.style.width = width + "px";
    for (const kind of KINDS) {
      const lane = document.createElement("div");
      lane.className = "lane";
      lane.dataset.kind = kind;
      const name = document.createElement("div");
      name.className = "name";
      name.textContent = `${LABEL[kind]} (${(state.doc[kind] || []).length})`;
      lane.appendChild(name);
      for (const el of state.doc[kind] || []) lane.appendChild(blockFor(kind, el));
      lanes.appendChild(lane);
    }
    // Schnittkanten als Hilfslinien — eigener Container, sonst wachsen sie
    // bei jedem Neuzeichnen weiter an.
    let cuts = document.getElementById("cuts");
    if (!cuts) {
      cuts = document.createElement("div");
      cuts.id = "cuts";
      cuts.style.cssText = "position:absolute;top:0;left:0;right:0;bottom:0;pointer-events:none";
      $("#timeline").appendChild(cuts);
    }
    cuts.innerHTML = "";
    cuts.style.width = width + "px";
    for (const seg of state.doc.segments.slice(1)) {
      const cut = document.createElement("div");
      cut.style.cssText = `position:absolute;top:24px;bottom:0;width:1px;background:#3a4150;
        left:${px(seg.t_in)}px;`;
      cuts.appendChild(cut);
    }
    movePlayhead();
  }

  function blockFor(kind, el) {
    const b = document.createElement("div");
    const point = kind === "sfx";
    b.className = "block" + (point ? " point" : "") + (el.enabled === false ? " off" : "");
    b.dataset.kind = kind;
    b.dataset.id = el.id;
    b.style.background = `var(--${kind})`;
    if (point) {
      b.style.left = px(el.t) + "px";
      b.title = `${el.id} · ${el.category || ""} @ ${el.t.toFixed(2)}s`;
    } else {
      b.style.left = px(el.t_in) + "px";
      b.style.width = Math.max(8, px(el.t_out - el.t_in)) + "px";
      b.textContent = el.text || el.queries?.join(", ") || el.id;
      b.title = `${el.id} · ${el.t_in.toFixed(2)}–${el.t_out.toFixed(2)}s`;
      b.appendChild(Object.assign(document.createElement("div"), { className: "h l" }));
      b.appendChild(Object.assign(document.createElement("div"), { className: "h r" }));
    }
    if (state.sel && state.sel.id === el.id) b.classList.add("sel");
    b.addEventListener("mousedown", (ev) => startDrag(ev, kind, el, b));
    return b;
  }

  function find(kind, id) { return (state.doc[kind] || []).find((e) => e.id === id); }

  // --- Ziehen, Verlaengern -------------------------------------------------
  function startDrag(ev, kind, el, node) {
    ev.preventDefault();
    select(kind, el.id);
    const mode = ev.target.classList.contains("h")
      ? (ev.target.classList.contains("l") ? "left" : "right") : "move";
    const x0 = ev.clientX;
    const start = kind === "sfx" ? { t: el.t } : { t_in: el.t_in, t_out: el.t_out };
    const total = dur();
    let moved = false;

    function onMove(e) {
      const d = sec(e.clientX - x0);
      if (Math.abs(e.clientX - x0) < 2 && !moved) return;   // reiner Klick, keine Aenderung
      moved = true;
      if (kind === "sfx") {
        el.t = round3(Math.max(0, Math.min(total, start.t + d)));
        node.style.left = px(el.t) + "px";
      } else if (mode === "move") {
        const len = start.t_out - start.t_in;
        let t_in = Math.max(0, Math.min(total - len, start.t_in + d));
        el.t_in = round3(t_in); el.t_out = round3(t_in + len);
        node.style.left = px(el.t_in) + "px";
      } else if (mode === "left") {
        el.t_in = round3(Math.max(0, Math.min(start.t_out - 0.1, start.t_in + d)));
        node.style.left = px(el.t_in) + "px";
        node.style.width = Math.max(8, px(el.t_out - el.t_in)) + "px";
      } else {
        el.t_out = round3(Math.min(total, Math.max(start.t_in + 0.1, start.t_out + d)));
        node.style.width = Math.max(8, px(el.t_out - el.t_in)) + "px";
      }
      if (kind === "captions" && el.words) shiftWords(el, start);
      showInspector();
    }
    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      if (moved) markDirty();
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  // Wortzeiten einer Caption sind relativ zum Blockanfang — beim Verlaengern
  // muessen sie mitskaliert werden, sonst laeuft die Hervorhebung aus dem Takt.
  function shiftWords(el, start) {
    const oldLen = start.t_out - start.t_in;
    const newLen = el.t_out - el.t_in;
    if (oldLen <= 0 || Math.abs(newLen - oldLen) < 1e-6 || !el._w0) return;
    const f = newLen / oldLen;
    el.words = el._w0.map((w) => ({ w: w.w, t_in: round3(w.t_in * f), t_out: round3(w.t_out * f) }));
  }

  // --- Inspektor -----------------------------------------------------------
  function select(kind, id) {
    const el = find(kind, id);
    state.sel = el ? { kind, id, el } : null;
    if (el && el.words) el._w0 = el._w0 || el.words.map((w) => ({ ...w }));
    document.querySelectorAll(".block.sel").forEach((n) => n.classList.remove("sel"));
    const node = document.querySelector(`.block[data-id="${id}"]`);
    if (node) node.classList.add("sel");
    showInspector();
  }

  function showInspector() {
    const box = $("#inspector");
    if (!state.sel) { box.innerHTML = '<div class="empty muted">Klicke einen Block an.</div>'; return; }
    const { kind, el } = state.sel;
    const rows = [];
    rows.push(`<h3>${LABEL[kind]} · <span class="mono muted">${el.id}</span></h3>`);
    if (kind === "sfx") {
      rows.push(`<label>Zeit (s)</label><input data-f="t" type="number" step="0.01" value="${el.t}">`);
      rows.push(`<label>Kategorie</label><input data-f="category" value="${el.category || ""}">`);
      rows.push(`<label>Datei</label><input data-f="file" value="${el.file || ""}">`);
      rows.push(`<label>Pegel (dB)</label><input data-f="gain_db" type="number" step="0.5" value="${el.gain_db ?? -12}">`);
    } else {
      rows.push(`<div class="row"><div><label>Von (s)</label>
        <input data-f="t_in" type="number" step="0.01" value="${el.t_in}"></div>
        <div><label>Bis (s)</label>
        <input data-f="t_out" type="number" step="0.01" value="${el.t_out}"></div></div>`);
      if ("text" in el)
        rows.push(`<label>Text</label><textarea data-f="text" rows="2">${el.text || ""}</textarea>`);
      if (kind === "zooms")
        rows.push(`<div class="row"><div><label>von</label>
          <input data-f="from" type="number" step="0.01" value="${el.from}"></div>
          <div><label>bis</label>
          <input data-f="to" type="number" step="0.01" value="${el.to}"></div></div>`);
      if (kind === "broll") {
        rows.push(`<label>Suchbegriffe (Komma)</label>
          <input data-f="queries" value="${(el.queries || []).join(", ")}">`);
        rows.push(`<label>Datei / Auswahl</label><input data-f="file" value="${el.file || ""}">`);
      }
    }
    rows.push(`<label><input type="checkbox" data-f="enabled" ${el.enabled === false ? "" : "checked"}
      style="width:auto"> aktiv</label>`);
    rows.push(`<div class="row" style="margin-top:12px">
      <button id="seekto">Hierhin springen</button>
      <button id="del" class="danger">Löschen</button></div>`);
    box.innerHTML = rows.join("");

    box.querySelectorAll("[data-f]").forEach((input) => {
      input.addEventListener("change", () => {
        const f = input.dataset.f;
        let v = input.type === "checkbox" ? input.checked
          : input.type === "number" ? parseFloat(input.value) : input.value;
        if (f === "queries") v = String(v).split(",").map((s) => s.trim()).filter(Boolean);
        el[f] = v;
        markDirty();
        render();
      });
    });
    $("#seekto").onclick = () => { video.currentTime = kind === "sfx" ? el.t : el.t_in; };
    $("#del").onclick = () => {
      state.doc[kind] = state.doc[kind].filter((e) => e.id !== el.id);
      state.sel = null;
      markDirty();
      render();
    };
  }

  // --- Abspielkopf ---------------------------------------------------------
  function movePlayhead() {
    $("#playhead").style.left = px(video.currentTime || 0) + "px";
    $("#time").textContent = (video.currentTime || 0).toFixed(2) + " s";
  }
  video.addEventListener("timeupdate", movePlayhead);
  video.addEventListener("seeked", movePlayhead);
  $("#timeline").addEventListener("click", (ev) => {
    if (ev.target.closest(".block")) return;
    const rect = $("#lanes").getBoundingClientRect();
    video.currentTime = Math.max(0, sec(ev.clientX - rect.left));
  });

  // --- Kopfleiste ----------------------------------------------------------
  $("#save").onclick = save;
  $("#playpause").onclick = () => (video.paused ? video.play() : video.pause());
  document.querySelectorAll("[data-seek]").forEach((b) => {
    b.onclick = () => { video.currentTime = Math.max(0, video.currentTime + (+b.dataset.seek)); };
  });
  $("#scale").oninput = (e) => { state.pxPerSec = +e.target.value; render(); };

  async function runJob(url, body, label) {
    await save();
    const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
                                   body: JSON.stringify(body || {}) });
    const out = await res.json();
    if (!out.started) { setStatus("läuft bereits", true); return; }
    setStatus(label + " läuft …");
    $("#logbox").hidden = false;
    poll();
  }
  $("#render").onclick = () => runJob("/api/render", { preview: true }, "Render");
  $("#assets").onclick = () => runJob("/api/assets", {}, "Assets");

  async function poll() {
    const s = await (await fetch("/api/render/status")).json();
    const box = $("#logbox");
    box.textContent = s.lines.join("\n");
    box.scrollTop = box.scrollHeight;
    if (s.running) { setTimeout(poll, 700); return; }
    if (s.returncode === 0) {
      setStatus("fertig");
      const t = video.currentTime;
      video.src = state.info.video + "?t=" + Date.now();   // Cache umgehen
      video.addEventListener("loadedmetadata", () => { video.currentTime = t; }, { once: true });
    } else {
      setStatus("fehlgeschlagen (Code " + s.returncode + ")", true);
    }
  }

  window.addEventListener("keydown", (e) => {
    if (e.target.matches("input, textarea")) return;
    if (e.key === " ") { e.preventDefault(); video.paused ? video.play() : video.pause(); }
    if (e.key === "s" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); save(); }
    if ((e.key === "Backspace" || e.key === "Delete") && state.sel) $("#del")?.click();
  });
  window.addEventListener("beforeunload", (e) => { if (state.dirty) e.preventDefault(); });

  load();
})();
