/* Markets desk: a [Commodities | Firms] switch drives one terminal — a
   watchlist rail + interactive price chart. Commodities come from the
   trading_series view; firms (listed operators) from firm_series, both as
   [date, price] arrays. Firm prices are USD; firms render in mono ink to match
   the companies aesthetic. Reads/writes ?view= & ?commodity= / ?firm=. */
(function () {
  "use strict";
  const C = window.COMMODITIES;
  const RANGES = [["1M", 21], ["6M", 126], ["1Y", 260], ["All", Infinity]];
  const fmtNum = (n) => d3.format(n >= 1000 ? ",.0f" : ",.2f")(n);
  const INK = "#0A0A0A";                 // firms accent (monochrome)

  let mode = "commodities";              // "commodities" | "firms"
  let comm = { series: {}, units: {}, sources: {} };
  let firms = { order: [], series: {}, names: {}, logos: {},
                tickers: {}, exchanges: {}, px: {}, chg: {}, loaded: false };

  const params = new URLSearchParams(location.search);
  if (params.get("view") === "firms") mode = "firms";
  let selComm = C.clean(params.get("commodity"));
  let selFirm = params.get("firm") || null;
  let range = "1Y";

  // ---- mode-aware accessors ----
  const isC = () => mode === "commodities";
  const keys = () => (isC() ? C.ORDER : firms.order);
  const ser = (k) => (isC() ? comm.series[k] : firms.series[k]) || [];
  const has = (k) => ser(k).length > 0;
  const cur = () => (isC() ? selComm : selFirm);
  const setCur = (k) => { if (isC()) selComm = k; else selFirm = k; };
  const lbl = (k) => (isC() ? C.label(k) : (firms.names[k] || k));
  const col = (k) => (isC() ? C.color(k) : INK);
  const unit = (k) => (isC() ? (comm.units[k] || "") : "USD");
  const src = (k) => (isC() ? comm.sources[k]
    : (firms.tickers[k] + " · " + firms.exchanges[k]));
  const logo = (k) => (isC() ? null : firms.logos[k]);
  // Headline figures. Commodities derive from their series (~1y lookback, no
  // live feed). Firms use the authoritative live quote (company_quotes) — its
  // day change dodges the gap artifacts of thin ADR daily bars.
  const price = (k) => (isC() ? (ser(k).slice(-1)[0] || [, 0])[1] : firms.px[k]);
  const chgVal = (k) => (isC() ? pctChange(ser(k), 12) : (firms.chg[k] || 0));
  const chgLabel = () => (isC() ? "vs ~1y ago" : "vs prev close");
  const money = (v) => (isC() ? "" : "$") + fmtNum(v);

  // Tiny inline sparkline (last ~80 points) in the market's colour.
  function sparkSVG(s, color) {
    const pts = s.slice(-80).map((d) => d[1]);
    if (pts.length < 2) return "";
    const w = 52, h = 22, pad = 3;
    const mn = Math.min(...pts), mx = Math.max(...pts), rng = (mx - mn) || 1;
    const step = w / (pts.length - 1);
    const path = pts.map((v, i) =>
      `${i ? "L" : "M"}${(i * step).toFixed(1)},${(pad + (h - 2 * pad) * (1 - (v - mn) / rng)).toFixed(1)}`
    ).join("");
    return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">` +
      `<path d="${path}" fill="none" stroke="${color}" stroke-width="1.3" ` +
      `stroke-linejoin="round" stroke-linecap="round" opacity="0.85"/></svg>`;
  }

  function pctChange(s, lookback) {
    if (s.length < 2) return 0;
    const last = s[s.length - 1][1];
    const prev = s[Math.max(0, s.length - 1 - lookback)][1];
    return prev ? (100 * (last - prev) / prev) : 0;
  }

  // ---- market switch ----
  function renderSwitch() {
    document.querySelectorAll("#mkt-switch button").forEach((b) =>
      b.classList.toggle("on", b.dataset.m === mode));
  }

  function switchMode(m) {
    if (m === mode) return;
    mode = m;
    renderSwitch();
    if (m === "firms" && !firms.loaded) loadFirms().then(afterSwitch);
    else afterSwitch();
  }

  function afterSwitch() {
    if (!has(cur())) setCur(keys().find(has) || keys()[0]);
    syncURL(); renderWatchlist(); renderRanges(); draw();
  }

  function loadFirms() {
    return SB.get("firm_series?select=company_id,name,logo,ticker,exchange," +
      "price_usd,change_pct,points").then((rows) => {
      (rows || []).forEach((r) => {
        firms.order.push(r.company_id);
        firms.series[r.company_id] = r.points || [];
        firms.names[r.company_id] = r.name;
        firms.logos[r.company_id] = r.logo;
        firms.tickers[r.company_id] = r.ticker;
        firms.exchanges[r.company_id] = r.exchange;
        firms.px[r.company_id] = r.price_usd;
        firms.chg[r.company_id] = r.change_pct || 0;
      });
      // Rank by day change (movers first), matching each row's shown %.
      firms.order.sort((a, b) => (firms.chg[b] || 0) - (firms.chg[a] || 0));
      firms.loaded = true;
      if (!selFirm || !has(selFirm)) selFirm = firms.order.find(has) || firms.order[0];
    }).catch(() => { firms.loaded = true; });
  }

  // ---- watchlist rail ----
  function renderWatchlist() {
    const box = document.getElementById("watchlist");
    box.innerHTML = "";
    // Priced markets first; unpriced (commodities only) sink and read "Coming soon".
    const ordered = keys().filter(has).concat(keys().filter((k) => !has(k)));
    ordered.forEach((k) => {
      const s = ser(k);
      const on = has(k);
      const btn = document.createElement("button");
      btn.className = "wl" + (on ? "" : " off") + (k === cur() ? " on" : "");
      btn.style.setProperty("--c", col(k));
      let right;
      if (on) {
        const chg = chgVal(k);
        const dir = chg >= 0 ? "up" : "down";
        right = `<span class="rt"><span class="px">${money(price(k))}</span>` +
          `<span class="ch ${dir}">${chg >= 0 ? "+" : ""}${chg.toFixed(1)}%</span></span>`;
      } else {
        right = `<span class="soon">Coming soon</span>`;
      }
      const spark = on ? `<span class="spark">${sparkSVG(s, col(k))}</span>`
        : `<span class="spark"></span>`;
      btn.innerHTML = `<span class="dot"></span><span class="nm"></span>${spark}${right}`;
      btn.querySelector(".nm").textContent = lbl(k);
      // Logo URL comes from our own registry, but set it via the DOM (src as a
      // property, not parsed from an HTML string) so a stray char can't break
      // out of the attribute.
      const lg = logo(k);
      if (lg) {
        const img = document.createElement("img");
        img.className = "wl-logo";
        img.alt = "";
        img.onerror = () => { img.style.visibility = "hidden"; };
        img.src = lg;
        btn.replaceChild(img, btn.querySelector(".dot"));
      }
      if (on) btn.onclick = () => select(k);
      box.appendChild(btn);
    });
  }

  function renderRanges() {
    const box = document.getElementById("ranges");
    box.innerHTML = "";
    RANGES.forEach(([lbl2]) => {
      const b = document.createElement("button");
      b.className = "range-btn" + (lbl2 === range ? " on" : "");
      b.style.setProperty("--c", col(cur()));
      b.textContent = lbl2;
      b.onclick = () => { range = lbl2; draw(); renderRanges(); };
      box.appendChild(b);
    });
  }

  function syncURL() {
    const u = new URL(location.href);
    u.searchParams.set("view", mode);
    if (isC()) { u.searchParams.set("commodity", selComm); u.searchParams.delete("firm"); }
    else { u.searchParams.set("firm", selFirm); u.searchParams.delete("commodity"); }
    history.replaceState(null, "", u);
  }

  function select(k) {
    setCur(k);
    syncURL();
    renderWatchlist(); renderRanges(); draw();
  }

  function windowed() {
    const full = ser(cur()).map((d) => [new Date(d[0]), d[1]]);
    const n = RANGES.find((r) => r[0] === range)[1];
    return n === Infinity ? full : full.slice(Math.max(0, full.length - n));
  }

  function draw() {
    const k = cur();
    const color = col(k);
    const u = unit(k);
    const s = src(k);
    const full = ser(k);

    document.getElementById("p-dot").style.background = color;
    document.getElementById("p-dot").style.boxShadow = "0 0 12px 0 " + color;
    document.getElementById("p-name").textContent = lbl(k);
    document.getElementById("p-unit").textContent = u;

    const svg = d3.select("#chart");
    svg.selectAll("*").remove();
    const tip = document.getElementById("tip");
    tip.style.opacity = 0;

    if (!full.length) {
      document.getElementById("p-price").textContent = "—";
      document.getElementById("p-chg").textContent = "";
      document.getElementById("foot").textContent = "";
      document.getElementById("stats").innerHTML = "";
      svg.append("foreignObject").attr("x", 0).attr("y", 0).attr("width", "100%").attr("height", 360)
        .html(`<div class="no-series"><div class="big">Coming soon</div>` +
          `<p>A live ${lbl(k)} price feed is on the way.</p></div>`);
      return;
    }

    const series = windowed();
    const last = full[full.length - 1];
    const chg = chgVal(k);
    const dir = chg >= 0 ? "up" : "down";
    document.getElementById("p-price").textContent = money(price(k));
    const chgEl = document.getElementById("p-chg");
    chgEl.className = "chg " + dir;
    chgEl.textContent = `${chg >= 0 ? "+" : ""}${chg.toFixed(1)}% · ${chgLabel()}`;
    // Window stats strip (over the visible range).
    const vals = series.map((d) => d[1]);
    const hi = d3.max(vals), lo = d3.min(vals), avg = d3.mean(vals);
    const spread = lo ? (100 * (hi - lo) / lo) : 0;
    const cell = (kk, v) => `<div class="s"><span class="k">${kk}</span><span class="v">${v}</span></div>`;
    document.getElementById("stats").innerHTML =
      cell(range + " high", money(hi)) + cell(range + " low", money(lo)) +
      cell("Average", money(avg)) + cell("Spread", spread.toFixed(1) + "%");

    const foot = document.getElementById("foot");
    foot.innerHTML = "";
    foot.append(document.createTextNode(`${full.length} points · `));
    const b1 = document.createElement("b"); b1.textContent = s || "—"; foot.append(b1);
    foot.append(document.createTextNode(` · latest ${last[0]}`));

    const box = svg.node().getBoundingClientRect();
    const w = box.width, h = box.height, m = { t: 14, r: 18, b: 26, l: 58 };
    const x = d3.scaleTime().domain(d3.extent(series, (d) => d[0])).range([m.l, w - m.r]);
    const y = d3.scaleLinear()
      .domain([d3.min(series, (d) => d[1]) * 0.98, d3.max(series, (d) => d[1]) * 1.02])
      .range([h - m.b, m.t]);

    svg.append("g").attr("transform", `translate(${m.l},0)`)
      .call(d3.axisLeft(y).ticks(6).tickSize(-(w - m.l - m.r)).tickFormat(""))
      .call((g) => g.select(".domain").remove())
      .selectAll("line").attr("class", "grid-line");
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${h - m.b})`)
      .call(d3.axisBottom(x).ticks(6).tickSizeOuter(0));
    svg.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`)
      .call(d3.axisLeft(y).ticks(6).tickSizeOuter(0).tickFormat((v) => fmtNum(v)));

    const gid = "grad-" + mode;
    const grad = svg.append("defs").append("linearGradient").attr("id", gid)
      .attr("x1", 0).attr("x2", 0).attr("y1", 0).attr("y2", 1);
    grad.append("stop").attr("offset", "0%").attr("stop-color", color).attr("stop-opacity", .3);
    grad.append("stop").attr("offset", "100%").attr("stop-color", color).attr("stop-opacity", 0);

    const area = d3.area().x((d) => x(d[0])).y0(h - m.b).y1((d) => y(d[1])).curve(d3.curveMonotoneX);
    const line = d3.line().x((d) => x(d[0])).y((d) => y(d[1])).curve(d3.curveMonotoneX);
    svg.append("path").datum(series).attr("fill", `url(#${gid})`).attr("d", area);
    svg.append("path").datum(series).attr("fill", "none")
      .attr("stroke", color).attr("stroke-width", 1.8).attr("d", line);

    // ---- hover crosshair + tooltip ----
    const hl = svg.append("line").attr("class", "hover-line").attr("y1", m.t).attr("y2", h - m.b).style("opacity", 0);
    const hd = svg.append("circle").attr("class", "hover-dot").attr("r", 4).attr("fill", color).style("opacity", 0);
    const bisect = d3.bisector((d) => d[0]).center;
    svg.append("rect").attr("x", m.l).attr("y", m.t).attr("width", w - m.l - m.r)
      .attr("height", h - m.b - m.t).attr("fill", "transparent")
      .on("mousemove", function (ev) {
        const mx = d3.pointer(ev, this)[0] + m.l;
        const d = series[bisect(series, x.invert(mx))];
        if (!d) return;
        hl.attr("x1", x(d[0])).attr("x2", x(d[0])).style("opacity", 1);
        hd.attr("cx", x(d[0])).attr("cy", y(d[1])).style("opacity", 1);
        tip.innerHTML = "";
        tip.append(document.createTextNode(money(d[1]) + (u ? " " : "")));
        const dd = document.createElement("span"); dd.className = "d";
        dd.textContent = d[0].toISOString().slice(0, 10); tip.append(dd);
        tip.style.left = x(d[0]) + "px";
        tip.style.top = y(d[1]) + "px";
        tip.style.opacity = 1;
      })
      .on("mouseleave", () => { hl.style("opacity", 0); hd.style("opacity", 0); tip.style.opacity = 0; });
  }

  // ---- boot ----
  document.querySelectorAll("#mkt-switch button").forEach((b) =>
    (b.onclick = () => switchMode(b.dataset.m)));
  renderSwitch();
  window.addEventListener("resize", draw);

  // Commodities always load (needed when the user toggles back). The
  // trading_series view already picks one source per commodity.
  const commReady = SB.get("trading_series?select=commodity,unit,source,points").then((rows) => {
    const series = {}, units = {}, sources = {};
    rows.forEach((r) => {
      series[r.commodity] = r.points || [];
      units[r.commodity] = r.unit;
      sources[r.commodity] = r.source;
    });
    comm = { series, units, sources };
    if (!has(selComm) && isC()) selComm = C.ORDER.find((k) => series[k] && series[k].length) || "crude";
  }).catch(() => {
    document.getElementById("foot").textContent = "Could not load prices from Supabase";
  });

  if (mode === "firms") {
    Promise.all([commReady, loadFirms()]).then(() => {
      renderWatchlist(); renderRanges(); draw();
    });
  } else {
    commReady.then(() => { renderWatchlist(); renderRanges(); draw(); });
  }
})();
