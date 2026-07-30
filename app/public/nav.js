/* Shared top navigation across the site's sections. Preserves the selected
   commodity across pages via a ?commodity= URL param (full cross-section sync
   is a later session; the plumbing lives here). */
(function () {
  const params = new URLSearchParams(location.search);
  // Sanitize: commodity keys are word chars only — prevents any URL-borne XSS.
  const commodity = (params.get("commodity") || "").replace(/[^\w-]/g, "");
  const q = commodity ? "?commodity=" + encodeURIComponent(commodity) : "";
  const page = location.pathname.split("/").pop() || "index.html";

  const links = [
    ["map.html", "Map"],
    ["companies.html", "Companies"],
    ["news.html", "News"],
    ["trading.html", "Trading"],
  ];
  const nav = document.createElement("nav");
  nav.className = "site-nav";
  nav.innerHTML =
    `<a class="site-brand" href="index.html${q}"><span class="mk"></span>VANTAGE</a>` +
    `<div class="site-links">` +
    links.map(([href, label]) =>
      `<a href="${href}${q}"${page === href ? ' class="active"' : ""}>${label}</a>`
    ).join("") +
    `</div>`;
  document.body.classList.add("has-nav");
  document.body.prepend(nav);
})();
