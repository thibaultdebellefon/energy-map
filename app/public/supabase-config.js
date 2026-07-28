/* Supabase browser client — the frontend reads its data live from Supabase's
   REST API (PostgREST). The URL and anon (publishable) key are PUBLIC by design:
   every table has Row-Level Security with a read-only policy for the anon role,
   so this key can only SELECT, never write. Safe to ship in the browser. */
(function () {
  "use strict";
  var URL = "https://wrjxtycpqcrjwezcyjor.supabase.co";
  var KEY = "sb_publishable_XhGbRwEKRiJrkymVMwl5Bg_xTQrdOck";

  window.SB = {
    url: URL,
    key: KEY,
    // GET a PostgREST path, e.g. SB.get("news?select=*&limit=10") -> rows[]
    get: function (path) {
      return fetch(URL + "/rest/v1/" + path, {
        headers: { apikey: KEY, Authorization: "Bearer " + KEY },
      }).then(function (r) {
        if (!r.ok) throw new Error("Supabase " + r.status + " on " + path);
        return r.json();
      });
    },
  };
})();
