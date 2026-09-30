/* FROID Psique V2 — preços vindos do backend, sem nenhum valor embutido.
 *
 * Regra da casa: falha da API NUNCA vira preço zero nem preço antigo. Toda
 * indisponibilidade aparece declarada na tela, no idioma da página. Os
 * números (créditos, totais, unitários, Trial, licença) vêm exclusivamente
 * de /api/psique/v2/pricing e /api/psique/v2/organization-license/quote.
 */
(function () {
  "use strict";

  var i18n = window.PSIQUE_PRECOS_V2_I18N || {};
  var locale = i18n.locale || "pt-BR";
  var raiz = document.getElementById("psique-v2-precos");
  if (!raiz) return;

  function texto(chave, padrao) {
    return Object.prototype.hasOwnProperty.call(i18n, chave) ? i18n[chave] : padrao;
  }

  function brl(cents) {
    return new Intl.NumberFormat(locale, { style: "currency", currency: "BRL" })
      .format(cents / 100);
  }

  function declararIndisponivel(no, motivo) {
    no.innerHTML = "";
    var aviso = document.createElement("div");
    aviso.className = "pv2-indisponivel";
    aviso.setAttribute("data-estado", "indisponivel");
    aviso.textContent = texto("indisponivel",
      "Preços temporariamente indisponíveis. Tente novamente em instantes.");
    if (motivo) aviso.setAttribute("data-motivo", motivo);
    no.appendChild(aviso);
  }

  function cartaoOferta(oferta) {
    var card = document.createElement("div");
    card.className = "card pv2-card";
    card.setAttribute("data-produto", oferta.product_code);
    var nome = document.createElement("h3");
    nome.textContent = oferta.name;
    var creditos = document.createElement("p");
    creditos.className = "pv2-creditos";
    creditos.textContent = oferta.credits + " " + texto("creditos", "créditos de análise");
    var valor = document.createElement("p");
    valor.className = "pv2-valor";
    valor.textContent = brl(oferta.total_cents);
    var unitario = document.createElement("p");
    unitario.className = "pv2-unitario";
    unitario.textContent = texto("unitario", "valor unitário de referência:") +
      " " + new Intl.NumberFormat(locale, { style: "currency", currency: "BRL" })
        .format(Number(oferta.unit_price_display));
    card.appendChild(nome);
    card.appendChild(creditos);
    card.appendChild(valor);
    card.appendChild(unitario);
    return card;
  }

  function preencherTrial(trial) {
    var alvo = document.getElementById("pv2-trial");
    if (!alvo) return;
    alvo.setAttribute("data-estado", "ok");
    alvo.textContent = texto("trial_modelo",
      "{creditos} análises gratuitas ou {dias} dias — o que ocorrer primeiro. Sem cartão.")
      .replace("{creditos}", String(trial.credits))
      .replace("{dias}", String(trial.days));
  }

  function montarCalculadora(limite) {
    var caixa = document.getElementById("pv2-calculadora");
    if (!caixa) return;
    var entrada = caixa.querySelector("input");
    var saida = caixa.querySelector("[data-papel='resultado']");
    var botao = caixa.querySelector("button");

    function consultar() {
      var quantos = parseInt(entrada.value, 10);
      if (!Number.isFinite(quantos) || quantos < 1) {
        saida.setAttribute("data-estado", "invalido");
        saida.textContent = texto("calc_invalido", "Informe quantos profissionais clínicos.");
        return;
      }
      saida.setAttribute("data-estado", "carregando");
      saida.textContent = texto("calc_carregando", "Consultando…");
      fetch("/api/psique/v2/organization-license/quote?clinical_seat_count=" + quantos)
        .then(function (resposta) {
          if (!resposta.ok) throw new Error("HTTP " + resposta.status);
          return resposta.json();
        })
        .then(function (cotacao) {
          if (cotacao.enterprise_required) {
            saida.setAttribute("data-estado", "enterprise");
            saida.textContent = texto("calc_enterprise",
              "Acima de {max} clínicos: proposta Enterprise com a equipe FROID.")
              .replace("{max}", String(limite));
            return;
          }
          saida.setAttribute("data-estado", "ok");
          saida.textContent = texto("calc_resultado", "Licença mensal: {valor}")
            .replace("{valor}", brl(cotacao.monthly_cents));
        })
        .catch(function () {
          saida.setAttribute("data-estado", "indisponivel");
          saida.textContent = texto("indisponivel",
            "Preços temporariamente indisponíveis. Tente novamente em instantes.");
        });
    }

    botao.addEventListener("click", consultar);
    entrada.addEventListener("keydown", function (evento) {
      if (evento.key === "Enter") consultar();
    });
  }

  fetch("/api/psique/v2/pricing")
    .then(function (resposta) {
      if (!resposta.ok) throw new Error("HTTP " + resposta.status);
      return resposta.json();
    })
    .then(function (catalogo) {
      var grade = document.getElementById("pv2-ofertas");
      grade.innerHTML = "";
      grade.setAttribute("data-estado", "ok");
      catalogo.offers.forEach(function (oferta) {
        grade.appendChild(cartaoOferta(oferta));
      });
      preencherTrial(catalogo.trial);
      montarCalculadora(catalogo.organization_license.self_service_max);
      raiz.setAttribute("data-pricing-version", catalogo.pricing_version);
    })
    .catch(function (erro) {
      declararIndisponivel(document.getElementById("pv2-ofertas"), String(erro && erro.message));
      var trial = document.getElementById("pv2-trial");
      if (trial) {
        trial.setAttribute("data-estado", "indisponivel");
        trial.textContent = texto("indisponivel",
          "Preços temporariamente indisponíveis. Tente novamente em instantes.");
      }
      var resultado = document.querySelector("#pv2-calculadora [data-papel='resultado']");
      if (resultado) {
        resultado.setAttribute("data-estado", "indisponivel");
        resultado.textContent = texto("indisponivel",
          "Preços temporariamente indisponíveis. Tente novamente em instantes.");
      }
    });
})();
