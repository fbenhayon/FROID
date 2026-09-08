// Melhorias progressivas: sem JavaScript, os links originais continuam disponíveis.
document.addEventListener('DOMContentLoaded', function () {
  var lang = document.documentElement.lang.slice(0, 2);
  var labels = {
    pt: ['Menu', 'Nesta página', 'Ir para o conteúdo'],
    en: ['Menu', 'On this page', 'Skip to content'],
    es: ['Menú', 'En esta página', 'Ir al contenido'],
    fr: ['Menu', 'Sur cette page', 'Aller au contenu']
  }[lang] || ['Menu', 'Nesta página', 'Ir para o conteúdo'];
  var header = document.querySelector('.site-header');
  var nav = document.querySelector('.nav-links');
  if (header && nav) {
    nav.id = 'site-navigation';
    var toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'site-menu-toggle';
    toggle.textContent = labels[0];
    toggle.setAttribute('aria-controls', nav.id);
    toggle.setAttribute('aria-expanded', 'false');
    header.querySelector('.nav-row').prepend(toggle);
    header.classList.add('menu-enhanced');
    function closeMenu() {
      header.classList.remove('menu-open');
      toggle.setAttribute('aria-expanded', 'false');
    }
    toggle.addEventListener('click', function () {
      var open = header.classList.toggle('menu-open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    header.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && header.classList.contains('menu-open')) {
        closeMenu();
        toggle.focus();
      }
    });
    nav.addEventListener('click', function (event) {
      if (event.target.closest('a')) closeMenu();
    });
  }
  // Algumas páginas usam o id no título, outras na seção que o contém.
  var seen = new Set();
  var sections = Array.from(document.querySelectorAll('h2')).map(function (heading) {
    var target = heading.id ? heading : heading.closest('section[id]');
    if (!target || seen.has(target.id)) return null;
    seen.add(target.id);
    return { target: target, heading: heading };
  }).filter(Boolean);
  if (!sections.length) return;
  var first = sections[0].target;
  var skip = document.createElement('a');
  skip.href = '#' + first.id;
  skip.className = 'skip-content';
  skip.textContent = labels[2];
  first.tabIndex = -1;
  document.body.prepend(skip);
  var outline = document.createElement('aside');
  outline.className = 'page-outline';
  var details = document.createElement('details');
  var summary = document.createElement('summary');
  summary.textContent = labels[1];
  var links = document.createElement('nav');
  links.setAttribute('aria-label', labels[1]);
  sections.forEach(function (section) {
    var link = document.createElement('a');
    link.href = '#' + section.target.id;
    link.textContent = section.heading.textContent.trim();
    links.append(link);
  });
  details.append(summary, links);
  outline.append(details);
  (first.closest('section') || first).before(outline);
});
