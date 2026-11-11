/* Condicoes do teste gratuito do FROID Psique, lidas do servidor.
 *
 * Usado pela secao "Inscricao Profissional Gratuita" (gerada em toda pagina
 * do Psique por tools/gerar-inscricao-psique.py) e por qualquer texto marcado
 * com .teste-condicoes ou .teste-qtd. O texto escrito no HTML e o mesmo do
 * catalogo (froid-server/psique_pricing.py: TRIAL_CREDITS, TRIAL_DAYS), e
 * tests/test_inscricao_psique.py confere isso; aqui ele e trocado pelo que o
 * servidor responde, para que uma mudanca no catalogo chegue ao site sem
 * ninguem lembrar de editar pagina.
 *
 * Se a consulta falhar (previa local, rede), o texto escrito continua.
 */
(function () {
  var condicoes = document.querySelectorAll('.teste-condicoes');
  var quantidades = document.querySelectorAll('.teste-qtd');
  if (!condicoes.length && !quantidades.length) return;
  fetch('/api/psique/v2/pricing?language=pt')
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function (c) {
      var t = c && c.trial;
      if (!t || !t.credits || !t.days) return;
      var frase = t.credits + ' sessões gratuitas, válidas por ' + t.days + ' dias';
      for (var i = 0; i < condicoes.length; i++) condicoes[i].textContent = frase;
      for (var j = 0; j < quantidades.length; j++) quantidades[j].textContent = String(t.credits);
    })
    .catch(function () {});
})();
