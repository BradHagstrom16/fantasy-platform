// Shared client-side flag-image builder — mirrors the server-side _flag.html
// Jinja macro so JS-rendered rows match every other WC surface. Renders a
// self-hosted SVG (emoji flags show as bare "GB"/"MX" on Windows). `iso` always
// originates server-side from WorldCupTeam.iso_code, but the result is inserted
// via innerHTML, so we validate it against the canonical ISO-2 shape and fall
// back to the neutral `_tbd` placeholder for anything missing or malformed —
// defense-in-depth plus the macro's falsy→`_tbd` semantics. `base` is the
// static flags-dir URL, `version` the asset_version cache-bust; both are
// Jinja-injected per page.
function cccFlagImg(base, version, iso) {
  var code = /^[a-z]{2}$/.test(iso) ? iso : '_tbd';
  return '<img class="ccc-flag" src="' + base + code + '.svg?v=' + version + '" alt="" loading="lazy" decoding="async">';
}
