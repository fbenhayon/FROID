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
//
// Desde 09/11/2026 o site tem pastas por produto (psique/, nr1/), e a chave é
// o caminho a partir da raiz do site ("psique/ciencia.html"), não só o nome do
// arquivo: "index.html" sozinho já não diz de qual produto é a página.
var NAV_SECOES = {
  "psique/ciencia.html": [
    ["tres-camadas-de-leitura", "Três camadas de leitura"],
    ["o-que-o-produto-apresenta", "O que o produto apresenta"],
    ["validacao", "Como comunicar evolução sem antecipar evidência"]
  ],
  "psique/como-funciona-clinico.html": [
    ["prepare-uma-captura-autorizada", "1. Prepare uma captura autorizada"],
    ["faca-um-convite-ao-seu-paciente", "1. Faça um convite ao seu paciente"],
    ["cortes-e-calibracao", "2. Calibração e cortes"],
    ["acompanhe-canais-complementares", "3. Acompanhe canais complementares"],
    ["distingua-candidato-registro-e-historico", "3. Distingua candidato, registro e histórico"],
    ["saiba-quando-nao-ha-medida", "4. Saiba quando não há medida"],
    ["revise-e-contextualize", "5. Revise e contextualize"],
    ["revise-a-sessao", "4. Revise a sessão"],
    ["veja-como-isso-se-apresenta", "Veja como isso se apresenta"]
  ],
  "psique/data-froid.html": [
    ["o-acervo-e-o-assistente-tem-papeis-diferentes", "O acervo e o assistente têm papéis diferentes"],
    ["tres-responsabilidades-na-arquitetura-proposta", "Três responsabilidades na arquitetura proposta"],
    ["o-que-pode-ser-investigado", "O que pode ser investigado"],
    ["voz-e-rosto-continuam-separados", "Voz e rosto continuam separados"],
    ["pesquisa", "Um caminho para investigar, não uma validação automática"],
    ["privacidade-nao-e-um-rotulo", "Privacidade não é um rótulo"],
    ["perguntas-que-respeitam-os-dados-disponiveis", "Perguntas que respeitam os dados disponíveis"]
  ],
  "nr1/index.html": [
    ["custo-da-omissao", "O custo da omissão"],
    ["armadilhas", "Armadilhas"],
    ["tres-linhas-metodo", "As 3 linhas que resumem o método"],
    ["lista-de-preparacao", "Lista de informações"],
    ["como-comparar", "Como comparar"],
    ["precos-nr1", "Preços"],
    ["simulador-nr1", "Simulação"],
    ["limites-e-responsabilidade", "Limites e responsabilidade"]
  ],
  "nr1/contratacao-nr1.html": [
    ["sumario-executivo", "Sumário executivo"],
    ["norma", "A NR-1 em vigor"],
    ["cadeia", "A oportunidade oculta"],
    ["linha-de-raciocinio", "Linha de raciocínio"],
    ["padroes", "Padrões"],
    ["indicadores", "Indicadores"],
    ["campanhas-segmentadas", "Campanhas segmentadas"],
    ["anonimato", "Anonimato"],
    ["pgr-e-psique", "PGR e Psique"],
    ["recomendacoes", "Recomendações"]
  ],
  "psique/faq.html": [
    ["medidas-e-interpretacao", "Medidas e interpretação"],
    ["uso-e-contratacao", "Uso e contratação"]
  ],
  "psique/froid-explica.html": [
    ["veja-em-acao", "Veja em ação"],
    ["como-um-bibliotecario-nao-como-um-oraculo", "Como um bibliotecário, não como um oráculo"],
    ["prompts", "Prompts nativos para começar; próprios para aprofundar"],
    ["mais-clareza-sem-transformar-resposta-em-conduta", "Mais clareza, sem transformar resposta em conduta"]
  ],
  "psique/glossario.html": [
    ["os-dez-conceitos", "Os dez conceitos"]
  ],
  "nr1/iso-45001.html": [
    ["obrigacao-legal-e-diretriz", "Obrigação legal e diretriz"],
    ["siglas-e-publicacoes", "Siglas e publicações"],
    ["como-se-conectam", "Como se conectam"],
    ["taxonomia-psicossocial", "Taxonomia psicossocial"],
    ["governanca-e-prazos", "Governança e prazos"],
    ["o-que-o-froid-entrega", "O que o FROID entrega"],
    ["limites", "Limites"]
  ],
  "nr1/apresentacao-nr1.html": [
    ["documento-integral", "Gestão dos riscos psicossociais"],
    ["pagina-1", "O que a empresa precisa demonstrar"],
    ["pagina-2", "O que o FROID entrega"],
    ["pagina-3", "O FROID não substitui prestadores"],
    ["pagina-4", "Proteção e evidência"],
    ["quando-a-segunda-avaliacao-reprova", "E se a segunda avaliação reprovar?"],
    ["pagina-5", "Minha proposta: experimentem"]
  ],
  "psique/mapas-faciais.html": [
    ["um-dicionario-de-movimentos-nao-um-leitor-de-pensamentos", "Um dicionário de movimentos, não um leitor de pensamentos"],
    ["familias", "As sete famílias"],
    ["o-detalhe-nao-desaparece-na-organizacao", "O detalhe não desaparece na organização"],
    ["quadros-de-referencia", "Os quadros de referência do FACS"],
    ["limites", "O que não deve ser inferido"]
  ],
  "menu.html": [
    ["as-paginas-por-produto", "As páginas, por produto"]
  ],
  "psique/precos-psique.html": [
    ["qual-e-o-seu-cenario", "Qual é o seu cenário?"],
    ["trial", "Teste gratuito, sem cartão"],
    ["como-funcionam-os-creditos", "Como funcionam os créditos"],
    ["pacotes", "Pacotes de créditos de análise"],
    ["o-que-a-licenca-organiza", "O que a licença organiza"],
    ["licenca", "Licença mensal por profissional clínico"],
    ["e-quando-o-saldo-termina", "E quando o saldo termina?"]
  ],
  "nr1/precos-nr1.html": [
    ["condicoes-comerciais", "Condições comerciais"],
    ["simulador-nr1", "Simulação"],
    ["exemplos", "Exemplos"]
  ],
  "privacidade.html": [
    ["psique", "FROID Psique"],
    ["nr1", "FROID NR-1"],
    ["duvidas-ou-solicitacoes-sobre-dados", "Dúvidas ou solicitações sobre dados"]
  ],
  "psique/index.html": [
    ["antes-durante-e-depois", "Antes, durante e depois"],
    ["relatorio-da-sessao", "O relatório da sessão"],
    ["instrumentos-que-informam-sem-decidir-por-voce", "Instrumentos que informam, sem decidir por você"],
    ["ipm-idm", "IPM e IDM: magnitude e direção"],
    ["uma-pergunta-melhor-comeca-por-um-contexto-claro", "Uma pergunta melhor começa por um contexto claro"],
    ["data-froid-da-informacao-registrada-a-investigacao", "Data-Froid: da informação registrada à investigação"],
    ["contratacao-adequada-a-sua-pratica", "Contratação adequada à sua prática"],
    ["comece-avaliando-o-encaixe-na-sua-rotina", "Comece avaliando o encaixe na sua rotina"],
    ["multimodal", "Processamento multimodal"],
    ["habilidades", "As 10 habilidades"],
    ["calibracao-60s", "Calibração de 60 segundos"],
    ["bussola-velocimetro", "IDM e IPM"],
    ["12-zonas", "As 12 zonas de percepção vocal"],
    ["ritmo-fala", "Taxa de elocução"],
    ["cortes-tematicos", "Cortes temáticos e FROID Explica"],
    ["privacidade-lgpd", "Data-Froid e privacidade"],
    ["calculadora-psique", "Calculadora para profissionais e clínicas"],
    ["resgate-bonificacao", "Bonificação de lançamento"]
  ],
  "nr1/proposta-nr1.html": [
    ["precos", "Condições comerciais"],
    ["lista-de-preparacao", "Lista de informações"],
    ["resultados-liberaveis", "Resultados liberáveis"],
    ["o-que-a-contratante-precisa-fornecer", "O que a contratante precisa fornecer"],
    ["por-que-este-procedimento-e-nao-outro", "Por que este procedimento, e não outro"],
    ["protecao-de-dados", "Proteção de dados"],
    ["limites-do-servico", "Limites do serviço"]
  ],
  "sobre-contato.html": [
    ["canal-de-contato", "Canal de contato"]
  ],
  "psique/tecnologia.html": [
    ["voz", "Voz: uma referência para a própria sessão"],
    ["face", "Face: do coeficiente ao padrão"],
    ["registro", "Consistência que chega à tela e ao relatório"],
    ["arquitetura-com-responsabilidades-distintas", "Arquitetura com responsabilidades distintas"],
    ["na-tela", "As medidas, na tela"]
  ]
};

// Raiz do site = a pasta acima de site-assets/, tirada do próprio src deste
// script. Funciona igual em froid.com.br, no Live Server e em file://, e em
// qualquer profundidade de pasta.
var RAIZ_DO_SITE = (function () {
  var s = document.currentScript ||
    document.querySelector('script[src*="site-assets/script.js"]');
  return s ? new URL("../", s.src).href : new URL("./", location.href).href;
})();

// "psique/ciencia.html" para qualquer URL do site; null se for de fora.
function chaveDaPagina(url) {
  var u = new URL(url, location.href);
  var p = u.href.split("#")[0].split("?")[0];
  if (p.indexOf(RAIZ_DO_SITE) !== 0) return null;
  p = p.slice(RAIZ_DO_SITE.length);
  if (p === "" || p.charAt(p.length - 1) === "/") p += "index.html";
  return decodeURIComponent(p).toLowerCase();
}

/* Teclado dos menus do header, um só para os dois tipos (o submenu de seções,
   montado aqui, e os menus de família, escritos no HTML). O ponteiro e o foco
   já abrem pelo CSS; isto acrescenta seta para baixo, Escape e o par
   aria-haspopup/aria-expanded. O link do rótulo NUNCA deixa de navegar: nada
   chama preventDefault fora da seta. */
function ligarTeclado(item, link, menu) {
  link.setAttribute("aria-haspopup", "true");
  link.setAttribute("aria-expanded", "false");

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
}

document.addEventListener("DOMContentLoaded", function () {
  // Destaca no header o link da página atual (itálico + sublinhado via CSS .ativo)
  // A comparação é pelo caminho resolvido, não pelo texto do href: o mesmo
  // destino se escreve "index.html" numa pasta e "../psique/index.html" noutra.
  var pagina = chaveDaPagina(location.href);
  document.querySelectorAll(".nav-links a").forEach(function (a) {
    var href = a.getAttribute("href") || "";
    if (href.indexOf("#") !== -1) return;
    if (pagina && chaveDaPagina(a.href) === pagina) a.classList.add("ativo");
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
      // Links que já vivem dentro de um menu de família (o rótulo e os filhos
      // dele) não ganham submenu de seções: seria menu suspenso dentro de menu
      // suspenso, e o de dentro abriria fora da tela. O submenu de seções fica
      // com os links soltos da fileira — Ética, Segurança e Preços.
      if (link.closest && link.closest(".nav-menu")) return;

      var hrefLink = (link.getAttribute("href") || "").split("#")[0];
      if (!hrefLink) return;
      var alvoPagina = chaveDaPagina(link.href);
      var secoes = alvoPagina && NAV_SECOES[alvoPagina];
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
        a.setAttribute("href", (naPagina ? "" : hrefLink) + "#" + par[0]);
        a.setAttribute("role", "menuitem");
        a.textContent = par[1];
        menu.appendChild(a);
        criados++;
      });
      if (!criados) return;

      item.appendChild(menu);
      ligarTeclado(item, link, menu);
    });
  })();

  // ---------- Menus de família do header (escritos no HTML) ----------
  // Os filhos de cada produto e o grupo Ciência e Tecnologia já vêm no HTML
  // dentro de um .nav-menu; o CSS abre no ponteiro e no foco. Aqui só se liga o
  // teclado, com o mesmo comportamento do submenu de seções — uma função só,
  // para os dois não divergirem.
  document.querySelectorAll(".nav-menu").forEach(function (item) {
    var link = item.querySelector(".nav-familia-rotulo");
    var menu = item.querySelector(".nav-drop");
    if (link && menu) ligarTeclado(item, link, menu);
  });

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

// ---------- Diamante no topo da pagina (celular) ----------
// Opcao (c) aprovada pelo dono em 09/11/2026. O CSS (refinement.css)
// centraliza o texto e alarga as linhas de cima para baixo ate o titulo; aqui
// a frase de abertura volta a estreitar ate o fim, fechando o losango. Duas
// bordas invisiveis em triangulo (shape-outside) empurram o texto; a altura
// delas vem do proprio paragrafo, entao e medida — e remedida quando a tela
// muda. Fora do celular as bordas sao removidas.
(function () {
  var celular = window.matchMedia ? window.matchMedia("(max-width: 860px)") : null;

  function limpar(p) {
    Array.prototype.slice.call(p.querySelectorAll(".diamante-borda")).forEach(function (e) {
      e.parentNode.removeChild(e);
    });
  }

  function aplicar() {
    // Site II (11/11/2026, pedido do dono): a abertura do Psique em diamante
    // em qualquer largura. Site 1: so no celular, como aprovado em 09/11/2026.
    var sempre = document.querySelector(".hero-banner .hero-lead");
    var p = sempre || document.querySelector(".hero .lead, .hero-neuro__content .lead");
    if (!p) return;
    limpar(p);
    if (!sempre && (!celular || !celular.matches)) return;
    var largura = p.clientWidth;
    if (!largura) return;
    var borda = Math.round(largura * 0.3);
    var esq = document.createElement("span");
    var dir = document.createElement("span");
    esq.className = "diamante-borda esq";
    dir.className = "diamante-borda dir";
    esq.setAttribute("aria-hidden", "true");
    dir.setAttribute("aria-hidden", "true");
    esq.style.width = dir.style.width = borda + "px";
    esq.style.shapeOutside = "polygon(0 0, 0 100%, 100% 100%)";
    dir.style.shapeOutside = "polygon(100% 0, 0 100%, 100% 100%)";
    p.insertBefore(dir, p.firstChild);
    p.insertBefore(esq, p.firstChild);
    var altura = p.offsetHeight;
    for (var i = 0; i < 4; i++) {
      esq.style.height = dir.style.height = altura + "px";
      var nova = p.offsetHeight;
      if (Math.abs(nova - altura) < 2) break;
      altura = nova;
    }
  }

  var espera = null;
  function agendar() {
    if (espera) clearTimeout(espera);
    espera = setTimeout(aplicar, 120);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", aplicar);
  else aplicar();
  window.addEventListener("load", aplicar);
  window.addEventListener("resize", agendar);
})();
