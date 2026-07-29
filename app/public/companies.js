/* Companies — a discovery flow: a welcome screen ("which company's
   infrastructure would you like to discover?") with a search + popular picks,
   then a company view with a search/switch box, suggestions, a profile card and
   the operated-assets map (same Natural Earth projection as the main map).
   Data: Supabase (companies + nested footprint/assets) + world.geojson. */
(function () {
  "use strict";
  const C = window.COMMODITIES;
  const esc = (s) => (s || "").replace(/[&<>"]/g, (m) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));

  const CATEGORY = {
    oilfield: "Production", offshore: "Production", mine: "Production",
    refinery: "Processing", smelter: "Processing", lng: "Processing",
    terminal: "Logistics", office: "Office",
  };
  const SYMBOL = {
    Production: d3.symbolCircle, Processing: d3.symbolSquare,
    Logistics: d3.symbolDiamond, Office: d3.symbolCross,
  };
  const TYPE_LABEL = {
    oilfield: "Oil & gas field", offshore: "Offshore field", mine: "Mine",
    refinery: "Refinery", smelter: "Smelter", lng: "LNG plant",
    terminal: "Terminal / storage", office: "Trading office",
  };
  const TYPE_SHORT = {
    "National oil company": "National oil co.", "Supermajor": "Supermajor",
    "Trading house": "Trading house", "Diversified miner": "Miner",
  };
  const QUICK = ["aramco", "shell", "exxonmobil", "glencore", "totalenergies",
    "gazprom", "trafigura", "vale", "bp", "riotinto", "qatarenergy", "petrobras"];

  const svg = d3.select("#cmap");
  const projection = d3.geoNaturalEarth1();
  const path = d3.geoPath(projection);
  let world = null, features = [], companies = [], byId = {}, current = null;
  let gSphere, gGrat, gCountries, gMarks, mapReady = false;

  const clean = (s) => (s || "").replace(/[^\w-]/g, "");
  const $ = (id) => document.getElementById(id);

  // -------------------------------------------------------- search + browse ---
  function matchCompanies(q) {
    q = (q || "").trim().toLowerCase();
    if (!q) return companies;
    return companies.filter((c) => c.name.toLowerCase().includes(q) ||
      (c.type || "").toLowerCase().includes(q));
  }
  function resultRow(c) {
    return `<button class="co-res" data-id="${c.id}">` +
      `<span class="d" style="background:${c.color}"></span>` +
      `<span class="rn">${esc(c.name)}</span>` +
      `<span class="rt">${esc(TYPE_SHORT[c.type] || c.type)}</span></button>`;
  }
  function wireSearch(input, box) {
    const render = () => {
      const m = matchCompanies(input.value);
      box.innerHTML = m.length ? m.slice(0, 40).map(resultRow).join("")
        : `<div class="co-nores">No company found</div>`;
      box.querySelectorAll("[data-id]").forEach((el) => {
        el.onmousedown = (e) => { e.preventDefault(); select(el.dataset.id);
          input.blur(); box.classList.remove("open"); };
      });
      box.classList.add("open");
    };
    input.addEventListener("focus", render);
    input.addEventListener("input", render);
    input.addEventListener("blur", () => setTimeout(() => box.classList.remove("open"), 160));
  }
  function chip(c, cls) {
    return `<button class="${cls}" data-id="${c.id}">` +
      `<span class="d" style="background:${c.color}"></span>${esc(c.name)}</button>`;
  }
  function renderQuick() {
    const box = $("welcome-quick");
    box.innerHTML = QUICK.filter((id) => byId[id]).map((id) => chip(byId[id], "co-quick-chip")).join("");
    box.querySelectorAll("[data-id]").forEach((el) => el.onclick = () => select(el.dataset.id));
  }
  function renderSuggest(c) {
    const box = $("co-suggest");
    const same = companies.filter((x) => x.type === c.type && x.id !== c.id);
    const others = companies.filter((x) => x.type !== c.type && x.id !== c.id);
    box.innerHTML = same.concat(others).slice(0, 6).map((x) => chip(x, "co-sug-chip")).join("");
    box.querySelectorAll("[data-id]").forEach((el) => el.onclick = () => select(el.dataset.id));
  }

  // -------------------------------------------------------------- profile ----
  function bar(f) {
    const col = C.color(f.commodity);
    const el = document.createElement("a");
    el.className = "co-bar";
    el.href = "trading.html?commodity=" + encodeURIComponent(f.commodity);
    el.title = "Open " + C.label(f.commodity) + " in Trading";
    el.innerHTML =
      `<div class="co-bar-top"><span class="nm"><span class="dot" style="background:${col}"></span></span>` +
      `<span class="role"></span></div>` +
      `<div class="track"><span class="fill" style="width:${f.presence}%;background:${col}"></span></div>` +
      `<div class="note"></div>`;
    el.querySelector(".nm").insertAdjacentText("beforeend", C.label(f.commodity));
    el.querySelector(".role").textContent = f.role;
    el.querySelector(".note").textContent = f.note || "";
    return el;
  }
  function metaRow(k, v) {
    return `<div class="mrow"><span class="k">${k}</span><span class="v">${v}</span></div>`;
  }
  function reach(n, label) { return `<div class="r"><b>${n}</b><span>${label}</span></div>`; }

  function renderProfile(c) {
    const p = $("profile");
    p.innerHTML = "";
    const card = document.createElement("div");
    card.className = "co-card";
    card.style.setProperty("--c", c.color);
    const priv = c.listing === "Private";
    card.innerHTML =
      `<div class="co-name"><span class="mono-tag">${esc(c.type)}</span><h2></h2></div>` +
      `<p class="co-blurb"></p><div class="co-meta">` +
      metaRow("HQ", esc(c.hq)) + metaRow("Founded", c.founded || "—") +
      metaRow("People", c.employees ? d3.format(",")(c.employees) : "—") +
      metaRow(priv ? "Turnover" : "Revenue", esc(c.revenue || "—")) +
      metaRow("Listing", esc(c.listing || "—")) + `</div>` +
      `<div class="co-reach">` +
      reach(c.numAssets, "flagship assets") + reach(c.numCountries, "countries") +
      reach(c.commodities.length, "commodities") + `</div>`;
    card.querySelector("h2").textContent = c.name;
    card.querySelector(".co-blurb").textContent = c.blurb;
    p.appendChild(card);
    const fh = document.createElement("div");
    fh.className = "co-foot-h"; fh.textContent = "Position across commodities";
    p.appendChild(fh);
    c.footprint.slice().sort((a, b) => b.presence - a.presence).forEach((f) => p.appendChild(bar(f)));
  }

  // ------------------------------------------------------------------ map ----
  function size() {
    const box = svg.node().getBoundingClientRect();
    return [Math.max(320, box.width), Math.max(320, box.height)];
  }
  function setup() {
    gSphere = svg.append("path").attr("class", "sphere");
    gGrat = svg.append("path").attr("class", "graticule");
    gCountries = svg.append("g");
    gMarks = svg.append("g");
    gCountries.selectAll("path").data(features).enter().append("path")
      .attr("class", "country").attr("d", path);
    renderLegend();
    svg.on("click", hidePop);
  }
  function fit() {
    const [w, h] = size();
    projection.fitExtent([[8, 8], [w - 8, h - 8]], { type: "Sphere" });
    gSphere.attr("d", path({ type: "Sphere" }));
    gGrat.attr("d", path(d3.geoGraticule10()));
    gCountries.selectAll("path").attr("d", path);
    if (current) placeMarks(current);
  }
  function countryOf(a) { return features.find((f) => d3.geoContains(f, [a.lon, a.lat])) || null; }
  function drawCountries(c) {
    const hi = new Set();
    c.assets.forEach((a) => { const f = countryOf(a); if (f) hi.add(f); });
    const sel = gCountries.selectAll("path").data(features);
    sel.enter().append("path").attr("class", "country").merge(sel)
      .attr("d", path)
      .style("fill", (f) => hi.has(f) ? c.color : null)
      .style("fill-opacity", (f) => hi.has(f) ? 0.24 : 1)
      .style("stroke", (f) => hi.has(f) ? c.color : null)
      .style("stroke-opacity", (f) => hi.has(f) ? 0.5 : 1);
    sel.exit().remove();
  }
  function placeMarks(c) {
    const marks = gMarks.selectAll("g.mk").data(c.assets, (d) => d.name);
    marks.exit().remove();
    const enter = marks.enter().append("g").attr("class", "mk").style("cursor", "pointer");
    enter.append("path");
    const all = enter.merge(marks);
    all.attr("transform", (d) => {
      const p = projection([d.lon, d.lat]);
      return p ? `translate(${p[0]},${p[1]})` : "translate(-999,-999)";
    });
    all.select("path")
      .attr("d", (d) => {
        const cat = CATEGORY[d.type] || "Office";
        return d3.symbol().type(SYMBOL[cat]).size(cat === "Office" ? 70 : 96)();
      })
      .attr("fill", (d) => C.color(d.commodity))
      .attr("stroke", "#060606").attr("stroke-width", 1.2).attr("fill-opacity", 0.95);
    all.on("click", (ev, d) => { ev.stopPropagation(); showPop(d); })
      .on("mouseenter", function () { d3.select(this).select("path").attr("stroke", "#fff"); })
      .on("mouseleave", function () { d3.select(this).select("path").attr("stroke", "#060606"); });
  }
  function drawMap(c) { drawCountries(c); placeMarks(c); hidePop(); }

  function showPop(a) {
    const pop = $("pop");
    const col = C.color(a.commodity);
    pop.innerHTML =
      `<div class="pop-x" id="pop-x">×</div>` +
      `<div class="pop-k" style="color:${col}"></div><div class="pop-t"></div>` +
      `<div class="pop-m"><span class="chip2" style="--c:${col}"><span class="dot"></span></span>` +
      `<span class="ctry"></span></div><div class="pop-note"></div>`;
    pop.querySelector(".pop-k").textContent = TYPE_LABEL[a.type] || (CATEGORY[a.type] || "Office");
    pop.querySelector(".pop-t").textContent = a.name;
    pop.querySelector(".chip2").insertAdjacentText("beforeend", C.label(a.commodity));
    pop.querySelector(".ctry").textContent = a.country;
    pop.querySelector(".pop-note").textContent = a.note || "";
    pop.hidden = false;
    const p = projection([a.lon, a.lat]);
    if (p) {
      const box = svg.node().getBoundingClientRect();
      pop.style.left = Math.min(Math.max(p[0], 130), box.width - 130) + "px";
      pop.style.top = Math.max(p[1] - 12, 90) + "px";
    }
    $("pop-x").onclick = (e) => { e.stopPropagation(); hidePop(); };
  }
  function hidePop() { const p = $("pop"); if (p) p.hidden = true; }

  function renderLegend() {
    const box = $("legend");
    ["Production", "Processing", "Logistics", "Office"];
    box.innerHTML = `<div class="lg-h">Asset type</div>` +
      ["Production", "Processing", "Logistics", "Office"].map((cat) => {
        const d = d3.symbol().type(SYMBOL[cat]).size(70)();
        return `<span class="lg"><svg width="14" height="14" viewBox="-8 -8 16 16">` +
          `<path d="${d}"/></svg>${cat}</span>`;
      }).join("") + `<div class="lg-note">Colour = commodity</div>`;
  }

  // ---------------------------------------------------------- welcome/view ---
  function showWelcome() {
    $("welcome").hidden = false;
    $("company-view").hidden = true;
    const u = new URL(location.href); u.searchParams.delete("company");
    history.replaceState(null, "", u);
    $("welcome-search").value = "";
  }
  function showView() {
    $("welcome").hidden = true;
    $("company-view").hidden = false;
    if (!mapReady) { setup(); mapReady = true; }
    fit();
  }
  function select(id) {
    current = byId[id] || companies[0];
    const u = new URL(location.href); u.searchParams.set("company", current.id);
    history.replaceState(null, "", u);
    showView();
    renderProfile(current);
    drawMap(current);
    renderSuggest(current);
    const cs = $("co-search"); if (cs) cs.value = current.name;
  }

  Promise.all([
    SB.get("companies?select=id,name,type,hq,founded,employees,revenue,listing,color,blurb," +
      "company_footprint(commodity,role,presence,note)," +
      "company_assets(name,type,commodity,country,lat,lon,note)&order=sort_order"),
    d3.json("world.geojson"),
  ]).then(([cd, w]) => {
    companies = (cd || []).map((c) => {
      const assets = c.company_assets || [], footprint = c.company_footprint || [];
      return Object.assign({}, c, {
        assets, footprint,
        numAssets: assets.length,
        numCountries: new Set(assets.map((a) => a.country)).size,
        commodities: footprint.map((f) => f.commodity),
      });
    });
    companies.forEach((c) => { byId[c.id] = c; });
    world = w;
    features = (w.features || []).filter((f) => f.geometry);
    const rc = $("roster-count"); if (rc) rc.textContent = companies.length + " companies";
    renderQuick();
    wireSearch($("welcome-search"), $("welcome-results"));
    wireSearch($("co-search"), $("co-dropdown"));
    $("welcome-back") && ($("welcome-back").onclick = showWelcome);
    window.addEventListener("resize", () => { if (!$("company-view").hidden) fit(); });
    const want = clean(new URLSearchParams(location.search).get("company"));
    if (want && byId[want]) select(want); else showWelcome();
  }).catch(() => {
    const w = $("welcome"); if (w) w.innerHTML =
      '<div class="co-err" style="margin:auto">Could not load companies from Supabase.</div>';
  });
})();
