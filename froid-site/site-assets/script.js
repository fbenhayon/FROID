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
    ["data-froid", "Data-Froid"],
    ["o-diferencial", "O diferencial"],
    ["para-quem-e", "Para quem é"],
    ["paciente", "Portal do Paciente"],
    ["transparencia", "Transparência"]
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
    ["sessao", "Antes, durante e depois"],
    ["financeiro", "Controle financeiro"],
    ["relatorios", "Relatórios de pacientes"],
    ["data-froid", "Data-Froid"],
    ["equipe", "Compartilhamento entre profissionais"],
    ["seguranca-e-responsabilidade", "Segurança e responsabilidade"],
    ["proximo-passo", "Próximo passo"]
  ],
  "iso-45003.html": [
    ["indice", "Como a página se organiza"],
    ["o-que-e", "O que a ISO 45003 é"],
    ["lastro", "O critério que decide numa perícia"],
    ["documental", "Dever de conduta × dever documental"],
    ["ja-tem-45001", "Se você já tem ISO 45001"],
    ["limites", "O que não afirmamos"],
    ["proximo", "Próximo passo"]
  ],
  "froid-explica-nr1.html": [
    ["duas-camadas", "As duas camadas"],
    ["temas", "Os oito temas"],
    ["trabalhador", "O que o trabalhador pergunta"],
    ["acervo", "O acervo, e o que é recusado"],
    ["limites", "O que não é"],
    ["proximo-passo", "Próximo passo"]
  ],
  "empresas.html": [
    ["indice", "Como a página se organiza"],
    ["o-retrato-legal", "O que mudou na norma"],
    ["o-que-a-fiscalizacao-pede", "Os três documentos"],
    ["o-custo-da-omissao", "O custo da omissão"],
    ["armadilhas", "Seis erros que geram passivo"],
    ["solucao", "A AEP psicossocial"],
    ["a-plataforma", "A plataforma"],
    ["eficacia", "Provar que a medida funcionou"],
    ["dado-insuficiente", "Quando o dado não basta"],
    ["comparacao", "Gestão tradicional × FROID"],
    ["perguntas-fornecedor", "Cinco perguntas ao fornecedor"],
    ["precos-nr1", "Quanto custa"],
    ["limites-e-responsabilidade", "Limites e responsabilidade"],
    ["proximo-passo", "Comece por uma unidade"]
  ],
  "como-funciona-nr1.html": [
    ["as-sete-etapas", "As sete etapas"],
    ["os-perigos", "A listagem do Guia MTE"],
    ["o-que-e-igual-em-toda-empresa-e-o-que-muda", "O que muda em cada empresa"],
    ["quando-a-segunda-avaliacao-reprova", "E se a segunda avaliação reprovar?"],
    ["a-sua-empresa-tem-tamanho-para-isso", "A sua empresa tem tamanho?"]
  ],
  "precos.html": [
    ["planos", "Planos PRO, PLUS e MASTER"],
    ["comparacao", "Comparação de habilidades"],
    ["creditos", "Como funcionam os créditos"],
    ["nr1", "Precisa cumprir a NR-1?"],
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

    // NÃO PERGUNTE AO NAVEGADOR SE EXISTE MOUSE. Aqui havia uma trava de media
    // query, em duas versões, e as duas desligaram o menu para quem tinha mouse:
    //
    //   (hover: hover) and (pointer: fine)      → descreve só o apontador que o
    //     sistema elegeu como principal. Num notebook com tela sensível ao toque
    //     o Windows elege o toque, e isso dava false com o mouse em uso.
    //   (any-hover: hover) or (any-pointer: fine) → deveria olhar todos os
    //     dispositivos, mas na máquina que reportou o defeito as duas também
    //     vêm false, com mouse e teclado externos ligados. Medido no aparelho.
    //
    // A declaração de capacidade do navegador é, portanto, não confiável nesta
    // classe de máquina. E ela nem é necessária: quem abre a lista é o :hover do
    // CSS, que responde ao movimento real do ponteiro e não ao que as media
    // queries afirmam. O papel deste bloco é só CONSTRUIR o menu — construir a
    // mais não estraga nada, não construir estraga tudo.
    //
    // No toque o link segue navegando: nada aqui chama preventDefault, então o
    // toque no link do header navega como sempre. O que pode acontecer é a lista
    // piscar durante a navegação, porque o toque também aciona o :hover. É
    // cosmético, e é o preço de não excluir quem tem mouse.

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
