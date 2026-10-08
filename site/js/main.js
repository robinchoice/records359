const burger = document.querySelector('.burger');
const nav = document.querySelector('.nav');
burger?.addEventListener('click', () => {
  const open = nav.classList.toggle('open');
  burger.setAttribute('aria-expanded', open);
});
nav?.addEventListener('click', e => {
  if (e.target.closest('a')) nav.classList.remove('open');
});

// German is the default in the markup; English lives in data-en attributes.
function setLang(lang) {
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-en]').forEach(el => {
    if (el.dataset.de === undefined) el.dataset.de = el.innerHTML;
    el.innerHTML = lang === 'en' ? el.dataset.en : el.dataset.de;
  });
  document.querySelectorAll('[data-en-content]').forEach(el => {
    if (el.dataset.deContent === undefined) el.dataset.deContent = el.content;
    el.content = lang === 'en' ? el.dataset.enContent : el.dataset.deContent;
  });
  document.querySelectorAll('.lang').forEach(b => { b.textContent = lang === 'en' ? 'DE' : 'EN'; });
  localStorage.setItem('records359-lang', lang);
}

const saved = localStorage.getItem('records359-lang');
const lang = saved || (navigator.language.toLowerCase().startsWith('de') ? 'de' : 'en');
if (lang === 'en') setLang('en');
document.querySelectorAll('.lang').forEach(b => b.addEventListener('click', () => {
  setLang(document.documentElement.lang === 'en' ? 'de' : 'en');
}));
