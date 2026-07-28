/* Companies section — a map-like view of the majors and trading houses that
   move the world's commodities: their flagship operated assets plotted on the
   same Natural Earth projection as the main map, plus a profile card and a
   footprint across the commodities we track.

   Data: companies.json (built by app/build_companies.py) + world.geojson.
   All company/asset copy is our own curated data, so building markup from it is
   trusted; the only user-controlled input is the ?company= param, sanitised. */
(function () {
  "use strict";
  const C = window.COMMODITIES;

  // Asset type -> broad category (drives marker shape + legend).
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

  const svg = d3.select("#cmap");
  const projection = d3.geoNaturalEarth1();
  const path = d3.geoPath(projection);
  let world = null, features = [], companies = [], byId = {}, current = null;
  let gSphere, gGrat, gCountries, gMarks;

  const clean = (s) => (s || "").replace(/[^\w-]/g, "");

  // ---------------------------------------------------------------- panel ---
  function renderPicker() {
    const box = document.getElementById("picker");
    box.innerHTML = "";
    const groups = [["Supermajors", "Supermajor"], ["Trading houses", "Trading house"]];
    groups.forEach(([label, type]) => {
      const h = document.createElement("div");
      h.className = "co-group"; h.textContent = label;
      box.appendChild(h);
      const grid = document.createElement("div");
      grid.className = "co-chip-grid";
      companies.filter((c) => c.type === type).forEach((c) => {
        const b = document.createElement("button");
        b.className = "co-chip" + (current && c.id === current.id ? " on" : "");
        b.style.setProperty("--c", c.color);
        b.innerHTML = `<span class="d"></span><span class="n"></span>`;
        b.querySelector(".n").textContent = c.name;
        b.onclick = () => select(c.id);
        grid.appendChild(b);
      });
      box.appendChild(grid);
    });
  }

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

  function renderProfile(c) {
    const p = document.getElementById("profile");
    p.innerHTML = "";

    const card = document.createElement("div");
    card.className = "co-card";
    card.style.setProperty("--c", c.color);
    const priv = c.listing === "Private";
    card.innerHTML =
      `<div class="co-name"><span class="mono-tag">${c.type}</span><h2></h2></div>` +
      `<p class="co-blurb"></p>` +
      `<div class="co-meta">` +
      metaRow("HQ", c.hq) + metaRow("Founded", c.founded) +
      metaRow("People", d3.format(",")(c.employees)) +
      metaRow(priv ? "Turnover" : "Revenue", c.revenue) +
      metaRow("Listing", c.listing) +
      `</div>` +
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

  function metaRow(k, v) {
    return `<div class="mrow"><span class="k">${k}</span><span class="v">${v}</span></div>`;
  }
  function reach(n, label) {
    return `<div class="r"><b>${n}</b><span>${label}</span></div>`;
  }

  // ------------------------------------------------------------------ map ---
  function size() {
    const box = svg.node().getBoundingClientRect();
    return [Math.max(320, box.width), Math.max(320, box.height)];
  }

  function setup() {
    gSphere = svg.append("path").attr("class", "sphere");
    gGrat = svg.append("path").attr("class", "graticule");
    gCountries = svg.append("g");
    gMarks = svg.append("g");
  }

  function fit() {
    const [w, h] = size();
    projection.fitExtent([[8, 8], [w - 8, h - 8]], { type: "Sphere" });
    gSphere.attr("d", path({ type: "Sphere" }));
    gGrat.attr("d", path(d3.geoGraticule10()));
    gCountries.selectAll("path").attr("d", path);
    if (current) placeMarks(current);
  }

  function countryOf(asset) {
    const pt = [asset.lon, asset.lat];
    return features.find((f) => d3.geoContains(f, pt)) || null;
  }

  function drawCountries(c) {
    const hi = new Set();
    c.assets.forEach((a) => { const f = countryOf(a); if (f) hi.add(f); });
    const sel = gCountries.selectAll("path").data(features);
    sel.enter().append("path").attr("class", "country").merge(sel)
      .attr("d", path)
      .style("fill", (f) => hi.has(f) ? c.color : null)
      .style("fill-opacity", (f) => hi.has(f) ? 0.22 : 1)
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
        const sz = cat === "Office" ? 70 : 96;
        return d3.symbol().type(SYMBOL[cat]).size(sz)();
      })
      .attr("fill", (d) => C.color(d.commodity))
      .attr("stroke", "#06090f").attr("stroke-width", 1.2)
      .attr("fill-opacity", 0.95);
    all.on("click", (ev, d) => { ev.stopPropagation(); showPop(d); })
      .on("mouseenter", function () { d3.select(this).select("path").attr("stroke", "#EDF3FA"); })
      .on("mouseleave", function () { d3.select(this).select("path").attr("stroke", "#06090f"); });
  }

  function drawMap(c) {
    drawCountries(c);
    placeMarks(c);
    hidePop();
  }

  // ----------------------------------------------------------- asset popup --
  function showPop(a) {
    const pop = document.getElementById("pop");
    const cat = CATEGORY[a.type] || "Office";
    const col = C.color(a.commodity);
    pop.innerHTML =
      `<div class="pop-x" id="pop-x">×</div>` +
      `<div class="pop-k" style="color:${col}"></div>` +
      `<div class="pop-t"></div>` +
      `<div class="pop-m"><span class="chip2" style="--c:${col}"><span class="dot"></span></span>` +
      `<span class="ctry"></span></div>` +
      `<div class="pop-note"></div>`;
    pop.querySelector(".pop-k").textContent = TYPE_LABEL[a.type] || cat;
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
    document.getElementById("pop-x").onclick = (e) => { e.stopPropagation(); hidePop(); };
  }
  function hidePop() { const p = document.getElementById("pop"); if (p) p.hidden = true; }

  function renderLegend() {
    const box = document.getElementById("legend");
    const cats = ["Production", "Processing", "Logistics", "Office"];
    box.innerHTML = `<div class="lg-h">Asset type</div>` +
      cats.map((cat) => {
        const d = d3.symbol().type(SYMBOL[cat]).size(70)();
        return `<span class="lg"><svg width="14" height="14" viewBox="-8 -8 16 16">` +
          `<path d="${d}" fill="#8593A4"/></svg>${cat}</span>`;
      }).join("") +
      `<div class="lg-note">Colour = commodity</div>`;
  }

  // --------------------------------------------------------------- select ---
  function select(id) {
    current = byId[id] || companies[0];
    const u = new URL(location.href);
    u.searchParams.set("company", current.id);
    history.replaceState(null, "", u);
    renderPicker();
    renderProfile(current);
    drawMap(current);
  }

  // Live from Supabase: one embedded query pulls each company with its footprint
  // and assets nested (PostgREST resource embedding via the FK relationships).
  Promise.all([
    SB.get("companies?select=id,name,type,hq,founded,employees,revenue,listing,color,blurb," +
      "company_footprint(commodity,role,presence,note)," +
      "company_assets(name,type,commodity,country,lat,lon,note)&order=sort_order"),
    d3.json("world.geojson"),
  ]).then(([cd, w]) => {
    companies = (cd || []).map((c) => {
      const assets = c.company_assets || [], footprint = c.company_footprint || [];
      return Object.assign({}, c, {
        assets: assets, footprint: footprint,
        numAssets: assets.length,
        numCountries: new Set(assets.map((a) => a.country)).size,
        commodities: footprint.map((f) => f.commodity),
      });
    });
    companies.forEach((c) => { byId[c.id] = c; });
    world = w;
    features = (w.features || []).filter((f) => f.geometry);
    document.getElementById("roster-count").textContent =
      companies.length + " companies · 1 map";
    setup();
    renderLegend();
    gCountries.selectAll("path").data(features).enter().append("path")
      .attr("class", "country").attr("d", path);
    const want = clean(new URLSearchParams(location.search).get("company"));
    current = byId[want] || companies[0];
    fit();
    renderPicker();
    renderProfile(current);
    drawMap(current);
    window.addEventListener("resize", fit);
    svg.on("click", hidePop);
  }).catch(() => {
    document.getElementById("profile").innerHTML =
      '<div class="co-err">Could not load companies.json — run <code>python app/build_companies.py</code>.</div>';
  });
})();
