/* Estatisticas do site (Umami), 17/11/2026. A contagem de visitas e feita
   pelo /umami/script.js; aqui so os cliques que levam ao cadastro e ao login,
   para medir o caminho visita -> cadastro. Nenhum dado pessoal e enviado:
   so o nome do evento e a pagina onde o clique aconteceu. */
document.addEventListener('click', function (e) {
  var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
  if (!a || !window.umami || typeof window.umami.track !== 'function') return;
  var h = a.getAttribute('href') || '';
  var evento = /\/cadastro(?:[\/?#]|$)/.test(h) ? 'clique-cadastro'
    : /\/app\/#\/login|\/login(?:[\/?#]|$)/.test(h) ? 'clique-entrar' : '';
  if (evento) window.umami.track(evento, { pagina: location.pathname });
}, true);
