/* Shared commodity registry — single source of truth for the site's signature
   colour system. Every surface (ticker, news tags, chart lines, watchlist dots)
   reads from here so a commodity looks the same everywhere. Colours are
   subject-linked, not arbitrary: cobalt blue, copper orange, lithium battery
   lime, rare-earths violet, etc. */
(function () {
  "use strict";
  // Canonical order used across News / Trading / landing.
  const ORDER = ["crude", "lng", "copper", "aluminium", "cobalt", "lithium",
    "nickel", "rare_earths", "zinc", "tin", "manganese", "graphite"];

  const META = {
    crude:       { label: "Crude oil",   short: "WTI",   color: "#F4A93C", cls: "energy" },
    lng:         { label: "LNG",         short: "Asia",  color: "#46D5E4", cls: "energy" },
    copper:      { label: "Copper",      short: "Cu",    color: "#E8794B", cls: "metal" },
    aluminium:   { label: "Aluminium",   short: "Al",    color: "#9FB4C7", cls: "metal" },
    cobalt:      { label: "Cobalt",      short: "Co",    color: "#4B7BEC", cls: "metal" },
    lithium:     { label: "Lithium",     short: "Li",    color: "#B7E23F", cls: "metal" },
    nickel:      { label: "Nickel",      short: "Ni",    color: "#5FD9A6", cls: "metal" },
    rare_earths: { label: "Rare earths", short: "REE",   color: "#C77DFF", cls: "metal" },
    zinc:        { label: "Zinc",        short: "Zn",    color: "#7FA8C9", cls: "metal" },
    tin:         { label: "Tin",         short: "Sn",    color: "#C6CDD8", cls: "metal" },
    manganese:   { label: "Manganese",   short: "Mn",    color: "#D96BA0", cls: "metal" },
    graphite:    { label: "Graphite",    short: "C",     color: "#8B94A2", cls: "metal" },
  };

  const label = (k) => (META[k] && META[k].label) ||
    k.charAt(0).toUpperCase() + k.slice(1).replace(/_/g, " ");
  const color = (k) => (META[k] && META[k].color) || "#E07B4B";
  const short = (k) => (META[k] && META[k].short) || label(k);

  // Sanitise a commodity key coming from a URL param (prevents URL-borne XSS).
  const clean = (s) => (s || "").replace(/[^\w-]/g, "");

  window.COMMODITIES = { ORDER, META, label, color, short, clean };
})();
