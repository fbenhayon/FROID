// FROID site — comportamento das seções "Só para Nerds"

// Seções de cada página, na ordem em que aparecem. O menu suspenso do header é
// construído a partir daqui.
//
// O mapa vive no script, e não no HTML de cada página, por um motivo prático:
// são catorze páginas em pt-BR mais as versões en/fr/es. Repetir o submenu no
// header de cada arquivo significaria manter o mesmo bloco em dezenas de
// lugares — e foi exatamente assim que o header já ficou fora de sincronia
// entre páginas antes.
//
// Cada id aqui existe no HTML. Quem acrescentar uma seção e esquecer de
// registrar perde só o item de menu; quem registrar um id que não existe deixa
// um link que não leva a lugar nenhum — o mesmo defeito que a revisão de links
// encontrou na página de preços. Por isso o construtor abaixo confere a
// existência do alvo antes de criar o item, quando está na própria página.
var NAV_SECOES = {
  "index.html": [
    ["visao-geral", "Visão geral"],
    ["transparencia", "Transparência"],
    ["para-quem-e", "Para quem é"],
    ["o-diferencial", "O diferencial"],
    ["paciente", "Transparência · LGPD"]
  ],
  "ciencia.html": [
    ["evidencia", "Explorador de evidências"],
    ["bibliografia", "Metodologia de verificação"]
  ],
  "tecnologia.html": [
    ["baseline", "Calibração da linha de base"],
    ["extracao-acustica", "Extração acústica"],
    ["facs", "Dinâmica facial (FACS)"],
    ["zonas", "As 12 Zonas de Percepção"],
    ["ipm-idm", "Os índices IPM e IDM"],
    ["estabilizacao", "Estabilização clínica da tela"]
  ],
  "froid-explica.html": [
    ["veja-em-acao", "Veja em ação"],
    ["como-funciona", "Como funciona"],
    ["inteligencia-da-carteira", "Inteligência da carteira"],
    ["prompts", "Biblioteca de prompts"],
    ["personalizacao", "Personalização"],
    ["datamart", "A base que aprende com o mundo"]
  ],
  "etica.html": [
    ["pilar-1-diretrizes-inegociaveis", "Diretrizes inegociáveis"],
    ["pilar-2-fairness-algoritmica", "Fairness algorítmica"],
    ["pilar-3-produto", "Produto"],
    ["pilar-4-conformidade-legal", "Conformidade legal"],
    ["pilar-5-soberania-de-dados", "Soberania de dados"],
    ["kit-de-conformidade", "Kit de conformidade"]
  ],
  "seguranca.html": [
    ["protecao", "Proteção de dados"],
    ["caminho", "O caminho de uma sessão"],
    ["conformidade", "Conformidade"]
  ],
  "profissionais.html": [
    ["sessao", "Na prática"],
    ["financeiro", "Financeiro"],
    ["relatorios", "Relatórios"],
    ["equipe", "Colaboração"],
    ["seguranca-e-responsabilidade", "Segurança e responsabilidade"],
    ["proximo-passo", "Próximo passo"]
  ],
  "empresas.html": [
    ["o-retrato-legal", "O retrato legal"],
    ["os-perigos", "Os perigos"],
    ["o-que-a-fiscalizacao-pede", "O que a fiscalização pede"],
    ["o-custo-da-omissao", "O custo da omissão"],
    ["pratica-juridica", "Prática jurídica"],
    ["solucao", "A solução FROID"],
    ["eficacia", "Provar que a medida funcionou"],
    ["armadilhas", "Armadilhas"],
    ["comparacao", "Comparação"],
    ["limites-e-responsabilidade", "Limites e responsabilidade"],
    ["linha-do-tempo", "Linha do tempo"],
    ["proximo-passo", "Próximo passo"]
  ],
  "como-funciona-nr1.html": [
    ["as-sete-etapas", "As sete etapas"],
    ["o-que-e-igual-em-toda-empresa-e-o-que-muda", "O que muda em cada empresa"],
    ["a-sua-empresa-tem-tamanho-para-isso", "A sua empresa tem tamanho?"]
  ],
  "precos.html": [
    ["planos", "Planos PRO, PLUS e MASTER"],
    ["comparacao", "Comparação de habilidades"],
    ["creditos", "Como funcionam os créditos"],
    ["nr1", "FROID NR-1 para empresas"],
    ["antes-de-decidir", "Antes de decidir"]
  ],
  "diagnostico-nr1.html": [
    ["por-que-existe-um-piso", "Por que existe um piso"],
    ["se-a-sua-empresa-nao-atinge-o-piso", "Se não atinge o piso"]
  ],
  "proposta-nr1.html": [
    ["o-que-esta-sendo-contratado", "O que está sendo contratado"],
    ["fases", "Fases"],
    ["condicoes-comerciais", "Condições comerciais"],
    ["o-que-a-contratante-precisa-fornecer", "O que a contratante fornece"],
    ["por-que-este-procedimento-e-nao-outro", "Por que este procedimento"],
    ["protecao-de-dados", "Proteção de dados"],
    ["limites-do-servico", "Limites do serviço"],
    ["aceite", "Aceite"]
  ],
  "sobre-contato.html": [
    ["quem-faz-o-froid", "Quem faz o FROID"],
    ["governanca-clinica", "Governança clínica"],
    ["fale-com-o-time", "Fale com o time"]
  ],
  "demonstracao.html": [
    ["framework-proprietario-froid", "Framework proprietário"],
    ["indices-em-tempo-real", "Índices em tempo real"],
    ["depois-da-sessao", "Depois da sessão"],
    ["galeria-do-produto", "Galeria do produto"]
  ]
};

document.addEventListener("DOMContentLoaded", function () {
  // Destaca no header o link da página atual (itálico + sublinhado via CSS .ativo)
  var pagina = (location.pathname.split("/").pop() || "index.html").toLowerCase();
  document.querySelectorAll(".nav-links a").forEach(function (a) {
    var href = (a.getAttribute("href") || "").toLowerCase();
    if (href === pagina) a.classList.add("ativo");
  });

  // ---------- Menu suspenso com as seções de cada página ----------
  (function () {
    var nav = document.querySelector(".nav-links");
    if (!nav) return;

    // O mapa descreve as âncoras das páginas pt-BR. Em /en, /fr e /es os links
    // do header têm o mesmo nome de arquivo mas resolvem para a pasta do
    // idioma, onde essas seções ainda não existem — montar o submenu ali
    // produziria links que não levam a lugar nenhum. Quando as traduções
    // ganharem seções, basta um mapa por idioma.
    var idioma = (document.documentElement.getAttribute("lang") || "pt").toLowerCase();
    if (idioma.indexOf("pt") !== 0) return;

    // Só monta com apontador fino. No toque, o primeiro toque abriria o menu em
    // vez de navegar, e a pessoa perderia o link principal — que é justamente
    // o comportamento que irrita em menu suspenso no celular.
    if (!window.matchMedia || !window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;

    Array.prototype.forEach.call(nav.querySelectorAll("a"), function (link) {
      var alvoPagina = (link.getAttribute("href") || "").toLowerCase().split("#")[0];
      var secoes = NAV_SECOES[alvoPagina];
      if (!secoes || !secoes.length) return;

      var naPagina = alvoPagina === pagina;

      var item = document.createElement("span");
      item.className = "nav-item";
      link.parentNode.insertBefore(item, link);
      item.appendChild(link);

      var menu = document.createElement("div");
      menu.className = "nav-drop";
      menu.setAttribute("role", "menu");

      var criados = 0;
      secoes.forEach(function (par) {
        // Na própria página dá para conferir se a âncora existe. Em outra
        // página não dá — mas o mapa é o mesmo, então um id errado aparece
        // aqui assim que alguém abrir a página correspondente.
        if (naPagina && !document.getElementById(par[0])) return;
        var a = document.createElement("a");
        a.setAttribute("href", (naPagina ? "" : alvoPagina) + "#" + par[0]);
        a.setAttribute("role", "menuitem");
        a.textContent = par[1];
        menu.appendChild(a);
        criados++;
      });
      if (!criados) return;

      item.appendChild(menu);
      link.setAttribute("aria-haspopup", "true");
      link.setAttribute("aria-expanded", "false");

      // Teclado: o link continua navegando; a seta para baixo entra no menu.
      link.addEventListener("keydown", function (e) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          item.classList.add("aberto");
          link.setAttribute("aria-expanded", "true");
          var primeiro = menu.querySelector("a");
          if (primeiro) primeiro.focus();
        }
      });
      item.addEventListener("focusout", function () {
        window.setTimeout(function () {
          if (!item.contains(document.activeElement)) {
            item.classList.remove("aberto");
            link.setAttribute("aria-expanded", "false");
          }
        }, 0);
      });
      menu.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
          item.classList.remove("aberto");
          link.setAttribute("aria-expanded", "false");
          link.focus();
        }
      });
    });
  })();

  document.querySelectorAll(".nerds-toggle").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var targetId = btn.getAttribute("data-target");
      var panel = document.getElementById(targetId);
      if (!panel) return;
      var isOpen = panel.classList.contains("open");
      panel.classList.toggle("open", !isOpen);
      btn.setAttribute("aria-expanded", String(!isOpen));
      btn.textContent = isOpen
        ? btn.getAttribute("data-label-closed") || "Só para Nerds"
        : btn.getAttribute("data-label-open") || "Fechar detalhes técnicos";
    });
  });

  // Fecha o painel ao clicar fora dele
  document.addEventListener("click", function (e) {
    document.querySelectorAll(".nerds-panel.open").forEach(function (panel) {
      var wrapper = panel.closest(".nerds-wrapper");
      if (wrapper && !wrapper.contains(e.target)) {
        panel.classList.remove("open");
        var btn = wrapper.querySelector(".nerds-toggle");
        if (btn) {
          btn.setAttribute("aria-expanded", "false");
          btn.textContent = btn.getAttribute("data-label-closed") || "Só para Nerds";
        }
      }
    });
  });

  // ---------- Lightbox: amplia as fotos (.site-img) ao clicar ----------
  (function () {
    var imgs = document.querySelectorAll("img.site-img, .gallery figure img");
    if (!imgs.length) return;

    var closeLabels = { pt: "Fechar", en: "Close", es: "Cerrar", fr: "Fermer" };
    var lang = (document.documentElement.getAttribute("lang") || "pt")
      .slice(0, 2)
      .toLowerCase();
    var closeLabel = closeLabels[lang] || "Fechar";

    var overlay = document.createElement("div");
    overlay.className = "lightbox-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-hidden", "true");
    overlay.innerHTML =
      '<button class="lightbox-close" type="button" aria-label="' +
      closeLabel +
      '">&times;</button>' +
      '<figure class="lightbox-figure">' +
      '<img class="lightbox-img" src="" alt="" />' +
      '<figcaption class="lightbox-caption"></figcaption>' +
      "</figure>";
    document.body.appendChild(overlay);

    var lbImg = overlay.querySelector(".lightbox-img");
    var lbCaption = overlay.querySelector(".lightbox-caption");
    var lastFocus = null;

    function openLightbox(src, alt) {
      lastFocus = document.activeElement;
      lbImg.setAttribute("src", src);
      lbImg.setAttribute("alt", alt || "");
      lbCaption.textContent = alt || "";
      lbCaption.style.display = alt ? "" : "none";
      overlay.classList.add("open");
      overlay.setAttribute("aria-hidden", "false");
      document.body.classList.add("lightbox-lock");
      overlay.querySelector(".lightbox-close").focus();
    }

    function closeLightbox() {
      overlay.classList.remove("open");
      overlay.setAttribute("aria-hidden", "true");
      document.body.classList.remove("lightbox-lock");
      lbImg.setAttribute("src", "");
      if (lastFocus && typeof lastFocus.focus === "function") lastFocus.focus();
    }

    imgs.forEach(function (img) {
      img.classList.add("zoomable");
      img.setAttribute("tabindex", "0");
      img.setAttribute("role", "button");
      img.addEventListener("click", function () {
        openLightbox(img.currentSrc || img.src, img.getAttribute("alt"));
      });
      img.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openLightbox(img.currentSrc || img.src, img.getAttribute("alt"));
        }
      });
    });

    // Clicar em qualquer ponto do overlay (fundo, imagem ou botão) fecha
    overlay.addEventListener("click", closeLightbox);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && overlay.classList.contains("open")) closeLightbox();
    });
  })();
});
