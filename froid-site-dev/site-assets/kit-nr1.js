/* Formulário do kit de demonstração NR-1 (nr1/apresentacao-nr1.html).
 *
 * Envia o contato a /api/leads/nr1 com origem "kit-demonstracao-nr1". O link
 * do PDF NÃO está escrito aqui: vem na resposta do servidor (kit_url), que é
 * a única fonte do caminho. Se o servidor não devolver o link, a tela diz que
 * falhou em vez de mostrar um link adivinhado.
 */
(function () {
  var form = document.getElementById('form-kit-nr1');
  if (!form) return;

  function textoDoErro(codigo) {
    if (codigo === 429) return 'Muitos envios feitos deste dispositivo. Tente novamente mais tarde.';
    if (codigo === 400) return 'Confira os campos: nome, e-mail e empresa são obrigatórios.';
    return 'Não foi possível concluir o cadastro agora.';
  }

  form.addEventListener('submit', function (evento) {
    evento.preventDefault();
    var botao = form.querySelector('button[type=submit]');
    var status = form.querySelector('.form-status');
    var rotulo = botao.textContent;
    var valor = function (nome) {
      var el = form.querySelector('[name="' + nome + '"]');
      return el ? el.value.trim() : '';
    };
    var trabalhadores = valor('trabalhadores');
    var dados = {
      origem: 'kit-demonstracao-nr1',
      nome: valor('nome'),
      email: valor('email'),
      telefone: valor('telefone'),
      empresa: valor('empresa'),
      cargo: valor('cargo'),
      contexto: trabalhadores ? 'Trabalhadores: ' + trabalhadores : ''
    };

    botao.disabled = true;
    botao.textContent = 'Enviando...';
    status.className = 'form-status';
    status.textContent = '';

    function falhou(codigo) {
      botao.disabled = false;
      botao.textContent = rotulo;
      status.className = 'form-status erro';
      status.innerHTML = textoDoErro(codigo) +
        ' Se preferir, peça o kit por <a href="mailto:froid@froid.com.br">froid@froid.com.br</a>' +
        ' ou pelo telefone <a href="tel:+5511945856941">(11) 94585-6941</a>.';
    }

    fetch(form.action, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados)
    }).then(function (resposta) {
      if (!resposta.ok) { falhou(resposta.status); return null; }
      return resposta.json();
    }).then(function (corpo) {
      if (!corpo) return;
      if (!corpo.kit_url) { falhou(0); return; }
      var link = document.createElement('a');
      link.href = corpo.kit_url;
      link.className = 'btn btn-solid';
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = 'Abrir o kit de demonstração (PDF)';
      link.setAttribute('data-umami-event', 'kit-nr1-download');
      var aviso = document.createElement('p');
      aviso.className = 'form-status ok';
      aviso.textContent = corpo.mensagem || 'Pronto.';
      var saida = document.getElementById('kit-nr1-pronto');
      saida.innerHTML = '';
      saida.appendChild(aviso);
      saida.appendChild(link);
      saida.hidden = false;
      form.hidden = true;
      if (window.umami && typeof window.umami.track === 'function') {
        window.umami.track('kit-nr1-cadastro');
      }
    }).catch(function () { falhou(0); });
  });
})();
