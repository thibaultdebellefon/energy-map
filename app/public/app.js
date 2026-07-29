/* Energy Map — interactive planisphere of crude oil & LNG trade.
   Reads data.json (built by build_data.py) + world.geojson. Pure D3 v7. */
(function () {
  "use strict";

  // Natural Earth ADM0_A3 -> our ISO3 where they differ.
  const ISO_ALIAS = { KOS: "XKX", SDS: "SSD", SAH: "ESH" };
  const ENERGY = new Set(["crude", "lng"]); // commodities the routes model covers
  const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Commodity registry helpers (state.registry populated from data.meta).
  const reg = (key) => state.registry[key] || {};
  const colorOf = (key) => reg(key).color || "#8896a6";
  const labelOf = (key) => reg(key).label || key;
  const prodKeyOf = (key) => reg(key).prod;      // production-table commodity
  const prodUnitOf = (key) => reg(key).unit || "";
  const isEnergy = () => ENERGY.has(state.commodity);

  // For the current commodity's base metal, find its ore & refined trade keys.
  // Only metals that exist in BOTH phases (copper, aluminium, cobalt, nickel,
  // zinc, tin, manganese) return a pair; energy / single-phase return null.
  function metalPair() {
    const base = reg(state.commodity).prod;
    if (!base || reg(state.commodity).phase === "energy") return null;
    let ore = null, refined = null;
    state.data.meta.commodities.forEach((c) => {
      if (c.prod !== base) return;
      if (c.phase === "ore") ore = c.key;
      if (c.phase === "refined") refined = c.key;
    });
    return (ore && refined) ? { ore, refined } : null;
  }

  const state = {
    mode: "overview",     // 'overview' (aggregates) | 'trade' (routes + sites)
    layers: { sites: true, ports: true, routes: true },  // Trade sub-layers
    selectedRoute: null,
    selectedFacility: null,
    selectedFlow: null,
    selectedPort: null,
    ports: {},
    valueChain: false,    // overlay ore + refined arcs for a paired metal
    commodity: "crude",
    metric: "net",        // 'prod' | 'exp' | 'imp' | 'net' | 'none'
    topN: 15,             // top maritime routes shown in Trade
    focusN: 20,           // routes drawn on the map for a selected country
    source: "all",
    selected: null,
    focusFlows: [], topPartners: new Set(), neighborSet: new Set(),
    data: null, features: null, centroids: {}, nameByIso: {}, registry: {},
  };

  // ---- number / currency formatting -------------------------------------
  const fUSD = (v) => {
    if (!v) return "$0";
    const a = Math.abs(v);
    if (a >= 1e12) return (v / 1e12).toFixed(2) + " T$";
    if (a >= 1e9) return "$" + (v / 1e9).toFixed(1) + "B";
    if (a >= 1e6) return "$" + (v / 1e6).toFixed(1) + "M";
    return "$" + d3.format(",.0f")(v);
  };
  const fNum = (v, unit) => (v ? d3.format(",.0f")(v) + (unit ? " " + unit : "") : "—");

  // ---- geometry ---------------------------------------------------------
  const svg = d3.select("#map");
  const gMap = svg.append("g").attr("class", "map-root");
  const gCountries = gMap.append("g");
  const gArcs = gMap.append("g");
  const gArcHit = gMap.append("g");   // wide transparent click targets for arcs
  const gNodes = gMap.append("g");
  const gLabels = gMap.append("g");
  const gRoutes = gMap.append("g");
  const gChokes = gMap.append("g");
  const gRouteLabels = gMap.append("g");
  const gConnect = gMap.append("g");
  const gPorts = gMap.append("g");
  const gFacilities = gMap.append("g");
  const projection = d3.geoNaturalEarth1();
  const path = d3.geoPath(projection);
  const tooltip = d3.select("#tooltip");
  let sphere, graticule;

  function size() {
    const el = document.querySelector(".stage");
    return [el.clientWidth, el.clientHeight];
  }

  function fit() {
    const [w, h] = size();
    svg.attr("viewBox", `0 0 ${w} ${h}`);
    projection.fitExtent([[6, 6], [w - 6, h - 6]], { type: "Sphere" });
    // zoom in about the stage centre so the map fills the space (crops the empty
    // ocean/poles rather than leaving big margins).
    const zk = 1.2, zt = projection.translate(), zs = projection.scale();
    projection.scale(zs * zk).translate([w / 2 + (zt[0] - w / 2) * zk, h / 2 + (zt[1] - h / 2) * zk]);
    if (sphere) sphere.attr("d", path({ type: "Sphere" }));
    if (graticule) graticule.attr("d", path(d3.geoGraticule10()));
    gCountries.selectAll("path.country").attr("d", path);
    // recompute centroids in screen space
    state.features.forEach((f) => {
      const iso = isoOf(f);
      if (iso) state.centroids[iso] = projection(d3.geoCentroid(f));
    });
    draw();
  }

  function isoOf(feature) {
    const p = feature.properties;
    let iso = p.ADM0_A3 || p.ISO_A3_EH || p.ISO_A3;
    if (iso === "-99") iso = p.ISO_A3_EH;
    return ISO_ALIAS[iso] || iso;
  }

  // ---- metric helpers ---------------------------------------------------
  const cats = () => [state.commodity];

  // Chain view ON (+ paired metal) draws BOTH ore and refined flows; the ore
  // key comes first so the value-chain reads producer → refiner → user.
  const chainOn = () => state.valueChain && !!metalPair();
  function arcKeys() {
    const p = metalPair();
    return chainOn() ? [p.ore, p.refined] : [state.commodity];
  }
  // Two-stop tone ramp of a hue by normalised importance t∈[0,1].
  const RAMP = {};
  function rampByValue(hex, t) {
    const key = hex;
    const r = RAMP[key] || (RAMP[key] = d3.interpolateRgb(
      d3.color(hex).darker(1.5), d3.color(hex).brighter(0.7)));
    return r(0.15 + 0.85 * t);
  }
  const ORE_HUE = "#E0913C", REFINED_HUE = "#3FB6C4"; // value-chain stage hues
  function arcHue(f) {
    if (chainOn()) return f.c === metalPair().ore ? ORE_HUE : REFINED_HUE;
    return colorOf(f.c);
  }

  function countryValue(iso) {
    const c = state.data.countries[iso];
    if (!c) return null;
    const m = state.metric;
    if (m === "none") return null;
    if (m === "prod") {
      const pk = prodKeyOf(state.commodity);
      return (pk && c.prod[pk]) || null;
    }
    if (m === "gap") {
      const p = metalPair();
      if (!p) return null;
      const refined = c.exp[p.refined] || 0, ore = c.exp[p.ore] || 0;
      return (refined || ore) ? refined - ore : null;   // + processor, − extractor
    }
    const exp = c.exp[state.commodity] || 0;
    const imp = c.imp[state.commodity] || 0;
    if (m === "exp") return exp || null;
    if (m === "imp") return imp || null;
    if (m === "net") return exp - imp; // signed
  }

  function activeCommodityColor() { return colorOf(state.commodity); }

  // Build the choropleth scale for the current metric.
  function makeScale() {
    const vals = [];
    for (const iso in state.data.countries) {
      const v = countryValue(iso);
      if (v != null && !Number.isNaN(v)) vals.push(v);
    }
    if (!vals.length) return null;
    if (state.metric === "gap") {
      if (!metalPair()) return null;
      const ext = d3.max(vals.map(Math.abs)) || 1;
      // Fixed high-contrast palette: extractor (raw ore) = warm ochre,
      // processor (refined) = cool cyan. Clearer than a single metal's hues.
      return {
        diverging: true, min: -ext, max: ext,
        scale: d3.scaleDivergingSqrt([-ext, 0, ext], d3.interpolateRgbBasis(
          ["#8A5A12", "#D9954A", "#F1F1F1", "#57B4CC", "#0E7E9C"])),
      };
    }
    const col = d3.color(activeCommodityColor());
    const dark = d3.color(col).darker(1.6).formatHex();
    const softer = d3.color(col).brighter(0.5).formatHex();
    if (state.metric === "net") {
      const ext = d3.max(vals.map(Math.abs)) || 1;
      return {
        diverging: true, min: -ext, max: ext,
        // On the light canvas, near-balanced countries sit at pale grey (blend
        // with land); importers deepen to blue, exporters to the commodity hue.
        scale: d3.scaleDivergingSqrt(
          [-ext, 0, ext],
          d3.interpolateRgbBasis(["#173FC7", "#7C97F0", "#F1F1F1", col.formatHex(), dark])
        ),
      };
    }
    const max = d3.max(vals) || 1;
    // Low = pale grey (≈ land), high = saturated → dark commodity hue.
    const interp = d3.interpolateRgbBasis(["#F1F1F1", softer, col.formatHex(), dark]);
    return { diverging: false, min: 0, max, scale: d3.scaleSequentialSqrt([0, max], interp) };
  }

  // ---- flows ------------------------------------------------------------
  // For a selected country: its strongest `focusN` routes, plus the ranked
  // set of partners (top 10 get labels + emphasis, all get a lit node).
  function computeFocus() {
    const cs = new Set(arcKeys());
    const f = state.data.flows
      .filter((x) => cs.has(x.c) && (state.source === "all" || x.s === state.source) &&
        (x.o === state.selected || x.d === state.selected))
      .sort((a, b) => b.v - a.v)
      .slice(0, state.focusN);
    state.focusFlows = f;
    const byPartner = {};
    f.forEach((x) => {
      const other = x.o === state.selected ? x.d : x.o;
      byPartner[other] = (byPartner[other] || 0) + x.v;
    });
    const ranked = Object.entries(byPartner).sort((a, b) => b[1] - a[1]).map((d) => d[0]);
    state.topPartners = new Set(ranked.slice(0, 10));
    state.neighborSet = new Set([state.selected, ...ranked]);
  }

  function visibleFlows() {
    if (state.selected) return state.focusFlows;
    const src = (x) => state.source === "all" || x.s === state.source;
    // Chain view: take the top half of each stage so both are legible.
    if (chainOn()) {
      const p = metalPair(), half = Math.ceil(state.topN / 2);
      const pick = (k) => state.data.flows.filter((x) => x.c === k && src(x)).slice(0, half);
      return [...pick(p.ore), ...pick(p.refined)];
    }
    return state.data.flows.filter((x) => x.c === state.commodity && src(x))
      .slice(0, state.topN);
  }

  const widthScale = d3.scaleSqrt().range([0.35, 3.4]); // thinner arcs

  function arcPath(o, d) {
    const a = state.centroids[o], b = state.centroids[d];
    if (!a || !b) return null;
    const interp = d3.geoInterpolate(inv(a), inv(b));
    const pts = d3.range(0, 1.0001, 1 / 24).map((t) => projection(interp(t)));
    if (pts.some((p) => !p)) return null;
    return d3.line().curve(d3.curveBasis)(pts);
  }
  // screen -> lon/lat (projection.invert) memo per centroid
  function inv(screenPt) { return projection.invert(screenPt); }

  // Real maritime route if precomputed (searoute), else a great-circle arc.
  // searoute returns CONTINUOUS (unwrapped) longitudes for trans-Pacific legs
  // (e.g. -242 instead of 118): wrap to [-180,180] then split at the
  // antimeridian so the line doesn't streak straight across the map.
  const seaLine = d3.line().curve(d3.curveLinear);
  function flowPath(f) {
    if (!f.path || f.path.length < 2) return arcPath(f.o, f.d);
    const wrapped = f.path.map((p) => [((p[0] + 540) % 360) - 180, p[1]]);
    const segs = [[]];
    let prev = wrapped[0][0];
    for (const p of wrapped) {
      if (Math.abs(p[0] - prev) > 180) segs.push([]);   // crossed ±180
      segs[segs.length - 1].push(p);
      prev = p[0];
    }
    let dstr = "";
    for (const seg of segs) {
      const pts = seg.map((p) => projection(p)).filter(Boolean);
      if (pts.length > 1) dstr += seaLine(pts);
    }
    return dstr || arcPath(f.o, f.d);
  }

  // ---- draw -------------------------------------------------------------
  // Trade = country aggregates (choropleth). Routes = bilateral flow arrows.
  // Infrastructure = physical sites. One concern per tab.
  function draw() {
    const trade = state.mode === "trade";   // routes + sites + ports, layered
    const L = state.layers;
    const on = (b) => (trade && b ? null : "none");
    gArcs.style("display", on(L.routes));
    gArcHit.style("display", on(L.routes));
    gNodes.style("display", on(L.routes));
    gLabels.style("display", on(L.routes));
    gFacilities.style("display", on(L.sites));
    gPorts.style("display", on(L.ports));
    gConnect.style("display", on(L.ports && L.sites));
    gRoutes.style("display", "none");
    gChokes.style("display", "none");
    gRouteLabels.style("display", "none");

    if (state.selected && trade) computeFocus();
    drawChoropleth();
    if (trade) {
      if (L.routes) { drawArcs(); drawLabels(); }
      if (L.sites) drawFacilities();
      if (L.ports) { drawPorts(); if (L.sites) drawConnectors(); }
    }
    updateLegend();
    updatePanel();
  }

  const routeWidth = d3.scaleSqrt().range([1, 8]);

  function drawRoutes() {
    const line = d3.line().curve(d3.curveCardinal.tension(0.6));
    const totals = state.data.routes
      .map((r) => (r.stats[state.commodity] ? r.stats[state.commodity].total : 0));
    routeWidth.domain([0, d3.max(totals) || 1]);

    const data = state.data.routes.map((r) => {
      const st = r.stats[state.commodity];
      return { r, st, active: !!st, proj: r.path.map((p) => projection(p)) };
    });

    // route lines
    const sel = gRoutes.selectAll("path.route").data(data, (d) => d.r.id);
    sel.exit().remove();
    sel.enter().append("path")
      .attr("class", "route")
      .on("click", (e, d) => { e.stopPropagation(); if (d.active) selectRoute(d.r.id); })
      .merge(sel)
      .attr("d", (d) => line(d.proj))
      .attr("class", (d) => {
        const on = d.r.id === state.selectedRoute;
        return `route ${d.r.type}` + (d.active ? "" : " inactive") +
          (on ? " rsel" + (REDUCED ? "" : " flow") : "") +
          (state.selectedRoute && !on ? " rdim" : "");
      })
      .style("stroke", (d) => (d.active && d.r.type !== "pipeline"
        ? colorOf(state.commodity) : null))
      .attr("data-w", (d) => (d.active ? routeWidth(d.st.total) : 1))
      .attr("stroke-width", (d) => (d.active ? routeWidth(d.st.total) : 1) / Math.sqrt(curK));

    // chokepoint markers
    const ch = gChokes.selectAll("circle.choke").data(data, (d) => d.r.id);
    ch.exit().remove();
    ch.enter().append("circle").attr("class", "choke").attr("r", 3.5)
      .on("click", (e, d) => { e.stopPropagation(); if (d.active) selectRoute(d.r.id); })
      .merge(ch)
      .attr("class", (d) => "choke" + (d.active ? "" : " inactive") +
        (d.r.id === state.selectedRoute ? " rsel" : ""))
      .attr("cx", (d) => projection(d.r.choke)[0])
      .attr("cy", (d) => projection(d.r.choke)[1])
      .attr("r", (d) => (d.r.id === state.selectedRoute ? 5 : 3.3) / Math.sqrt(curK));

    // labels
    const lab = gRouteLabels.selectAll("text.rlbl").data(data, (d) => d.r.id);
    lab.exit().remove();
    lab.enter().append("text").attr("class", "rlbl")
      .merge(lab)
      .attr("class", (d) => "rlbl" + (d.r.id === state.selectedRoute ? " rsel" : ""))
      .style("display", (d) => (d.active || d.r.id === state.selectedRoute ? null : "none"))
      .style("font-size", (d) => (d.r.id === state.selectedRoute ? 11 : 9) / Math.sqrt(curK) + "px")
      .attr("x", (d) => projection(d.r.choke)[0])
      .attr("y", (d) => projection(d.r.choke)[1] - 7 / Math.sqrt(curK))
      .text((d) => d.r.name.replace(/ (Pipeline|Canal|Strait|Straits| & SUMED)/g, ""));
  }

  function isNeighbor(iso) { return state.neighborSet ? state.neighborSet.has(iso) : false; }

  function drawChoropleth() {
    const paths = gCountries.selectAll("path.country");
    // Trade with a focused country: light up the country + its partners.
    if (state.mode === "trade" && state.selected) {
      const self = d3.color(activeCommodityColor());
      const partner = d3.color(activeCommodityColor()); partner.opacity = 0.5;
      paths.style("fill", (f) => {
        const iso = isoOf(f);
        if (iso === state.selected) return self.formatHex();
        if (state.topPartners.has(iso)) return partner.formatRgb();
        return null;
      })
        .classed("dim", (f) => isoOf(f) !== state.selected && !isNeighbor(isoOf(f)))
        .classed("focus", (f) => isoOf(f) === state.selected);
      return;
    }
    // Trade (no selection): neutral land so routes + markers pop.
    if (state.mode !== "overview") {
      paths.style("fill", null).classed("dim", false).classed("focus", false);
      return;
    }
    // Overview: the metric choropleth.
    const sc = state.metric === "none" ? null : makeScale();
    paths.style("fill", (f) => {
      if (!sc) return null;
      const v = countryValue(isoOf(f));
      if (v == null || Number.isNaN(v) || v === 0) return null;
      return sc.scale(v);
    })
      .classed("dim", false)
      .classed("focus", (f) => state.selected && isoOf(f) === state.selected);
  }

  function drawArcs() {
    const flows = visibleFlows();
    const maxV = flows.length ? d3.max(flows, (f) => f.v) : 1;
    widthScale.domain([0, maxV]);
    const tOf = (v) => Math.sqrt(v / maxV);             // normalised importance

    // Draw smallest first so the biggest, brightest flows sit on top.
    // Keep the SVG path in _d so it doesn't clobber f.d (the destination ISO).
    const data = flows.map((f) => ({ ...f, _d: flowPath(f) }))
      .filter((f) => f._d).sort((a, b) => a.v - b.v);

    const arcs = gArcs.selectAll("path.arc")
      .data(data, (f) => f.o + "|" + f.d + "|" + f.c);
    arcs.exit().remove();
    arcs.enter().append("path")
      .attr("class", "arc flow")
      .merge(arcs)
      .order()
      .attr("d", (f) => f._d)
      .attr("class", (f) => "arc" + (REDUCED ? "" : " flow") +
        (state.selectedFlow && f.o === state.selectedFlow.o && f.d === state.selectedFlow.d ? " fsel" : ""))
      // hue = commodity (or value-chain stage); tone + opacity = importance.
      .style("stroke", (f) => rampByValue(arcHue(f), tOf(f.v)))
      .attr("data-w", (f) => widthScale(f.v))
      .attr("stroke-width", (f) => widthScale(f.v) / Math.sqrt(curK))
      .attr("stroke-opacity", (f) => {
        if (state.selectedFlow) return (f.o === state.selectedFlow.o && f.d === state.selectedFlow.d) ? 0.95 : 0.12;
        return (state.selected ? 0.4 : 0.18) + 0.62 * tOf(f.v);
      })
      .style("animation-duration", (f) => (2.6 - 1.4 * tOf(f.v)).toFixed(2) + "s");

    // Partner nodes: bigger for the top-10 inner circle, biggest for the country.
    const nodes = state.selected
      ? Array.from(state.neighborSet).filter((i) => state.centroids[i]) : [];
    const baseR = (i) => (i === state.selected ? 5 : state.topPartners.has(i) ? 3.4 : 1.8);
    const sel = gNodes.selectAll("circle.node").data(nodes, (d) => d);
    sel.exit().remove();
    sel.enter().append("circle").attr("class", "node")
      .merge(sel)
      .classed("partner", (i) => state.topPartners.has(i))
      .classed("self", (i) => i === state.selected)
      .attr("data-r", baseR)
      .attr("cx", (i) => state.centroids[i][0])
      .attr("cy", (i) => state.centroids[i][1])
      .attr("r", (i) => baseR(i) / Math.sqrt(curK));

    // Wide transparent click targets so thin routes are easy to click.
    const hit = gArcHit.selectAll("path.arc-hit").data(data, (f) => f.o + "|" + f.d + "|" + f.c);
    hit.exit().remove();
    hit.enter().append("path").attr("class", "arc-hit")
      .on("click", (e, f) => { e.stopPropagation(); selectFlow(f); })
      .on("mousemove", showFlowTip).on("mouseleave", hideTip)
      .merge(hit)
      .attr("d", (f) => f._d)
      .attr("stroke-width", 11 / Math.sqrt(curK));
  }

  function showFlowTip(event, f) {
    const [x, y] = d3.pointer(event, document.querySelector(".stage"));
    tooltip.html(`<div class="tt-nm">${nm(f.o)} → ${nm(f.d)}</div>` +
      `<div class="tt-r"><span>${labelOf(f.c)}</span><b>${fUSD(f.v)}</b></div>`)
      .style("left", Math.min(x + 14, size()[0] - 230) + "px")
      .style("top", (y + 14) + "px").attr("hidden", null);
  }

  function drawLabels() {
    // Name the country and its top-10 partners so the inner circle is legible.
    const labels = state.selected
      ? [state.selected, ...state.topPartners].filter((i) => state.centroids[i]) : [];
    const sel = gLabels.selectAll("text.lbl").data(labels, (d) => d);
    sel.exit().remove();
    sel.enter().append("text").attr("class", "lbl")
      .merge(sel)
      .classed("self", (i) => i === state.selected)
      .attr("x", (i) => state.centroids[i][0])
      .attr("y", (i) => state.centroids[i][1] - baseNodeR(i) - 4)
      .style("font-size", (i) => (i === state.selected ? 12 : 9.5) / Math.sqrt(curK) + "px")
      .text((i) => nm(i));
  }
  function baseNodeR(i) { return i === state.selected ? 5 : 3.4; }

  // ---- facilities (Infrastructure view) ---------------------------------
  const FAC_SYMBOL = {
    well: d3.symbolCircle, lng_terminal: d3.symbolSquare,
    mine: d3.symbolTriangle, refinery: d3.symbolDiamond, smelter: d3.symbolDiamond,
  };
  const FAC_LABEL = { well: "Oil field / well", lng_terminal: "LNG export terminal",
    mine: "Mine", refinery: "Refinery", smelter: "Smelter", pipeline: "Pipeline",
    port: "Port" };
  // Which global total a site's output is a share of, by role.
  const SHARE_LABEL = { mine: "world extraction", well: "world oil output",
    lng_terminal: "world LNG capacity", refinery: "world refining",
    smelter: "world smelting" };
  const facSize = d3.scaleSqrt().range([40, 260]);

  function facilitiesFor(comm) {
    return state.data.facilities.filter((f) => f.c === comm);
  }

  function drawFacilities() {
    const list = facilitiesFor(state.commodity)
      .map((f) => ({ ...f, p: state.centroids && projection([f.lon, f.lat]) }))
      .filter((f) => f.p);
    facSize.domain([0, d3.max(list, (f) => f.cap || 0) || 1]);
    const symPath = (f) => d3.symbol()
      .type(FAC_SYMBOL[f.type] || d3.symbolCircle)
      .size(f.cap ? facSize(f.cap) : 60)();
    const cc = colorOf(state.commodity);

    const sel = gFacilities.selectAll("path.fac").data(list, (d) => d.name);
    sel.exit().remove();
    sel.enter().append("path").attr("class", "fac")
      .on("click", (e, d) => { e.stopPropagation(); selectFacility(d); })
      .on("mousemove", showFacTip).on("mouseleave", hideTip)
      .merge(sel)
      .attr("d", symPath)
      .attr("transform", (d) => `translate(${d.p[0]},${d.p[1]}) scale(${1 / Math.sqrt(curK)})`)
      .attr("fill", cc)
      .classed("sel", (d) => state.selectedFacility && d.name === state.selectedFacility.name);
  }

  function selectFacility(d) {
    state.selectedFacility = (state.selectedFacility && state.selectedFacility.name === d.name) ? null : d;
    draw();
  }

  function showFacTip(event, d) {
    const [x, y] = d3.pointer(event, document.querySelector(".stage"));
    const cap = d.cap ? `${d.cap} ${d.unit || ""}` : (d.status || "");
    tooltip.html(`<div class="tt-nm">${d.name}</div>` +
      `<div class="tt-r"><span>${FAC_LABEL[d.type] || d.type}</span><b>${nm(d.iso)}</b></div>` +
      (d.op ? `<div class="tt-r"><span>operator</span><b>${d.op.slice(0, 22)}</b></div>` : "") +
      (cap ? `<div class="tt-r"><span>${d.cap ? "capacity" : "status"}</span><b>${cap}</b></div>` : ""))
      .style("left", Math.min(x + 14, size()[0] - 240) + "px")
      .style("top", (y + 14) + "px").attr("hidden", null);
  }

  // ---- ports + site→port connectors -------------------------------------
  // Ports for countries touched by the visible routes or holding a site.
  function relevantPortIsos() {
    const s = new Set();
    visibleFlows().forEach((f) => { s.add(f.o); s.add(f.d); });
    facilitiesFor(state.commodity).forEach((f) => s.add(f.iso));
    return [...s].filter((iso) => state.ports[iso]);
  }

  function drawPorts() {
    const data = relevantPortIsos()
      .map((iso) => ({ iso, p: projection(state.ports[iso]) })).filter((d) => d.p);
    const sym = d3.symbol().type(d3.symbolDiamond).size(26)();
    const sel = gPorts.selectAll("path.port").data(data, (d) => d.iso);
    sel.exit().remove();
    sel.enter().append("path").attr("class", "port").attr("d", sym)
      .on("click", (e, d) => { e.stopPropagation(); selectPort(d.iso); })
      .on("mousemove", (e, d) => showPortTip(e, d)).on("mouseleave", hideTip)
      .merge(sel)
      .classed("sel", (d) => d.iso === state.selectedPort)
      .attr("transform", (d) => `translate(${d.p[0]},${d.p[1]}) scale(${1 / Math.sqrt(curK)})`);
  }

  function selectPort(iso) {
    state.selectedPort = state.selectedPort === iso ? null : iso;
    state.selected = null; state.selectedFacility = null; state.selectedFlow = null;
    draw();
  }

  // Thin lines linking each production site to its country's export port,
  // so the chain reads site → port → sea route → destination.
  function drawConnectors() {
    const line = d3.line();
    const data = facilitiesFor(state.commodity)
      .filter((f) => state.ports[f.iso])
      .map((f) => {
        const a = projection([f.lon, f.lat]), b = projection(state.ports[f.iso]);
        return (a && b) ? { key: f.name, d: line([a, b]) } : null;
      }).filter(Boolean);
    const sel = gConnect.selectAll("path.connect").data(data, (d) => d.key);
    sel.exit().remove();
    sel.enter().append("path").attr("class", "connect")
      .merge(sel).attr("d", (d) => d.d).style("stroke", colorOf(state.commodity));
  }

  function showPortTip(event, d) {
    const [x, y] = d3.pointer(event, document.querySelector(".stage"));
    tooltip.html(`<div class="tt-nm">${nm(d.iso)}</div>` +
      `<div class="tt-r"><span>export / import port</span></div>`)
      .style("left", Math.min(x + 14, size()[0] - 220) + "px")
      .style("top", (y + 14) + "px").attr("hidden", null);
  }

  function selectFlow(f) {
    state.selectedFlow = (state.selectedFlow &&
      state.selectedFlow.o === f.o && state.selectedFlow.d === f.d) ? null : f;
    state.selected = null; state.selectedFacility = null;
    draw();
  }

  // ---- legend -----------------------------------------------------------
  const METRIC_LABEL = { prod: "Production", exp: "Exports ($)", imp: "Imports ($)",
    net: "Net trade ($)", gap: "Ore → refined gap", none: "" };
  function updateLegend() {
    const label = document.getElementById("scale-label");
    const grad = document.getElementById("scale-grad");
    const row = grad.parentElement;
    const flowKey = document.querySelector(".legend .flow-key");
    const cc = activeCommodityColor();
    const dot = (c, txt, ml) =>
      `<span class="dot" style="background:${c};box-shadow:0 0 7px ${c}${ml ? ";margin-left:10px" : ""}"></span> ${txt}`;
    if (state.mode === "trade") {
      row.style.display = "none";
      flowKey.innerHTML = '<i class="arc"></i>sea route + production sites (▲ mine · ● field · ■ LNG)';
      document.getElementById("legend-comm").innerHTML = chainOn()
        ? dot(ORE_HUE, "ore → refiner") + dot(REFINED_HUE, "refiner → user", true)
        : dot(cc, labelOf(state.commodity));
      return;
    }
    flowKey.innerHTML = "stronger colour = larger net position";
    document.getElementById("legend-comm").innerHTML = dot(cc, labelOf(state.commodity));
    if (state.metric === "none" || state.selected) { row.style.display = "none"; }
    else {
      row.style.display = "";
      const sc = makeScale();
      const unit = state.metric === "prod" ? " · " + prodUnitOf(state.commodity) : "";
      label.textContent = METRIC_LABEL[state.metric] + unit;
      if (sc) {
        const stops = d3.range(0, 1.001, 0.1).map((t) => {
          const v = sc.diverging ? sc.min + t * (sc.max - sc.min) : t * sc.max;
          return sc.scale(v);
        });
        grad.style.background = `linear-gradient(90deg, ${stops.join(",")})`;
        const gap = state.metric === "gap";
        document.getElementById("scale-min").textContent =
          gap ? "◀ extractor (ore)" : sc.diverging ? "◀ import " + fUSD(sc.min) : "0";
        document.getElementById("scale-max").textContent =
          gap ? "processor (refined) ▶"
            : sc.diverging ? "export " + fUSD(sc.max) + " ▶"
            : state.metric === "prod" ? fNum(sc.max) : fUSD(sc.max);
      } else if (state.metric === "gap") {
        grad.style.background = "none";
        document.getElementById("scale-min").textContent = "";
        document.getElementById("scale-max").textContent =
          "pick a metal with ore + refined (copper, aluminium, cobalt, nickel, zinc, tin, manganese)";
      }
    }
  }

  // ---- side panel -------------------------------------------------------
  function nm(iso) { return state.nameByIso[iso] || iso; }

  function updatePanel() {
    const cflows = state.data.flows.filter((f) => f.c === state.commodity);
    document.getElementById("s-total").textContent = fUSD(d3.sum(cflows, (f) => f.v));
    document.getElementById("s-exp").textContent = new Set(cflows.map((f) => f.o)).size;
    document.getElementById("s-routes").textContent = d3.format(",")(cflows.length);

    const panels = {
      global: document.getElementById("panel-global"),
      country: document.getElementById("panel-country"),
      routes: document.getElementById("panel-routes"),
      infra: document.getElementById("panel-infra"),
      facility: document.getElementById("panel-facility"),
      flow: document.getElementById("panel-flow"),
      port: document.getElementById("panel-port"),
    };
    let show;
    if (state.mode === "overview") show = state.selected ? "country" : "global";
    else show = state.selectedPort ? "port" : state.selectedFlow ? "flow"
      : state.selectedFacility ? "facility"
      : state.selected ? "country" : "routes";        // trade
    for (const k in panels) if (panels[k]) panels[k].hidden = k !== show;

    if (show === "global") renderLeaderboard();
    else if (show === "country") renderCountry();
    else if (show === "routes") renderExchanges();
    else if (show === "flow") renderFlowCard();
    else if (show === "port") renderPortCard();
    else renderFacilityCard();
  }

  // Clicked port: its city (geocoded), and the country's share of the
  // commodity's world exports / imports handled through this gateway.
  function renderPortCard() {
    const iso = state.selectedPort, c = state.data.countries[iso] || { exp: {}, imp: {} };
    const worldExp = d3.sum(state.data.flows.filter((f) => f.c === state.commodity), (f) => f.v) || 1;
    const expShare = 100 * (c.exp[state.commodity] || 0) / worldExp;
    const impShare = 100 * (c.imp[state.commodity] || 0) / worldExp;
    const city = (state.data.meta.port_city || {})[iso];
    document.getElementById("pt-name").textContent = (city ? city + " · " : "") + nm(iso);
    document.getElementById("pt-sub").textContent = labelOf(state.commodity) + " gateway";
    const pct = (x) => (x < 0.1 && x > 0 ? "<0.1" : x.toFixed(1)) + "%";
    const meta = [
      ["City", city || "coastal export/import point"],
      ["Exports via", pct(expShare) + " of world " + labelOf(state.commodity) + " exports"],
      ["Imports via", pct(impShare) + " of world " + labelOf(state.commodity) + " imports"],
      ["Export value", fUSD(c.exp[state.commodity] || 0)],
      ["Import value", fUSD(c.imp[state.commodity] || 0)],
    ];
    document.getElementById("pt-meta").innerHTML = meta.map(
      ([k, v]) => `<div class="m"><div class="mk">${k}</div><div class="mv">${v}</div></div>`
    ).join("");
  }

  // Clicked sea route: exact origin/destination, volume, year, market share.
  function renderFlowCard() {
    const f = state.selectedFlow;
    if (!f) return updatePanel();
    const commTotal = d3.sum(state.data.flows.filter((x) => x.c === f.c), (x) => x.v);
    const share = commTotal ? 100 * f.v / commTotal : 0;
    document.getElementById("fl-name").textContent = nm(f.o) + " → " + nm(f.d);
    document.getElementById("fl-sub").textContent = labelOf(f.c) + " · maritime route";
    const meta = [
      ["Value", fUSD(f.v) + (f.y ? " (" + f.y + ")" : "")],
      ["Volume", f.q ? d3.format(",.0f")(f.q / 1e9) + " Mt" : "—"],
      ["Market share", (share < 0.1 ? "<0.1" : share.toFixed(1)) + "% of world " + labelOf(f.c) + " trade"],
      ["From", nm(f.o) + " — export port"],
      ["To", nm(f.d) + " — import port"],
    ];
    document.getElementById("fl-meta").innerHTML = meta.map(
      ([k, v]) => `<div class="m"><div class="mk">${k}</div><div class="mv">${v}</div></div>`
    ).join("");
  }

  // Routes (no selection): the top bilateral exchanges, e.g. "COD → CHN $2.1B".
  function renderExchanges() {
    const rows = state.data.flows
      .filter((f) => f.c === state.commodity && (state.source === "all" || f.s === state.source))
      .slice(0, 15);
    const max = rows.length ? rows[0].v : 1;
    const ol = d3.select("#exchanges");
    ol.selectAll("*").remove();
    rows.forEach((f, i) => {
      const li = ol.append("li").attr("class", "row").on("click", () => select(f.o));
      li.append("div").attr("class", "fill").style("background", colorOf(state.commodity))
        .style("transform", `scaleX(${(f.v / max).toFixed(3)})`);
      li.append("div").attr("class", "rank").text(String(i + 1).padStart(2, "0"));
      li.append("div").attr("class", "nm").html(
        `${nm(f.o)} <span style="color:var(--faint)">→</span> ${nm(f.d)}`);
      li.append("div").attr("class", "val").text(fUSD(f.v));
    });
  }

  function renderInfraList() {
    document.getElementById("infra-note").textContent =
      state.commodity === "crude" ? "Major operating oil fields (GEM)."
      : state.commodity === "lng" ? "Largest LNG export terminals by capacity (GEM)."
      : "Top producing mines by output (share of world extraction).";
    const worldProd = state.data.meta.prod_world[reg(state.commodity).prod];
    const list = facilitiesFor(state.commodity)
      .slice().sort((a, b) => (b.prod || b.cap || 0) - (a.prod || a.cap || 0));
    const ol = d3.select("#infra-list");
    ol.selectAll("*").remove();
    list.forEach((f, i) => {
      const li = ol.append("li").attr("class", "row")
        .classed("sel", state.selectedFacility && f.name === state.selectedFacility.name)
        .on("click", () => selectFacility(f));
      li.append("div").attr("class", "rank").text(String(i + 1).padStart(2, "0"));
      li.append("div").attr("class", "nm").text(f.name);
      const share = (f.prod && worldProd) ? 100 * f.prod / worldProd : null;
      li.append("div").attr("class", "val").text(
        share != null ? (share < 0.1 ? "<0.1%" : share.toFixed(1) + "%")
          : f.cap ? `${f.cap} ${f.unit || ""}` : nm(f.iso));
    });
    if (!list.length) ol.append("li").attr("class", "hint").style("padding", "8px")
      .text("No sites for this commodity yet.");
  }

  function renderFacilityCard() {
    const f = state.selectedFacility;
    if (!f) return updatePanel();
    // Presentation photo (Wikimedia Commons), if any.
    const fig = document.getElementById("f-photo");
    if (f.photo) {
      const src = f.photo.replace(/^http:/, "https:") +
        (f.photo.includes("?") ? "" : "?width=460");
      fig.querySelector("img").src = src;
      fig.querySelector("figcaption").textContent = f.psrc || "";
      fig.hidden = false;
    } else { fig.hidden = true; }

    document.getElementById("f-name").textContent = f.name;
    document.getElementById("f-type").textContent =
      (FAC_LABEL[f.type] || f.type).toUpperCase() + " · " + nm(f.iso);
    const vol = f.prod ? `${d3.format(",")(f.prod)} ${f.unit || "t"}${f.year ? " (" + f.year + ")" : ""}`
      : f.cap ? `${f.cap} ${f.unit || ""}` : "—";
    // Share of the relevant global total (extraction for a mine, refining for
    // a refinery — never mixed). Denominator is USGS/EIA world production.
    const worldProd = state.data.meta.prod_world[reg(state.commodity).prod];
    const share = (f.prod && worldProd) ? 100 * f.prod / worldProd : null;
    const shareTxt = share != null
      ? `${share < 0.1 ? "<0.1" : share.toFixed(1)}% of ${SHARE_LABEL[f.type] || "world output"}`
      : "—";
    const meta = [
      ["Role", FAC_LABEL[f.type] || f.type],
      ["Operator", f.op || "—"],
      [f.cap ? "Capacity" : "Volume", vol],
      ["Share", shareTxt],
      ["Status", f.status || "—"],
      ["Since", f.start || "—"],
      ["Source", f.src + (f.url ? ` · <a href="${f.url}" target="_blank" rel="noopener">page ↗</a>` : "")],
    ];
    document.getElementById("f-meta").innerHTML = meta.map(
      ([k, v]) => `<div class="m"><div class="mk">${k}</div><div class="mv">${v}</div></div>`
    ).join("");
  }

  // The left ranking follows the "Shade by" metric: producers / exporters /
  // importers, so the panel always matches what the map is coloured by.
  function renderLeaderboard() {
    const m = state.metric;
    let title, valueFn, rows;
    if (m === "prod") {
      const pk = prodKeyOf(state.commodity);
      title = "Top producers";
      valueFn = (v) => fNum(v, prodUnitOf(state.commodity));
      rows = Object.entries(state.data.countries)
        .map(([iso, c]) => ({ iso, v: (pk && c.prod[pk]) || 0 }));
    } else {
      const key = m === "imp" ? "imp" : "exp";
      title = m === "imp" ? "Top importers" : "Top exporters";
      valueFn = fUSD;
      rows = Object.entries(state.data.countries)
        .map(([iso, c]) => ({ iso, v: c[key][state.commodity] || 0 }));
    }
    rows = rows.filter((r) => r.v > 0).sort((a, b) => b.v - a.v).slice(0, 15);
    document.getElementById("lead-title").textContent = title;
    const max = rows.length ? rows[0].v : 1;
    const ol = d3.select("#leaderboard");
    const li = ol.selectAll("li.row").data(rows, (r) => r.iso);
    li.exit().remove();
    const en = li.enter().append("li").attr("class", "row").on("click", (_, r) => select(r.iso));
    en.append("div").attr("class", "fill");
    en.append("div").attr("class", "rank");
    en.append("div").attr("class", "nm");
    en.append("div").attr("class", "val");
    const all = en.merge(li).order();
    all.classed("sel", false);
    all.select(".fill").style("background", activeCommodityColor())
      .style("transform", (r) => `scaleX(${(r.v / max).toFixed(3)})`);
    all.select(".rank").text((_, i) => String(i + 1).padStart(2, "0"));
    all.select(".nm").text((r) => nm(r.iso));
    all.select(".val").text((r) => valueFn(r.v));
  }

  function renderCountry() {
    const iso = state.selected, c = state.data.countries[iso] || { exp: {}, imp: {}, prod: {} };
    document.getElementById("c-name").textContent = nm(iso);
    document.getElementById("c-iso").textContent = iso + " · " + labelOf(state.commodity);
    const exp = c.exp[state.commodity] || 0;
    const imp = c.imp[state.commodity] || 0;
    const net = exp - imp;
    const pk = prodKeyOf(state.commodity);
    const prod = pk ? c.prod[pk] : null;
    const cells = [
      ["Exports", fUSD(exp), ""],
      ["Imports", fUSD(imp), ""],
      ["Net trade", (net >= 0 ? "+" : "−") + fUSD(Math.abs(net)), net >= 0 ? "pos" : "neg"],
      [reg(state.commodity).phase === "energy" ? "Production" : "Mine production",
       fNum(prod, prodUnitOf(state.commodity)), ""],
    ];
    // Ore vs refined split — the extractor/processor gap for paired metals.
    const pair = metalPair();
    if (pair) {
      const oreExp = c.exp[pair.ore] || 0, refExp = c.exp[pair.refined] || 0;
      cells.push(["Ore exports", fUSD(oreExp), "ore"]);
      cells.push(["Refined exports", fUSD(refExp), "ref"]);
    }
    document.getElementById("c-metrics").innerHTML = cells.map(
      ([k, v, cls]) => `<div class="c-cell"><div class="k">${k}</div><div class="v ${cls}">${v}</div></div>`
    ).join("");

    // Full partner list (all of them — the map only draws the strongest 20,
    // the panel is where every partner is browsable).
    const cs = new Set(cats());
    const dest = state.data.flows
      .filter((f) => f.o === iso && cs.has(f.c) && (state.source === "all" || f.s === state.source))
      .sort((a, b) => b.v - a.v);
    const src = state.data.flows
      .filter((f) => f.d === iso && cs.has(f.c) && (state.source === "all" || f.s === state.source))
      .sort((a, b) => b.v - a.v);
    const showImports = dest.length === 0 && src.length > 0;
    const list = showImports ? src : dest;
    document.getElementById("c-flows-title").textContent =
      (showImports ? "All suppliers (imports)" : "All destinations (exports)") +
      ` · ${list.length}`;
    const max = list.length ? list[0].v : 1;
    const ol = d3.select("#c-flows");
    ol.selectAll("*").remove();
    list.forEach((f, i) => {
      const other = showImports ? f.o : f.d;
      const li = ol.append("li").attr("class", "row").on("click", () => select(other));
      li.append("div").attr("class", "fill")
        .style("background", colorOf(f.c)).style("transform", `scaleX(${(f.v / max).toFixed(3)})`);
      li.append("div").attr("class", "rank").text(String(i + 1).padStart(2, "0"));
      li.append("div").attr("class", "nm").text(nm(other));
      li.append("div").attr("class", "val").text(fUSD(f.v));
    });
    if (!list.length) ol.append("li").attr("class", "hint").style("padding", "8px")
      .text("No routes for this commodity / source.");
  }

  // ---- routes panel -----------------------------------------------------
  const fVol = (kg) => (kg ? d3.format(",.0f")(kg / 1e9) + " Mt" : null); // kg -> Mt

  function renderRouteList() {
    document.getElementById("routes-note").textContent =
      "Model estimate (which flows likely transit each route), not ship tracking. " +
      "Showing " + labelOf(state.commodity) + ". Oil pipelines carry crude only.";
    const rows = state.data.routes.map((r) => {
      const st = r.stats[state.commodity];
      return { r, v: st ? st.total : -1 };
    }).sort((a, b) => b.v - a.v);
    const max = d3.max(rows, (d) => d.v) || 1;
    const ol = d3.select("#route-list");
    ol.selectAll("*").remove();
    rows.forEach((d) => {
      const li = ol.append("li").attr("class", "row")
        .classed("sel", d.r.id === state.selectedRoute);
      if (d.v >= 0) li.on("click", () => selectRoute(d.r.id));
      else li.style("opacity", 0.45);
      li.append("div").attr("class", "fill")
        .style("background", d.r.type === "pipeline" ? "#E27B4E" : colorOf(state.commodity))
        .style("transform", `scaleX(${d.v > 0 ? (d.v / max).toFixed(3) : 0})`);
      li.append("div").attr("class", "rank").html(`<span class="type-icon ${d.r.type}"></span>`);
      li.append("div").attr("class", "nm").text(d.r.name);
      li.append("div").attr("class", "val")
        .text(d.v >= 0 ? fUSD(d.v) : "n/a");
    });
  }

  function renderRouteCard() {
    const r = state.data.routes.find((x) => x.id === state.selectedRoute);
    if (!r) { state.selectedRoute = null; return updatePanel(); }

    const st = r.stats[state.commodity];      // per-commodity route stats
    const commLabel = st ? labelOf(state.commodity)
      : (r.type === "pipeline" ? "crude only — n/a for " + labelOf(state.commodity)
         : "no significant " + labelOf(state.commodity) + " flow here");

    document.getElementById("r-name").textContent = r.name;
    document.getElementById("r-type").textContent = r.type.toUpperCase() + " · " + commLabel;

    const meta = [
      ["From", r.from], ["To", r.to],
      ["Transit", r.transit_time],
      ["Chokepoints", r.chokepoints.join(" · ")],
      ["Countries", `<div class="chips">${r.transit_countries.map((i) =>
        `<span class="chip">${nm(i)}</span>`).join("")}</div>`],
      ["Volume", st ? fUSD(st.total) + (st.quantity ? " · " + fVol(st.quantity) : "") +
        ` · ${st.n_flows} flows` : "—"],
    ];
    document.getElementById("r-meta").innerHTML = meta.map(
      ([k, v]) => `<div class="m"><div class="mk">${k}</div><div class="mv">${v}</div></div>`
    ).join("");

    document.getElementById("r-users-title").textContent =
      "Top users · " + commLabel;
    const ol = d3.select("#r-users");
    ol.selectAll("*").remove();
    const users = (st && st.users) || [];
    const max = users.length ? users[0].value : 1;
    users.forEach((u, i) => {
      const li = ol.append("li").attr("class", "row")
        .on("click", () => { setMode("trade"); select(u.iso); });
      li.append("div").attr("class", "fill").style("background", colorOf(state.commodity))
        .style("transform", `scaleX(${(u.value / max).toFixed(3)})`);
      li.append("div").attr("class", "rank").text(String(i + 1).padStart(2, "0"));
      li.append("div").attr("class", "nm").text(nm(u.iso));
      const val = li.append("div").attr("class", "val");
      val.append("span").text(fUSD(u.value));
      if (u.share != null) val.append("span").attr("class", "share")
        .text(" " + Math.round(u.share * 100) + "%");
    });
    if (!users.length) ol.append("li").attr("class", "hint").style("padding", "8px")
      .text("No matching flows for this commodity.");
    document.getElementById("r-note").textContent =
      "Model estimate. " + r.note + " Share = this country's value on the route " +
      "÷ its total oil/LNG trade.";
  }

  function selectRoute(id) {
    state.selectedRoute = state.selectedRoute === id ? null : id;
    draw();
  }

  function updateChainButton() {
    const btn = document.getElementById("chain");
    const ok = !!metalPair();
    btn.disabled = !ok;
    btn.classList.toggle("off", !ok);
    if (!ok) state.valueChain = false;
    btn.classList.toggle("chain-on", state.valueChain);
  }

  function populateCommodities() {
    const sel = document.getElementById("commodity");
    const groups = {};
    // Ore commodities stay in the data (they power the value-chain overlay) but
    // are hidden from the selector — the app focuses on refined + energy.
    state.data.meta.commodities
      .filter((c) => c.group !== "Metal · ore")
      .forEach((c) => { (groups[c.group] ||= []).push(c); });
    sel.innerHTML = "";
    for (const g in groups) {
      const og = document.createElement("optgroup");
      og.label = g;
      groups[g].forEach((c) => {
        const o = document.createElement("option");
        o.value = c.key; o.textContent = c.label;
        og.appendChild(o);
      });
      sel.appendChild(og);
    }
    sel.value = state.commodity;
  }

  // ---- selection & interaction -----------------------------------------
  function setMode(mode) {
    if (state.mode === mode) return;
    state.mode = mode;
    state.selected = null; state.selectedRoute = null;
    state.selectedFacility = null; state.selectedFlow = null; state.selectedPort = null;
    d3.selectAll("#view button").classed("on", function () { return this.dataset.v === mode; });
    document.getElementById("layers").hidden = mode !== "trade";  // layer toggles: Trade only
    draw();
  }

  function select(iso) {
    state.selected = state.selected === iso ? null : iso;
    draw();
  }

  function showTip(event, feature) {
    const iso = isoOf(feature), c = state.data.countries[iso];
    const [x, y] = d3.pointer(event, document.querySelector(".stage"));
    let rows = "";
    if (c) {
      const exp = d3.sum(cats(), (k) => c.exp[k]);
      const imp = d3.sum(cats(), (k) => c.imp[k]);
      rows =
        `<div class="tt-r"><span>Exports</span><b>${fUSD(exp)}</b></div>` +
        `<div class="tt-r"><span>Imports</span><b>${fUSD(imp)}</b></div>`;
      if (state.metric === "prod") {
        const pk = prodKeyOf(state.commodity);
        const plabel = reg(state.commodity).phase === "energy" ? "Production" : "Mine prod. (metal)";
        rows += `<div class="tt-r"><span>${plabel}</span><b>${fNum(pk && c.prod[pk], prodUnitOf(state.commodity))}</b></div>`;
      }
    } else rows = `<div class="tt-r"><span>No trade data</span></div>`;
    tooltip.html(`<div class="tt-nm">${nm(iso) || feature.properties.NAME}</div>${rows}`)
      .style("left", Math.min(x + 14, size()[0] - 240) + "px")
      .style("top", (y + 14) + "px").attr("hidden", null);
  }
  function hideTip() { tooltip.attr("hidden", true); }

  // ---- controls ---------------------------------------------------------
  function wireControls() {
    d3.selectAll("#view button").on("click", function () { setMode(this.dataset.v); });
    d3.select("#commodity").on("change", function () {
      state.commodity = this.value;
      state.selectedRoute = null;   // route selection is per-commodity
      updateChainButton();
      draw();
    });
    d3.select("#chain").on("click", function () {
      if (!metalPair()) return;
      state.valueChain = !state.valueChain;
      state.selected = null;
      updateChainButton();
      draw();
    });
    d3.select("#metric").on("change", function () { state.metric = this.value; draw(); });
    d3.select("#source").on("change", function () { state.source = this.value; draw(); });
    d3.select("#topN").on("input", function () {
      state.topN = +this.value; document.getElementById("topN-val").textContent = this.value;
      if (state.mode === "trade" && !state.selected) drawArcs();
    });
    d3.select("#reset").on("click", () => {
      state.selected = null; state.selectedRoute = null; state.selectedFacility = null;
      svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity);
      draw();
    });
    d3.select("#back").on("click", () => { state.selected = null; draw(); });
    d3.select("#fac-back").on("click", () => { state.selectedFacility = null; draw(); });
    d3.select("#flow-back").on("click", () => { state.selectedFlow = null; draw(); });
    d3.select("#port-back").on("click", () => { state.selectedPort = null; draw(); });
    d3.selectAll("#layers button").on("click", function () {
      const l = this.dataset.l;
      state.layers[l] = !state.layers[l];
      this.classList.toggle("on", state.layers[l]);
      draw();
    });
    d3.select("#panel-toggle").on("click", function () {
      const app = document.getElementById("app");
      const collapsed = app.classList.toggle("collapsed");
      this.textContent = collapsed ? "›" : "‹";
      this.title = collapsed ? "Show panel" : "Hide panel";
      // let the grid finish animating, then refit the map to the new width
      setTimeout(fit, 300);
    });
    window.addEventListener("resize", debounce(fit, 150));
  }

  let curK = 1;
  const zoom = d3.zoom().scaleExtent([1, 8]).on("zoom", (e) => {
    curK = e.transform.k;
    gMap.attr("transform", e.transform);
    gArcs.selectAll("path.arc").attr("stroke-width", function () {
      return (+this.getAttribute("data-w") || 1) / Math.sqrt(curK);
    });
    gArcHit.selectAll("path.arc-hit").attr("stroke-width", 11 / Math.sqrt(curK));
    gNodes.selectAll("circle.node").attr("r", function () {
      return (+this.getAttribute("data-r") || 2) / Math.sqrt(curK);
    });
    gLabels.selectAll("text.lbl").style("font-size", function () {
      return (this.classList.contains("self") ? 12 : 9.5) / Math.sqrt(curK) + "px";
    });
    gCountries.selectAll("path.country").attr("stroke-width", 0.4 / curK);
    gRoutes.selectAll("path.route").attr("stroke-width", function () {
      return (+this.getAttribute("data-w") || 1) / Math.sqrt(curK);
    });
    gChokes.selectAll("circle.choke").attr("r", function () {
      return (this.classList.contains("rsel") ? 5 : 3.3) / Math.sqrt(curK);
    });
    gRouteLabels.selectAll("text.rlbl").style("font-size", function () {
      return (this.classList.contains("rsel") ? 11 : 9) / Math.sqrt(curK) + "px";
    });
    gFacilities.selectAll("path.fac").attr("transform", (d) =>
      `translate(${d.p[0]},${d.p[1]}) scale(${1 / Math.sqrt(curK)})`);
    gPorts.selectAll("path.port").attr("transform", (d) =>
      `translate(${d.p[0]},${d.p[1]}) scale(${1 / Math.sqrt(curK)})`);
  });

  function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

  // ---- boot -------------------------------------------------------------
  async function boot() {
    if (location.protocol === "file:") {
      document.getElementById("loading").innerHTML =
        "Serve over HTTP — run:<br><code style='color:#F4A93C'>python3 -m http.server -d app/public 8000</code><br>then open localhost:8000";
      return;
    }
    let data, world;
    try {
      [data, world] = await Promise.all([
        SB.get("map_snapshot?commodity=eq.__all__&select=data").then((r) => r[0].data),
        d3.json("world.geojson"),
      ]);
    } catch (e) {
      document.getElementById("loading").textContent =
        "Could not load data. Run: python3 app/build_data.py"; return;
    }
    state.data = data;
    state.ports = data.ports || {};
    data.meta.commodities.forEach((c) => { state.registry[c.key] = c; });
    state.features = world.features;
    state.features.forEach((f) => { const i = isoOf(f); if (i) state.nameByIso[i] = f.properties.NAME; });
    // some ISO names not in geojson — fall back gracefully handled by nm()

    document.getElementById("subtitle").textContent =
      `Energy & metals trade · ${data.meta.years.join("/")} · latest available`;
    populateCommodities();
    updateChainButton();

    // Layer order: sphere (bottom) < graticule < countries < arcs < nodes.
    sphere = gMap.insert("path", ":first-child").attr("class", "sphere");
    graticule = gMap.insert("path", "g").attr("class", "graticule"); // before first <g>

    gCountries.selectAll("path.country")
      .data(state.features).enter().append("path")
      .attr("class", "country hoverable")
      .on("mousemove", showTip).on("mouseleave", hideTip)
      .on("click", (e, f) => {
        e.stopPropagation();
        const i = isoOf(f);
        if (i) select(i);   // overview: profile · trade: isolate routes
      });
    svg.on("click", () => {
      if (state.selected) { state.selected = null; draw(); }
      else if (state.selectedFacility) { state.selectedFacility = null; draw(); }
      else if (state.selectedFlow) { state.selectedFlow = null; draw(); }
      else if (state.selectedPort) { state.selectedPort = null; draw(); }
    });

    svg.call(zoom);
    document.getElementById("loading").remove();
    fit();
    wireControls();
  }

  boot();
})();
