/* Markets desk: watchlist rail + interactive price chart from prices.json.
   Data is numeric / from our own registry; the only external strings are unit
   and source labels, rendered via textContent. Reads/writes ?commodity=. */
(function () {
  "use strict";
  const C = window.COMMODITIES;
  const RANGES = [["1M", 21], ["6M", 126], ["1Y", 260], ["All", Infinity]];
  const fmtNum = (n) => d3.format(n >= 1000 ? ",.0f" : ",.2f")(n);

  let data = { series: {}, units: {}, sources: {} };
  let commodity = C.clean(new URLSearchParams(location.search).get("commodity"));
  let range = "1Y";

  const has = (k) => (data.series[k] || []).length > 0;

  // Tiny inline sparkline (last ~80 points) in the commodity's colour — the
  // Bloomberg/Koyfin watchlist tell-at-a-glance. Values are numeric, so the
  // built SVG string is trusted.
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

  // ---- watchlist rail ----
  function renderWatchlist() {
    const box = document.getElementById("watchlist");
    box.innerHTML = "";
    C.ORDER.forEach((k) => {
      const s = data.series[k] || [];
      const on = has(k);
      const btn = document.createElement("button");
      btn.className = "wl" + (on ? "" : " off") + (k === commodity ? " on" : "");
      btn.style.setProperty("--c", C.color(k));
      let right;
      if (on) {
        const last = s[s.length - 1][1];
        const chg = pctChange(s, 12);
        const dir = chg >= 0 ? "up" : "down";
        right = `<span class="rt"><span class="px">${fmtNum(last)}</span>` +
          `<span class="ch ${dir}">${chg >= 0 ? "+" : ""}${chg.toFixed(1)}%</span></span>`;
      } else {
        right = `<span class="na">n/a</span>`;
      }
      const spark = on ? `<span class="spark">${sparkSVG(s, C.color(k))}</span>`
        : `<span class="spark"></span>`;
      btn.innerHTML = `<span class="dot"></span><span class="nm"></span>${spark}${right}`;
      btn.querySelector(".nm").textContent = C.label(k);
      if (on) btn.onclick = () => select(k);
      box.appendChild(btn);
    });
  }

  function renderRanges() {
    const box = document.getElementById("ranges");
    box.innerHTML = "";
    RANGES.forEach(([lbl]) => {
      const b = document.createElement("button");
      b.className = "range-btn" + (lbl === range ? " on" : "");
      b.style.setProperty("--c", C.color(commodity));
      b.textContent = lbl;
      b.onclick = () => { range = lbl; draw(); renderRanges(); };
      box.appendChild(b);
    });
  }

  function select(k) {
    commodity = k;
    const u = new URL(location.href);
    u.searchParams.set("commodity", k);
    history.replaceState(null, "", u);
    renderWatchlist(); renderRanges(); draw();
  }

  function windowed() {
    const full = (data.series[commodity] || []).map((d) => [new Date(d[0]), d[1]]);
    const n = RANGES.find((r) => r[0] === range)[1];
    return n === Infinity ? full : full.slice(Math.max(0, full.length - n));
  }

  function draw() {
    const color = C.color(commodity);
    const unit = data.units[commodity] || "";
    const src = data.sources && data.sources[commodity];
    const full = data.series[commodity] || [];

    document.getElementById("p-dot").style.background = color;
    document.getElementById("p-dot").style.boxShadow = "0 0 12px 0 " + color;
    document.getElementById("p-name").textContent = C.label(commodity);
    document.getElementById("p-unit").textContent = unit;
    document.querySelectorAll(".panel-title .dot, .price-now").forEach(() => {});

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
        .html(`<div class="no-series"><div class="big">No free price series</div>` +
          `<p>${C.label(commodity)} has no public daily/monthly price feed we can chart.</p></div>`);
      return;
    }

    const series = windowed();
    const last = full[full.length - 1];
    const chg = pctChange(full, 12);
    const dir = chg >= 0 ? "up" : "down";
    document.getElementById("p-price").textContent = fmtNum(last[1]);
    const chgEl = document.getElementById("p-chg");
    chgEl.className = "chg " + dir;
    chgEl.textContent = `${chg >= 0 ? "+" : ""}${chg.toFixed(1)}% · vs ~1y ago`;
    // Window stats strip (over the visible range).
    const vals = series.map((d) => d[1]);
    const hi = d3.max(vals), lo = d3.min(vals), avg = d3.mean(vals);
    const spread = lo ? (100 * (hi - lo) / lo) : 0;
    const cell = (k, v) => `<div class="s"><span class="k">${k}</span><span class="v">${v}</span></div>`;
    document.getElementById("stats").innerHTML =
      cell(range + " high", fmtNum(hi)) + cell(range + " low", fmtNum(lo)) +
      cell("Average", fmtNum(avg)) + cell("Spread", spread.toFixed(1) + "%");

    const foot = document.getElementById("foot");
    foot.innerHTML = "";
    foot.append(document.createTextNode(`${full.length} points · `));
    const b1 = document.createElement("b"); b1.textContent = src || "—"; foot.append(b1);
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

    const gid = "grad-" + commodity;
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
        tip.append(document.createTextNode(fmtNum(d[1]) + (unit ? " " : "")));
        const dd = document.createElement("span"); dd.className = "d";
        dd.textContent = d[0].toISOString().slice(0, 10); tip.append(dd);
        tip.style.left = x(d[0]) + "px";
        tip.style.top = y(d[1]) + "px";
        tip.style.opacity = 1;
      })
      .on("mouseleave", () => { hl.style("opacity", 0); hd.style("opacity", 0); tip.style.opacity = 0; });
  }

  fetch("prices.json").then((r) => r.json()).then((d) => {
    data = { series: d.series || {}, units: d.units || {}, sources: d.sources || {} };
    if (!has(commodity)) commodity = C.ORDER.find(has) || "crude";
    renderWatchlist(); renderRanges(); draw();
    window.addEventListener("resize", draw);
  }).catch(() => {
    document.getElementById("foot").textContent = "Could not load prices.json — run python app/build_news_trading.py";
  });
})();
