// Inline text editor, injected by tools/edit.py. Never deployed.
const els = [...document.querySelectorAll('[data-en]')];
const status = document.createElement('div');
status.className = 'edit-status';
status.textContent = 'Bearbeiten: Text anklicken · Enter speichert · Shift+Enter Zeilenumbruch · Esc verwirft';
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
