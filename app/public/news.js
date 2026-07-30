/* Newsroom — editorial rubrics, not a flat commodity filter. A lead story +
   a live "price in focus" card open the page, then thematic sections:
   Geopolitics · Deals & Contracts · Companies · Markets, each a scannable strip
   of cards. A commodity filter stays available as a secondary lens.
   Data: Supabase (rubric-tagged at ingestion). All external fields escaped. */
(function () {
  "use strict";
  const C = window.COMMODITIES;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => (s || "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // rubric key → [label, standfirst]
  const RUBRICS = [
    ["geopolitics", "Geopolitics", "Sanctions · OPEC · supply risk"],
    ["contracts", "Deals & Contracts", "Offtakes · projects · M&A"],
    ["company", "Companies", "Earnings · results · moves"],
    ["markets", "Markets", "Prices · demand · flows"],
  ];

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
  const fmtNum = (n) => (n >= 1000 ? Math.round(n).toLocaleString("en-US")
    : (Math.round(n * 100) / 100).toString());

  const safeImg = (u) => (typeof u === "string" &&
    /^https?:\/\/[^\s"'()<>]+$/.test(u)) ? u : null;

  function thumbStyle(a) {
    const img = safeImg(a.image);
    const c = C.color((a.tags || [])[0] || "crude");
    const grad = `linear-gradient(135deg, color-mix(in srgb, ${c} 46%, #fff), ` +
      `color-mix(in srgb, ${c} 14%, #fff))`;
    return img ? `background:${grad};background-image:url('${img}');` +
      `background-size:cover;background-position:center` : `background:${grad}`;
  }

  function commTag(a) {
    const tag = (a.tags || [])[0];
    return tag ? `<span class="acard-tag" style="color:${C.color(tag)}">` +
      `<span class="d" style="background:${C.color(tag)}"></span>${esc(C.label(tag))}</span>` : "";
  }

  function acard(a) {
    return `<a class="acard" href="${esc(a.url)}" target="_blank" rel="noopener">` +
      `<div class="acard-img" style="${thumbStyle(a)}"></div>` +
      `<div class="acard-b">${commTag(a)}` +
      `<div class="acard-t">${esc(a.title)}</div>` +
      `<div class="acard-m"><span>${esc(a.source || "")}</span><span>${esc(ago(a.date))}</span></div>` +
      `</div></a>`;
  }

  // Big lead card for the freshest strong story.
  function heroCard(a) {
    return `<a class="hero-lead" href="${esc(a.url)}" target="_blank" rel="noopener">` +
      `<div class="hero-img" style="${thumbStyle(a)}"></div>` +
      `<div class="hero-b"><span class="hero-eyebrow">Today</span>` +
      `<h2 class="hero-t">${esc(a.title)}</h2>` +
      `<div class="hero-m">${commTag(a)}<span>${esc(a.source || "")}</span>` +
      `<span>·</span><span>${esc(ago(a.date))}</span></div></div></a>`;
  }

  // Tiny sparkline (last ~70 pts), ink stroke to match the mono system.
  function sparkSVG(pts) {
    const v = pts.slice(-70).map((d) => d[1]);
    if (v.length < 2) return "";
    const w = 132, h = 40, pad = 4;
    const mn = Math.min(...v), mx = Math.max(...v), rng = (mx - mn) || 1;
    const step = w / (v.length - 1);
    const d = v.map((y, i) =>
      `${i ? "L" : "M"}${(i * step).toFixed(1)},${(pad + (h - 2 * pad) * (1 - (y - mn) / rng)).toFixed(1)}`
    ).join("");
    return `<svg class="pf-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">` +
      `<path d="${d}" fill="none" stroke="#0A0A0A" stroke-width="1.6" ` +
      `stroke-linejoin="round" stroke-linecap="round"/></svg>`;
  }

  // "Price in focus": the biggest mover among priced commodities + its latest story.
  function priceCard(series) {
    const cand = Object.keys(series).map((k) => {
      const p = series[k] || [];
      if (p.length < 2) return null;
      const last = p[p.length - 1][1];
      const prev = p[Math.max(0, p.length - 1 - 21)][1];
      return { k, last, chg: prev ? 100 * (last - prev) / prev : 0, pts: p };
    }).filter(Boolean);
    if (!cand.length) return "";
    cand.sort((a, b) => Math.abs(b.chg) - Math.abs(a.chg));
    const f = cand[0];
    const dir = f.chg >= 0 ? "up" : "down";
    const rel = articles.find((a) => (a.tags || []).includes(f.k));
    return `<div class="price-focus" style="--c:${C.color(f.k)}">` +
      `<span class="pf-eyebrow">Price in focus</span>` +
      `<div class="pf-row"><span class="pf-dot"></span>` +
      `<span class="pf-name">${esc(C.label(f.k))}</span></div>` +
      `<div class="pf-px">${fmtNum(f.last)}<span class="pf-chg ${dir}">` +
      `${f.chg >= 0 ? "+" : ""}${f.chg.toFixed(1)}%</span></div>` +
      sparkSVG(f.pts) +
      (rel ? `<a class="pf-rel" href="${esc(rel.url)}" target="_blank" rel="noopener">` +
        `${esc(rel.title)}</a>` : "") +
      `<a class="pf-link" href="trading.html?commodity=${f.k}">Open chart →</a></div>`;
  }

  // ---- state ----
  let filter = C.clean(new URLSearchParams(location.search).get("commodity"));
  if (!C.ORDER.includes(filter)) filter = "all";
  let articles = [], series = {};

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
    mk("all", "All markets", null);
    C.ORDER.filter((k) => ct[k] > 0).sort((a, b) => ct[b] - ct[a])
      .forEach((k) => mk(k, C.label(k), C.color(k)));
  }

  const inFilter = (a) => filter === "all" || (a.tags || []).includes(filter);

  // Compact headline row with a small thumbnail — keeps many stories visible.
  function hitem(a) {
    return `<a class="hitem" href="${esc(a.url)}" target="_blank" rel="noopener">` +
      `<div class="hitem-img" style="${thumbStyle(a)}"></div>` +
      `<div class="hitem-b"><div class="hitem-t">${esc(a.title)}</div>` +
      `<div class="hitem-m">${commTag(a)}<span>${esc(a.source || "")}</span>` +
      `<span>·</span><span>${esc(ago(a.date))}</span></div></div></a>`;
  }

  // Medium photo-led card that opens each rubric block.
  function plead(a) {
    return `<a class="plead" href="${esc(a.url)}" target="_blank" rel="noopener">` +
      `<div class="plead-img" style="${thumbStyle(a)}"></div>` +
      `<div class="plead-b">${commTag(a)}<div class="plead-t">${esc(a.title)}</div>` +
      `<div class="plead-m"><span>${esc(a.source || "")}</span><span>${esc(ago(a.date))}</span></div>` +
      `</div></a>`;
  }

  // Right-rail "Latest" — the freshest stories as thumbnail rows.
  function topList(shown, exclude) {
    const arts = shown.filter((a) => a !== exclude).slice(0, 5);
    if (!arts.length) return "";
    return `<div class="top-list"><span class="tl-head">Latest</span>` +
      arts.map(hitem).join("") + `</div>`;
  }

  // A rubric block: a photo lead (a story with an image if there is one) + a
  // stack of headlines, so each theme shows real depth at a glance.
  function rubricBlock(key, label, sub) {
    const arts = articles.filter((a) => a.rubric === key && inFilter(a));
    if (!arts.length) return "";
    const lead = arts.find((a) => safeImg(a.image)) || arts[0];
    const rest = arts.filter((a) => a !== lead).slice(0, 5);
    return `<section class="rblock" id="sec-${key}">` +
      `<div class="rub-head"><div><h2 class="rub-name">${esc(label)}</h2>` +
      `<span class="rub-sub">${esc(sub)}</span></div>` +
      `<span class="rub-ct">${arts.length}</span></div>` +
      plead(lead) +
      (rest.length ? `<div class="hl-list">${rest.map(hitem).join("")}</div>` : "") +
      `</section>`;
  }

  function render() {
    const ct = counts();
    renderFilters(ct);
    const shown = articles.filter(inFilter);
    $("count").innerHTML = `<b>${shown.length}</b> stor${shown.length === 1 ? "y" : "ies"}` +
      (filter === "all" ? " · live" : " · " + esc(C.label(filter)));
    if (!shown.length) { $("feed").innerHTML = '<div class="empty">No stories yet.</div>'; return; }

    const lead = shown.find((a) => safeImg(a.image)) || shown[0];
    let html = `<div class="news-hero">${heroCard(lead)}` +
      `<div class="front-rail">${priceCard(series)}${topList(shown, lead)}</div></div>`;
    html += `<div class="rubric-grid">`;
    RUBRICS.forEach(([k, label, sub]) => { html += rubricBlock(k, label, sub); });
    html += `</div>`;
    const rest = shown.filter((a) => !RUBRICS.some(([k]) => k === a.rubric) && a !== lead);
    if (rest.length) {
      html += `<section class="rub-sec"><div class="rub-head"><div>` +
        `<h2 class="rub-name">More headlines</h2>` +
        `<span class="rub-sub">Across the sector</span></div></div>` +
        `<div class="news-grid">${rest.slice(0, 12).map(acard).join("")}</div></section>`;
    }
    $("feed").innerHTML = html;
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

  Promise.all([
    SB.get("news?select=title,url,source,published_date,commodities_tags,image,rubric" +
      "&order=published_date.desc&limit=1000"),
    SB.get("trading_series?select=commodity,points").catch(() => []),
  ]).then(([rows, ts]) => {
    articles = dedupe((rows || []).map((r) => ({
      title: r.title, url: r.url, source: r.source, date: r.published_date,
      tags: r.commodities_tags || [], image: r.image, rubric: r.rubric || "general",
    })));
    (ts || []).forEach((r) => { series[r.commodity] = r.points || []; });
    render();
  }).catch(() => {
    $("feed").innerHTML = '<div class="empty">Could not load the newsroom from Supabase.</div>';
  });
})();
