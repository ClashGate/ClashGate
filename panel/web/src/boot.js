// Boot data the panel embeds in the page as <script type="application/json" id="cs-boot"> (a data
// block, so the Content-Security-Policy needs no inline-script exception for it). Imported first in
// main.js: i18n.js and usePanel.js read window.__CS_BOOT__ while they load.
if (!window.__CS_BOOT__) {
  const el = document.getElementById('cs-boot')
  if (el) {
    try {
      window.__CS_BOOT__ = JSON.parse(el.textContent || '{}')
    } catch {
      window.__CS_BOOT__ = undefined
    }
  }
}
