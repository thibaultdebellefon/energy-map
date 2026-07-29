/* Newsroom — Bloomberg-style: always-visible thematic sections (one per
   commodity), each an auto-scrolling carousel of article cards with photos, so
   the reader sees the full diversity of coverage at a glance. Filtering by a
   commodity switches to a full grid of that theme.
   Data: Supabase (relevance-filtered at ingestion). All external fields escaped. */
(function () {
  "use strict";
  const C = window.COMMODITIES;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => (s || "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function ago(dateStr) {
    if (!dateStr) return "";
    const then = new Date(dateStr + "T00:00:00Z"), now = new Date();
    const days = Math.floor((now - then) / 86400000);
    if (days <= 0) return "today";
    if (days === 1) return "yesterday";
    if (days < 7) return days + " days ago";
    const w = Math.floor(days / 7);
    return w + (w === 1 ? " week ago" : " weeks ago");
  }

  const safeImg = (u) => (typeof u === "string" &&
    /^https?:\/\/[^\s"'()<>]+$/.test(u)) ? u : null;

  // Card thumbnail: the article's own image, else a soft commodity-tinted
  // gradient (so a dead host degrades to colour, never a broken image).
  function thumbStyle(a) {
    const img = safeImg(a.image);
    const c = C.color((a.tags || [])[0] || "crude");
    const grad = `linear-gradient(135deg, color-mix(in srgb, ${c} 50%, #fff), ` +
      `color-mix(in srgb, ${c} 16%, #fff))`;
    return img ? `background:${grad};background-image:url('${img}');` +
      `background-size:cover;background-position:center` : `background:${grad}`;
  }

  function acard(a) {
    const tag = (a.tags || [])[0];
    return `<a class="acard" href="${esc(a.url)}" target="_blank" rel="noopener">` +
      `<div class="acard-img" style="${thumbStyle(a)}"></div>` +
      `<div class="acard-b">` +
      (tag ? `<span class="acard-tag" style="color:${C.color(tag)}">` +
        `<span class="d" style="background:${C.color(tag)}"></span>${esc(C.label(tag))}</span>` : "") +
      `<div class="acard-t">${esc(a.title)}</div>` +
      `<div class="acard-m"><span>${esc(a.source || "")}</span><span>${esc(ago(a.date))}</span></div>` +
      `</div></a>`;
  }

  let filter = C.clean(new URLSearchParams(location.search).get("commodity"));
  if (!C.ORDER.includes(filter)) filter = "all";
  let articles = [];

  function setFilter(f) {
    filter = f;
    const u = new URL(location.href);
    if (f === "all") u.searchParams.delete("commodity");
    else u.searchParams.set("commodity", f);
    history.replaceState(null, "", u);
    render();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function counts() {
    const c = { all: articles.length };
    C.ORDER.forEach((k) => { c[k] = 0; });
    articles.forEach((a) => (a.tags || []).forEach((t) => { if (c[t] != null) c[t]++; }));
    return c;
  }

  function renderFilters(ct) {
    const box = $("filters");
    box.innerHTML = "";
    const mk = (k, lbl, color) => {
      const el = document.createElement("span");
      el.className = "chip" + (filter === k ? " on" : "");
      if (color) el.style.setProperty("--c", color);
      el.innerHTML = (color ? `<span class="dot" style="background:${color}"></span>` : "") +
        `${esc(lbl)} <span class="ct">${ct[k] || 0}</span>`;
      el.onclick = () => setFilter(k);
      box.appendChild(el);
    };
    mk("all", "All", null);
    C.ORDER.filter((k) => ct[k] > 0).sort((a, b) => ct[b] - ct[a])
      .forEach((k) => mk(k, C.label(k), C.color(k)));
  }

  // one always-visible section per commodity, articles scrolling in a carousel
  function renderSections() {
    const byC = {};
    C.ORDER.forEach((k) => { byC[k] = []; });
    articles.forEach((a) => (a.tags || []).forEach((t) => { if (byC[t]) byC[t].push(a); }));
    const html = C.ORDER.filter((k) => byC[k].length).map((k, i) => {
      const arts = byC[k], col = C.color(k);
      const marquee = arts.length >= 5;                 // enough cards to loop
      const cards = arts.map(acard).join("");
      const track = marquee ? cards + cards : cards;    // duplicate for seamless loop
      const dur = Math.max(24, arts.length * 4.5);
      const dir = i % 2 ? " rev" : "";                  // alternate drift direction
      return `<section class="rubric" style="--c:${col}">` +
        `<div class="rubric-head">` +
        `<span class="rubric-dot"></span>` +
        `<h2 class="rubric-name">${esc(C.label(k))}</h2>` +
        `<span class="rubric-ct">${arts.length}</span>` +
        `<button class="rubric-all" data-k="${k}">View all →</button></div>` +
        `<div class="rubric-scroll${marquee ? " marq" : ""}">` +
        `<div class="rubric-track${marquee ? " run" + dir : ""}" style="--dur:${dur}s">${track}</div>` +
        `</div></section>`;
    }).join("");
    $("feed").innerHTML = html;
    $("feed").querySelectorAll(".rubric-all").forEach((b) => b.onclick = () => setFilter(b.dataset.k));
  }

  function renderGrid(k) {
    const arts = articles.filter((a) => (a.tags || []).includes(k));
    $("feed").innerHTML = arts.length
      ? `<div class="news-grid">${arts.map(acard).join("")}</div>`
      : `<div class="empty">No headlines for ${esc(C.label(k))} yet.</div>`;
  }

  function render() {
    const ct = counts();
    renderFilters(ct);
    const n = filter === "all" ? articles.length : (ct[filter] || 0);
    $("count").innerHTML = `<b>${n}</b> headline${n === 1 ? "" : "s"}` +
      (filter === "all" ? " indexed" : " · " + esc(C.label(filter)));
    if (!articles.length) {
      $("feed").innerHTML = '<div class="empty">No headlines yet.</div>'; return;
    }
    if (filter === "all") renderSections(); else renderGrid(filter);
  }

  function dedupe(list) {
    const norm = (t) => (t || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
    const seen = new Map();
    list.forEach((a) => {
      const k = norm(a.title);
      if (!k) return;
      const prev = seen.get(k);
      if (!prev) { seen.set(k, { ...a, tags: (a.tags || []).slice() }); return; }
      (a.tags || []).forEach((t) => { if (!prev.tags.includes(t)) prev.tags.push(t); });
    });
    return [...seen.values()];
  }

  SB.get("news?select=title,url,source,published_date,commodities_tags,image" +
    "&order=published_date.desc&limit=1000").then((rows) => {
    articles = dedupe(rows.map((r) => ({
      title: r.title, url: r.url, source: r.source,
      date: r.published_date, tags: r.commodities_tags || [], image: r.image,
    })));
    render();
  }).catch(() => {
    $("feed").innerHTML = '<div class="empty">Could not load the news feed from Supabase.</div>';
  });
})();
