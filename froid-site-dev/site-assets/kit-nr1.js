/* Formulário do kit de demonstração NR-1 (nr1/apresentacao-nr1.html).
 *
 * Envia o contato a /api/leads/nr1 com origem "kit-demonstracao-nr1". O kit
 * sai SÓ por e-mail, num link individual que expira (determinação do dono,
 * 23/11/2026): esta tela não mostra link nenhum, só a mensagem do servidor
 * dizendo o que de fato aconteceu com o envio.
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
      if (!corpo.mensagem) { falhou(0); return; }
      var aviso = document.createElement('p');
      aviso.className = corpo.email_enviado ? 'form-status ok' : 'form-status erro';
      aviso.textContent = corpo.mensagem;
      var saida = document.getElementById('kit-nr1-pronto');
      saida.innerHTML = '';
      saida.appendChild(aviso);
      saida.hidden = false;
      form.hidden = true;
      if (window.umami && typeof window.umami.track === 'function') {
        window.umami.track(corpo.email_enviado ? 'kit-nr1-cadastro' : 'kit-nr1-cadastro-sem-email');
      }
    }).catch(function () { falhou(0); });
  });
})();
