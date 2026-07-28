/* Landing page: fills the live ticker, the three section stats, and the
   coverage strip from prices.json + news.json. Pure progressive enhancement —
   the page reads fine if the data hasn't been built yet. */
(function () {
  "use strict";
  const C = window.COMMODITIES;
  const fmt = (n) => n >= 1000 ? d3fmt(n) : n.toFixed(2);
  function d3fmt(n) { return n.toLocaleString("en-US", { maximumFractionDigits: 0 }); }

  // ---- coverage strip (static, always renders) ----
  const cov = document.getElementById("coverage");
  if (cov) {
    cov.innerHTML = C.ORDER.map((k) =>
      `<span class="cov"><span class="dot" style="background:${C.color(k)}"></span>${C.label(k)}</span>`
    ).join("");
  }

  // ---- prices → ticker + trading stat (live from Supabase) ----
  SB.get("trading_series?select=commodity,points").then((rows) => {
    const series = {};
    rows.forEach((r) => { series[r.commodity] = r.points || []; });
    const priced = C.ORDER.filter((k) => (series[k] || []).length);

    const st = document.getElementById("stat-trading");
    if (st) st.innerHTML = `<b>${priced.length}</b> price series live <span class="go">→</span>`;

    const items = priced.map((k) => {
      const s = series[k];
      const last = s[s.length - 1][1];
      const prev = s[Math.max(0, s.length - 13)][1];
      const chg = prev ? (100 * (last - prev) / prev) : 0;
      return { k, last, chg };
    });
    const track = document.getElementById("ticker");
    if (track && items.length) {
      // Duplicate the row so the marquee can loop seamlessly (-50% keyframe).
      const one = items.map((it) => {
        const dir = it.chg >= 0 ? "up" : "down";
        const arw = it.chg >= 0 ? "▲" : "▼"; // ▲ ▼
        const sign = it.chg >= 0 ? "+" : "";
        return `<span class="tk"><span class="dot" style="background:${C.color(it.k)}"></span>` +
          `<span class="sym">${C.label(it.k).toUpperCase()}</span>` +
          `<span class="px">${fmt(it.last)}</span>` +
          `<span class="chg ${dir}">${arw} ${sign}${it.chg.toFixed(1)}%</span></span>`;
      }).join("");
      track.innerHTML = one + one;
    } else if (track) {
      track.innerHTML = `<span class="tk"><span class="px">Run app/build_news_trading.py to load prices</span></span>`;
    }
  }).catch(() => {});

  // ---- news → headline count (live from Supabase) ----
  SB.get("news?select=id").then((rows) => {
    const n = rows.length;
    const el = document.getElementById("stat-news");
    if (el) el.innerHTML = `<b>${n}</b> headline${n === 1 ? "" : "s"} indexed <span class="go">→</span>`;
  }).catch(() => {});
})();
