// Shared client-side flag-image builder — mirrors the server-side _flag.html
// Jinja macro so JS-rendered rows match every other WC surface. Renders a
// self-hosted SVG (emoji flags show as bare "GB"/"MX" on Windows) and falls
// back to the neutral `_tbd` placeholder for a missing iso, exactly like the
// macro. `base` is the static flags-dir URL, `version` the asset_version
// cache-bust; both are Jinja-injected per page.
function cccFlagImg(base, version, iso) {
  return '<img class="ccc-flag" src="' + base + (iso || '_tbd') + '.svg?v=' + version + '" alt="" loading="lazy" decoding="async">';
}
