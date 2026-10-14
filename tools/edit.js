// Inline text editor, injected by tools/edit.py. Never deployed.
const els = [...document.querySelectorAll('[data-en]')];
const status = document.createElement('div');
status.className = 'edit-status';
status.textContent = 'Bearbeiten: Text oder Bild anklicken · Enter speichert · Shift+Enter Zeilenumbruch · Esc verwirft';
document.body.append(status);

function show(text, error) {
  status.textContent = text;
  status.classList.toggle('error', !!error);
}

// Contenteditable sometimes adds inline styles, which the CSP forbids.
function clean(el) {
  el.querySelectorAll('[style]').forEach(n => n.removeAttribute('style'));
  el.querySelectorAll('span:not([class]):not([data-en])').forEach(n => n.replaceWith(...n.childNodes));
  // Chrome inserts a placeholder <br> after a line break at the end.
  return el.innerHTML.replace(/(<br>\s*)+/g, '<br>').replace(/(<br>|\s)+$/, '').trim();
}

async function finish(el, original) {
  el.removeAttribute('contenteditable');
  const html = clean(el);
  if (html === original) return;
  const lang = document.documentElement.lang === 'en' ? 'en' : 'de';
  const res = await fetch('/__edit/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ page: location.pathname, index: els.indexOf(el), tag: el.tagName.toLowerCase(), lang, html }),
  });
  if (!res.ok) {
    el.innerHTML = original;
    return show(`Nicht gespeichert: ${await res.text()}`, true);
  }
  // Keep main.js's language cache in sync so switching languages shows the new text.
  if (lang === 'en') el.dataset.en = html;
  else if (el.dataset.de !== undefined) el.dataset.de = html;
  show(`Gespeichert (${lang.toUpperCase()}): ${el.textContent.slice(0, 60)}`);
}

function edit(el) {
  const original = el.innerHTML.trim();
  let cancelled = false;
  el.contentEditable = 'true';
  el.focus();
  el.addEventListener('keydown', function key(e) {
    if (e.key === 'Enter' && e.shiftKey) {
      e.preventDefault();
      document.execCommand('insertLineBreak');
    } else if (e.key === 'Enter' || e.key === 'Escape') {
      e.preventDefault();
      cancelled = e.key === 'Escape';
      el.blur();
    }
  });
  el.addEventListener('paste', e => {
    e.preventDefault();
    document.execCommand('insertText', false, e.clipboardData.getData('text/plain'));
  });
  el.addEventListener('blur', () => {
    if (cancelled) {
      el.removeAttribute('contenteditable');
      el.innerHTML = original;
      show('Verworfen');
    } else finish(el, original);
  }, { once: true });
}

document.addEventListener('click', e => {
  const el = e.target.closest('[data-en]');
  if (!el) return;
  e.preventDefault();
  if (!el.isContentEditable) edit(el);
}, true);

// Images: click one to swap it for another from site/img or a new upload.
const imgs = [...document.querySelectorAll('img')];
const panel = document.createElement('dialog');
panel.className = 'edit-panel';
panel.innerHTML = `
  <h2>Bild tauschen</h2>
  <label>Neues Bild hochladen (JPG, PNG, WebP) <input type="file" accept="image/jpeg,image/png,image/webp"></label>
  <div class="edit-grid"></div>
  <label>Beschreibung DE <input name="alt"></label>
  <label>Beschreibung EN <input name="altEn"></label>
  <div class="edit-actions"><button type="button" value="cancel">Abbrechen</button><button type="button" value="save">Übernehmen</button></div>`;
document.body.append(panel);
const grid = panel.querySelector('.edit-grid');
let target, chosen;

function choose(base) {
  chosen = base;
  grid.querySelectorAll('button').forEach(b => b.classList.toggle('chosen', b.dataset.base === base));
}

function addThumb(base, first) {
  const b = document.createElement('button');
  b.type = 'button';
  b.dataset.base = base;
  b.innerHTML = `<img src="/img/${base}-700.webp" loading="lazy" alt="${base}">`;
  b.title = base;
  b.addEventListener('click', () => choose(base));
  if (first) grid.prepend(b);
  else grid.append(b);
}

async function openPanel(img) {
  target = img;
  const current = img.getAttribute('src').match(/^\/img\/(.+)-(?:700|1400)\.webp$/);
  if (!current) return show('Dieses Bild lässt sich nicht tauschen', true);
  grid.replaceChildren();
  (await (await fetch('/__edit/images')).json()).forEach(base => addThumb(base));
  choose(current[1]);
  panel.querySelector('[name=alt]').value = img.dataset.deAlt ?? img.alt;
  panel.querySelector('[name=altEn]').value = img.dataset.enAlt;
  panel.showModal();
  grid.querySelector('.chosen')?.scrollIntoView({ block: 'center' });
}

panel.querySelector('[type=file]').addEventListener('change', async e => {
  const file = e.target.files[0];
  if (!file) return;
  show('Lade hoch und wandle um …');
  const res = await fetch(`/__edit/upload?name=${encodeURIComponent(file.name)}`, { method: 'POST', body: file });
  e.target.value = '';
  if (!res.ok) return show(`Upload fehlgeschlagen: ${await res.text()}`, true);
  const base = await res.json();
  addThumb(base, true);
  choose(base);
  grid.scrollTop = 0;
  show(`Hochgeladen: ${base}`);
});

panel.querySelector('.edit-actions').addEventListener('click', async e => {
  if (e.target.value === 'cancel') return panel.close();
  if (e.target.value !== 'save') return;
  const res = await fetch('/__edit/image', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      page: location.pathname,
      index: imgs.indexOf(target),
      base: chosen,
      alt: panel.querySelector('[name=alt]').value.trim(),
      altEn: panel.querySelector('[name=altEn]').value.trim(),
    }),
  });
  if (!res.ok) return show(`Nicht gespeichert: ${await res.text()}`, true);
  location.reload();
});

document.addEventListener('click', e => {
  const img = e.target.closest('img');
  if (!img || panel.contains(img)) return;
  e.preventDefault();
  openPanel(img);
}, true);
