/* Newsroom: commodity-filtered headlines from news.json.
   All article fields come from GDELT (external) and are HTML-escaped before
   they ever touch innerHTML. Reads/writes ?commodity= so a filter carries
   across sections. */
(function () {
  "use strict";
  const C = window.COMMODITIES;
  const esc = (s) => (s || "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // "3 hours ago", "2 days ago" — GDELT gives day precision, so this is coarse.
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

  function pill(k) {
    return `<span class="pill" style="--c:${C.color(k)}"><span class="dot"></span>${esc(C.label(k))}</span>`;
  }

  const PAGE_SIZE = 24; // headlines rendered per batch (after the lead story)

  let filter = C.clean(new URLSearchParams(location.search).get("commodity"));
  if (!C.ORDER.includes(filter)) filter = "all";
  let articles = [];
  let shown = PAGE_SIZE; // how many list items are currently revealed

  function setFilter(f) {
    filter = f;
    shown = PAGE_SIZE; // reset paging when the filter changes
    const u = new URL(location.href);
    if (f === "all") u.searchParams.delete("commodity");
    else u.searchParams.set("commodity", f);
    history.replaceState(null, "", u);
    render();
  }

  function counts() {
    const c = { all: articles.length };
    C.ORDER.forEach((k) => { c[k] = 0; });
    articles.forEach((a) => (a.tags || []).forEach((t) => { if (c[t] != null) c[t]++; }));
    return c;
  }

  function renderFilters(ct) {
    const box = document.getElementById("filters");
    box.innerHTML = "";
    const mk = (k, lbl, color) => {
      const el = document.createElement("span");
      el.className = "chip" + (filter === k ? " on" : "");
      if (color) el.style.setProperty("--c", color);
      const n = ct[k] || 0;
      el.innerHTML = (color ? `<span class="dot" style="background:${color}"></span>` : "") +
        `${esc(lbl)} <span class="ct">${n}</span>`;
      el.onclick = () => setFilter(k);
      box.appendChild(el);
    };
    mk("all", "All", null);
    // Only show commodities that actually have coverage, richest first.
    C.ORDER.filter((k) => ct[k] > 0)
      .sort((a, b) => ct[b] - ct[a])
      .forEach((k) => mk(k, C.label(k), C.color(k)));
  }

  function itemRow(a) {
    const tags = (a.tags || []).map(pill).join("");
    return `<a class="news-item" href="${esc(a.url)}" target="_blank" rel="noopener">` +
      `<div><div class="t">${esc(a.title)}</div>` +
      `<div class="m"><span class="src">${esc(a.source || "")}</span>` +
      `<span class="when">${esc(ago(a.date))}</span></div></div>` +
      `<div class="tags">${tags}</div></a>`;
  }

  function render() {
    const ct = counts();
    renderFilters(ct);
    document.getElementById("count").innerHTML =
      `<b>${filter === "all" ? articles.length : (ct[filter] || 0)}</b> ` +
      `headline${(filter === "all" ? articles.length : ct[filter]) === 1 ? "" : "s"}` +
      (filter === "all" ? " indexed" : " · " + esc(C.label(filter)));

    const items = articles.filter((a) => filter === "all" || (a.tags || []).includes(filter));
    const lead = document.getElementById("lead");
    const list = document.getElementById("list");
    const more = document.getElementById("more");

    if (!items.length) {
      lead.innerHTML = "";
      more.innerHTML = "";
      list.innerHTML = `<div class="empty">No headlines yet` +
        `${filter !== "all" ? " for " + esc(C.label(filter)) : ""}. ` +
        `Run <code>python data-pipeline/fetch_news_gdelt.py</code> to populate the feed.</div>`;
      return;
    }

    // Lead story = most recent in the current view.
    const top = items[0];
    const leadTag = (top.tags || [])[0];
    lead.innerHTML =
      `<a class="lead" href="${esc(top.url)}" target="_blank" rel="noopener"` +
      (leadTag ? ` style="--c:${C.color(leadTag)}"` : "") + `>` +
      `<div class="kicker">${leadTag ? esc(C.label(leadTag)) : "Top story"} · ${esc(ago(top.date))}</div>` +
      `<h2 class="t">${esc(top.title)}</h2>` +
      `<div class="m"><span class="src">${esc(top.source || "")}</span>` +
      `<span>${(top.tags || []).map(pill).join(" ")}</span></div></a>`;

    // Everything after the lead, revealed a batch at a time (client-side — the
    // whole feed is already loaded, so "Load more" is instant, no network).
    const rest = items.slice(1);
    list.innerHTML = rest.slice(0, shown).map(itemRow).join("");

    const remaining = rest.length - shown;
    if (remaining > 0) {
      more.innerHTML =
        `<button class="load-more" type="button">Load more ` +
        `<span>${Math.min(PAGE_SIZE, remaining)} of ${remaining}</span></button>`;
      more.querySelector(".load-more").onclick = () => { shown += PAGE_SIZE; render(); };
    } else {
      more.innerHTML = rest.length > PAGE_SIZE
        ? `<div class="feed-end">You're all caught up — ${rest.length + 1} headlines.</div>` : "";
    }
  }

  // GDELT syndicates the same story across many outlets; collapse near-identical
  // titles so the feed doesn't repeat itself. Keep the most recent copy and
  // merge its tags so filtering still works.
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

  // Live from Supabase (already relevance-filtered at ingestion). Ordered newest
  // first; dedupe() collapses syndicated near-duplicate titles.
  SB.get("news?select=title,url,source,published_date,commodities_tags" +
    "&order=published_date.desc&limit=1000").then((rows) => {
    articles = dedupe(rows.map((r) => ({
      title: r.title, url: r.url, source: r.source,
      date: r.published_date, tags: r.commodities_tags || [],
    })));
    render();
  }).catch(() => {
    document.getElementById("list").innerHTML =
      '<div class="empty">Could not load the news feed from Supabase.</div>';
  });
})();
