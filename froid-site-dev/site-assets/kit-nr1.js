/* Kit de demonstração + proposta NR-1 (nr1/apresentacao-nr1.html, 4 idiomas).
 *
 * Envia o contato a /api/leads/nr1 com origem "kit-demonstracao-nr1". O kit e
 * a proposta saem SÓ por e-mail, em links individuais que expiram
 * (determinação do dono, 23 e 24/11/2026): esta tela não mostra link nenhum,
 * só o que de fato aconteceu com o envio.
 *
 * 24/11/2026: o formulário mora numa janela (<dialog id="dialogo-kit-nr1">), e
 * este script põe, centralizado no fim de cada seção da página, o botão que a
 * abre. O texto do botão e as mensagens vêm do próprio <dialog> (data-*), um
 * por idioma; em pt-BR a mensagem de resultado é a do servidor.
 */
(function () {
  var dialogo = document.getElementById('dialogo-kit-nr1');
  var form = document.getElementById('form-kit-nr1');
  if (!dialogo || !form) return;

  var d = dialogo.dataset;
  var usaMensagemDoServidor = d.idioma === 'pt';

  function abrir() {
    if (typeof dialogo.showModal === 'function') { if (!dialogo.open) dialogo.showModal(); }
    else { dialogo.setAttribute('open', ''); }
    var primeiro = form.querySelector('input');
    if (primeiro && !form.hidden) primeiro.focus();
    if (window.umami && typeof window.umami.track === 'function') window.umami.track('kit-nr1-abrir');
  }

  // Um botão no fim de cada seção de conteúdo (o topo da página fica de fora).
  var secoes = document.querySelectorAll('section.block');
  Array.prototype.forEach.call(secoes, function (secao) {
    var alvo = secao.querySelector(':scope > .container') || secao;
    var p = document.createElement('p');
    p.className = 'kit-gatilho';
    var botao = document.createElement('button');
    botao.type = 'button';
    botao.textContent = d.rotuloBotao;
    botao.addEventListener('click', abrir);
    p.appendChild(botao);
    alvo.appendChild(p);
  });

  dialogo.querySelector('.kit-fechar').addEventListener('click', function () { dialogo.close(); });

  if (location.hash === '#pedir-kit' || location.hash === '#kit-demonstracao') abrir();

  function textoDoErro(codigo, detalhe) {
    if (codigo === 429) return d.msgMuitos;
    if (codigo === 400) return (usaMensagemDoServidor && detalhe) ? detalhe : d.msgCampos;
    return d.msgFalha;
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
    var dados = {
      origem: 'kit-demonstracao-nr1',
      nome: valor('nome'),
      cargo: valor('cargo'),
      email: valor('email'),
      telefone: valor('telefone'),
      empresa: valor('empresa'),
      cnpj: valor('cnpj'),
      estabelecimentos: valor('estabelecimentos'),
      trabalhadores: valor('trabalhadores')
    };

    botao.disabled = true;
    botao.textContent = d.msgEnviando;
    status.className = 'form-status';
    status.textContent = '';

    function falhou(codigo, detalhe) {
      botao.disabled = false;
      botao.textContent = rotulo;
      status.className = 'form-status erro';
      status.textContent = textoDoErro(codigo, detalhe) + ' ' + d.msgContato;
    }

    fetch(form.action, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dados)
    }).then(function (resposta) {
      if (!resposta.ok) {
        return resposta.json().then(function (c) { falhou(resposta.status, c && c.detail); },
                                    function () { falhou(resposta.status); }).then(function () { return null; });
      }
      return resposta.json();
    }).then(function (corpo) {
      if (!corpo) return;
      if (!corpo.mensagem) { falhou(0); return; }
      var aviso = document.createElement('p');
      aviso.className = corpo.email_enviado ? 'form-status ok' : 'form-status erro';
      if (usaMensagemDoServidor) {
        aviso.textContent = corpo.mensagem;
      } else if (corpo.email_enviado) {
        aviso.textContent = (corpo.proposta_calculada ? d.msgOk : d.msgSemProposta).replace('{email}', dados.email);
      } else {
        aviso.textContent = (corpo.equipe_avisada ? d.msgEquipe : d.msgFalha + ' ' + d.msgContato).replace('{email}', dados.email);
      }
      var saida = dialogo.querySelector('[data-papel="pronto"]');
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
