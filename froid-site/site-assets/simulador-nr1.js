/* Calculadora do valor mensal do FROID NR-1.
 *
 * Uma copia so, usada por nr1/precos-nr1.html e psique/index.html. Ate
 * 10/11/2026 este codigo vivia inline em precos-nr1.html; pedir a calculadora
 * tambem na pagina do Psique faria dela a terceira copia da tabela de faixas
 * (a de nr1/index.html ja e outra) - e copia de numero diverge em silencio
 * (skill-froid-master, 2.7).
 *
 * O valor vem do motor de precificacao do servidor
 * (GET /api/nr1/pricing/simulate, froid-server/pricing_nr1.py). A tabela
 * abaixo so e usada em PREVIA LOCAL (arquivo aberto do disco ou servidor de
 * desenvolvimento em localhost), onde nao ha API; nesse caso a procedencia
 * diz "previa local" em vez de apresentar o numero como vindo do motor.
 * tests/test_precos_nr1_espelhados.py confere esta tabela contra o motor.
 *
 * A pagina precisa ter:
 *   #simulador-nr1 [data-sep-mil][data-sep-dec][data-moeda-depois]  (a caixa)
 *   #sim-trabalhadores, #sim-estabelecimentos, #sim-botao,
 *   #sim-resultado, #sim-mensal, #sim-por-trabalhador,
 *   #sim-procedencia, #sim-erro
 * e chamar froidSimularNr1(event) no submit do formulario.
 */
var FROID_NR1_TABELA_PREVIA = {
  code: 'FROID-PRICING-2026-V02',
  version: '1.1',
  validFrom: '2026-11-05',
  sha256: '36164a02ad5d2ece58053efd746c17de755afb4a41402dc85048941cbd0acc19',
  baseEstablishmentCents: 27670,
  tiers: [
    { order: 1, lowerBound: 1, upperBound: 100, workerPriceCents: 2075 },
    { order: 2, lowerBound: 101, upperBound: 300, workerPriceCents: 1729 },
    { order: 3, lowerBound: 301, upperBound: 1000, workerPriceCents: 1487 },
    { order: 4, lowerBound: 1001, upperBound: null, workerPriceCents: 993 }
  ]
};

function froidPreviaLocal() {
  var h = window.location.hostname;
  return window.location.protocol === 'file:' || h === 'localhost' || h === '127.0.0.1';
}

function froidFormatarBRL(centavos, caixa, comCentavos) {
  var mil = caixa.getAttribute('data-sep-mil');
  var dec = caixa.getAttribute('data-sep-dec');
  var depois = caixa.getAttribute('data-moeda-depois') === '1';
  var inteiro = Math.floor(centavos / 100);
  var resto = centavos % 100;
  var corpo = String(inteiro).replace(/\B(?=(\d{3})+(?!\d))/g, mil);
  if (comCentavos) corpo += dec + (resto < 10 ? '0' : '') + resto;
  return depois ? corpo + ' R$' : 'R$ ' + corpo;
}

function froidNr1PricingEndpoint(trabalhadores, estabelecimentos) {
  if (froidPreviaLocal()) {
    return { local: true, corpo: froidSimularNr1Local(trabalhadores, estabelecimentos) };
  }
  return {
    local: false,
    url: '/api/nr1/pricing/simulate?trabalhadores=' + encodeURIComponent(trabalhadores) +
      '&estabelecimentos=' + encodeURIComponent(estabelecimentos)
  };
}

function froidSimularNr1Local(trabalhadores, estabelecimentos) {
  var workers = parseInt(trabalhadores, 10);
  var sites = parseInt(estabelecimentos, 10);
  if (!isFinite(workers) || !isFinite(sites) || workers <= 0 || sites <= 0) {
    throw new Error('Informe trabalhadores e estabelecimentos maiores que zero.');
  }
  var t = FROID_NR1_TABELA_PREVIA;
  var baseSubtotal = sites * t.baseEstablishmentCents;
  var workersSubtotal = 0;
  var memoria = t.tiers.map(function (tier) {
    var superior = tier.upperBound === null ? workers : tier.upperBound;
    var naFaixa = Math.max(0, Math.min(workers, superior) - tier.lowerBound + 1);
    var subtotal = naFaixa * tier.workerPriceCents;
    workersSubtotal += subtotal;
    return {
      order: tier.order,
      workersInTier: naFaixa,
      workerPriceCents: tier.workerPriceCents,
      subtotalCents: subtotal
    };
  });
  var total = baseSubtotal + workersSubtotal;
  return {
    workers: workers,
    establishments: sites,
    baseSubtotalCents: baseSubtotal,
    workersSubtotalCents: workersSubtotal,
    monthlyTotalCents: total,
    perWorkerMonthCents: Math.floor((2 * total + workers) / (2 * workers)),
    tierBreakdown: memoria,
    pricingTable: {
      code: t.code,
      version: t.version,
      validFrom: t.validFrom,
      sha256: t.sha256,
      baseEstablishmentCents: t.baseEstablishmentCents,
      source: 'local-preview'
    }
  };
}

function froidSimularNr1(evento) {
  evento.preventDefault();
  var caixa = document.querySelector('#simulador-nr1 [data-sep-mil]');
  var botao = document.getElementById('sim-botao');
  var resultado = document.getElementById('sim-resultado');
  var procedencia = document.getElementById('sim-procedencia');
  var erro = document.getElementById('sim-erro');
  var trabalhadores = document.getElementById('sim-trabalhadores').value;
  var estabelecimentos = document.getElementById('sim-estabelecimentos').value;
  erro.hidden = true;
  botao.disabled = true;
  var rotulo = botao.textContent;
  botao.textContent = 'Calculando...';
  Promise.resolve()
    .then(function () {
      var consulta = froidNr1PricingEndpoint(trabalhadores, estabelecimentos);
      if (consulta.local) return { ok: true, corpo: consulta.corpo };
      return fetch(consulta.url)
        .then(function (resposta) {
          return resposta.json().then(function (corpo) {
            return { ok: resposta.ok, corpo: corpo };
          });
        });
    })
    .then(function (r) {
      if (!r.ok) throw new Error((r.corpo && r.corpo.detail) || 'Não foi possível simular agora.');
      document.getElementById('sim-mensal').textContent =
        froidFormatarBRL(r.corpo.monthlyTotalCents, caixa, true);
      document.getElementById('sim-por-trabalhador').textContent =
        froidFormatarBRL(r.corpo.perWorkerMonthCents, caixa, true);
      var tabela = r.corpo.pricingTable;
      procedencia.textContent = 'Tabela ' + tabela.code + ' v' + tabela.version +
        ' · SHA-256 ' + tabela.sha256.slice(0, 16) + '...' +
        (tabela.source === 'local-preview'
          ? ' · prévia local, sem consultar o servidor'
          : '');
      procedencia.hidden = false;
      resultado.hidden = false;
    })
    .catch(function (e) {
      resultado.hidden = true;
      procedencia.hidden = true;
      erro.textContent = String(e.message || e) || 'Não foi possível simular agora.';
      erro.hidden = false;
    })
    .finally(function () {
      botao.disabled = false;
      botao.textContent = rotulo;
    });
  return false;
}
