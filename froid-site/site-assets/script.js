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
  "ciencia.html": [
    ["tres-camadas-de-leitura", "Três camadas de leitura"],
    ["o-que-o-produto-apresenta", "O que o produto apresenta"],
    ["validacao", "Como comunicar evolução sem antecipar evidência"],
    ["do-entendimento-a-avaliacao-da-sua-pratica", "Do entendimento à avaliação da sua prática"]
  ],
  "como-funciona-clinico.html": [
    ["prepare-uma-captura-autorizada", "1. Prepare uma captura autorizada"],
    ["acompanhe-canais-complementares", "2. Acompanhe canais complementares"],
    ["distingua-candidato-registro-e-historico", "3. Distingua candidato, registro e histórico"],
    ["saiba-quando-nao-ha-medida", "4. Saiba quando não há medida"],
    ["revise-e-contextualize", "5. Revise e contextualize"],
    ["veja-como-isso-se-apresenta", "Veja como isso se apresenta"]
  ],
  "como-funciona-nr1.html": [
    ["defina-unidades-e-responsabilidades", "1. Defina unidades e responsabilidades"],
    ["prepare-finalidade-comunicacao-e-apoio", "2. Prepare finalidade, comunicação e apoio"],
    ["colete-e-reuna-evidencias", "3. Colete e reúna evidências"],
    ["examine-resultados-elegiveis", "4. Examine resultados elegíveis"],
    ["organize-documentacao-e-acao", "5. Organize documentação e ação"],
    ["implemente-e-acompanhe", "6. Implemente e acompanhe"],
    ["reavalie-e-revise", "7. Reavalie e revise"],
    ["as-sete-etapas", "As nove etapas"],
    ["dossie-verificavel", "Comprovação de Gestão Disciplinar"],
    ["o-que-e-igual-em-toda-empresa-e-o-que-muda", "O que é igual em toda empresa, e o que muda"],
    ["quando-a-segunda-avaliacao-reprova", "E se a segunda avaliação reprovar?"],
    ["a-sua-empresa-tem-tamanho-para-isso", "A sua empresa tem tamanho para isso?"],
    ["anonimato-das-respostas", "Por que ninguém consegue saber quem respondeu o quê"],
    ["os-perigos", "A listagem do Guia MTE 2025"],
    ["construa-o-percurso-adequado-a-organizacao", "Construa o percurso adequado à organização"]
  ],
  "data-froid.html": [
    ["o-acervo-e-o-assistente-tem-papeis-diferentes", "O acervo e o assistente têm papéis diferentes"],
    ["tres-responsabilidades-na-arquitetura-proposta", "Três responsabilidades na arquitetura proposta"],
    ["o-que-pode-ser-investigado", "O que pode ser investigado"],
    ["voz-e-rosto-continuam-separados", "Voz e rosto continuam separados"],
    ["pesquisa", "Um caminho para investigar, não uma validação automática"],
    ["privacidade-nao-e-um-rotulo", "Privacidade não é um rótulo"],
    ["perguntas-que-respeitam-os-dados-disponiveis", "Perguntas que respeitam os dados disponíveis"],
    ["avalie-o-data-froid-com-a-equipe", "Avalie o Data-Froid com a equipe"]
  ],
  "demonstracao.html": [
    ["uma-linha-do-tempo-dois-canais", "Uma linha do tempo, dois canais"],
    ["explore-tres-situacoes", "Explore três situações"],
    ["o-que-o-profissional-leva-para-a-revisao", "O que o profissional leva para a revisão"],
    ["cortes-e-calibracao", "Calibração e cortes: os números da sessão"],
    ["o-produto-na-tela", "O aplicativo, na tela"],
    ["quer-conhecer-a-interface-em-uma-apresentacao", "Quer conhecer a interface em uma apresentação?"]
  ],
  "diagnostico-nr1.html": [
    ["checklist-de-preparacao", "Checklist de preparação"],
    ["calculadora", "A sua empresa consegue resultado liberável?"],
    ["por-que-existe-um-piso", "Por que existe um piso"],
    ["participacao-e-privacidade-sao-criterios-distintos", "Participação e privacidade são critérios distintos"],
    ["se-um-recorte-nao-puder-ser-divulgado", "Se um recorte não puder ser divulgado"],
    ["leve-um-escopo-claro-a-primeira-conversa", "Leve um escopo claro à primeira conversa"]
  ],
  "empresas.html": [
    ["nao-basta-uma-fotografia-do-problema", "Não basta uma fotografia do problema"],
    ["processo", "Um processo, responsabilidades claras"],
    ["privacidade", "Condições de trabalho, não vigilância clínica"],
    ["o-que-entra-no-escopo-da-conversa", "O que entra no escopo da conversa"],
    ["comece-com-um-escopo-bem-definido", "Comece com um escopo bem definido"]
  ],
  "etica.html": [
    ["limites", "Informação, não um veredito sobre a pessoa"],
    ["o-que-a-captura-permite-e-o-que-nao-permite", "O que a captura permite"],
    ["autonomia-autorizacoes-e-conferencia", "Autonomia, autorizações e conferência"],
    ["sem-promessas-de-resultado-automatico", "Sem promessas de resultado automático"],
    ["avalie-com-os-limites-a-vista", "Avalie com os limites à vista"]
  ],
  "faq-nr1.html": [
    ["escopo-e-responsabilidade", "Escopo e responsabilidade"],
    ["participacao-e-divulgacao", "Participação e divulgação"],
    ["depois-da-coleta", "Depois da coleta"],
    ["sua-situacao-precisa-de-analise-especifica", "Sua situação precisa de análise específica?"]
  ],
  "faq.html": [
    ["medidas-e-interpretacao", "Medidas e interpretação"],
    ["uso-e-contratacao", "Uso e contratação"],
    ["sua-duvida-depende-da-sua-rotina", "Sua dúvida depende da sua rotina?"]
  ],
  "froid-explica-nr1.html": [
    ["dois-caminhos-de-consulta", "Dois caminhos de consulta"],
    ["exemplos-de-perguntas-uteis", "Exemplos de perguntas úteis"],
    ["privacidade-tambem-na-pergunta", "Privacidade também na pergunta"],
    ["orientacao-com-limites-explicitos", "Orientação com limites explícitos"],
    ["veja-a-aplicacao-no-seu-projeto", "Veja a aplicação no seu projeto"]
  ],
  "froid-explica.html": [
    ["veja-em-acao", "Veja em ação"],
    ["conhecimento-sessao-e-acervo-tres-escopos", "Conhecimento, sessão e acervo: três escopos"],
    ["como-um-bibliotecario-nao-como-um-oraculo", "Como um bibliotecário, não como um oráculo"],
    ["prompts", "Prompts nativos para começar; próprios para aprofundar"],
    ["mais-clareza-sem-transformar-resposta-em-conduta", "Mais clareza, sem transformar resposta em conduta"],
    ["veja-o-assistente-no-contexto-da-sua-pratica", "Veja o assistente no contexto da sua prática"]
  ],
  "glossario-nr1.html": [
    ["os-termos-do-projeto", "Os termos do projeto"],
    ["coloque-os-termos-em-sequencia", "Coloque os termos em sequência"]
  ],
  "glossario.html": [
    ["os-dez-conceitos", "Os dez conceitos"],
    ["veja-os-conceitos-no-contexto-de-uso", "Veja os conceitos no contexto de uso"]
  ],
  "index.html": [
    ["produtos", "Dois produtos. Cada um no seu contexto."],
    ["um-painel-de-apoio-nao-um-piloto-automatico", "Um painel de apoio, não um piloto automático"],
    ["o-diferencial-aparece-no-registro", "O diferencial aparece no registro"],
    ["inteligencia-artificial-que-voce-pode-compreender", "Inteligência artificial que você pode compreender"],
    ["confianca-exige-explicacao", "Confiança exige explicação"],
    ["o-produto-na-tela", "O painel do FROID Psique"],
    ["descubra-onde-o-froid-pode-ajudar", "Descubra onde o FROID pode ajudar"]
  ],
  "iso-45003.html": [
    ["referencia-nao-e-validacao-automatica-do-produto", "Referência não é validação automática do produto"],
    ["o-que-deve-ser-verificado-no-projeto", "O que deve ser verificado no projeto"],
    ["como-o-froid-entra-nessa-organizacao", "Como o FROID entra nessa organização"],
    ["avalie-a-relacao-com-seu-sistema-de-gestao", "Avalie a relação com seu sistema de gestão"]
  ],
  "mapas-faciais.html": [
    ["um-dicionario-de-movimentos-nao-um-leitor-de-pensamentos", "Um dicionário de movimentos, não um leitor de pensamentos"],
    ["familias", "As sete famílias"],
    ["o-detalhe-nao-desaparece-na-organizacao", "O detalhe não desaparece na organização"],
    ["quadros-de-referencia", "Os quadros de referência do FACS"],
    ["limites", "O que não deve ser inferido"],
    ["explore-antes-de-decidir", "Explore antes de decidir"]
  ],
  "menu.html": [
    ["as-paginas-por-produto", "As páginas, por produto"]
  ],
  "precos.html": [
    ["qual-e-o-seu-cenario", "Qual é o seu cenário?"],
    ["trial", "Teste gratuito, sem cartão"],
    ["como-funcionam-os-creditos", "Como funcionam os créditos"],
    ["pacotes", "Pacotes de créditos de análise"],
    ["o-que-a-licenca-organiza", "O que a licença organiza"],
    ["licenca", "Licença mensal por profissional clínico"],
    ["e-quando-o-saldo-termina", "E quando o saldo termina?"],
    ["receba-uma-proposta-para-sua-pratica", "Receba uma proposta para sua prática"]
  ],
  "privacidade.html": [
    ["psique", "FROID Psique"],
    ["nr1", "FROID NR-1"],
    ["duvidas-ou-solicitacoes-sobre-dados", "Dúvidas ou solicitações sobre dados"]
  ],
  "profissionais.html": [
    ["antes-durante-e-depois", "Antes, durante e depois"],
    ["relatorio-da-sessao", "O relatório da sessão"],
    ["instrumentos-que-informam-sem-decidir-por-voce", "Instrumentos que informam, sem decidir por você"],
    ["uma-pergunta-melhor-comeca-por-um-contexto-claro", "Uma pergunta melhor começa por um contexto claro"],
    ["data-froid-da-informacao-registrada-a-investigacao", "Data-Froid: da informação registrada à investigação"],
    ["contratacao-adequada-a-sua-pratica", "Contratação adequada à sua prática"],
    ["comece-avaliando-o-encaixe-na-sua-rotina", "Comece avaliando o encaixe na sua rotina"]
  ],
  "proposta-nr1.html": [
    ["o-que-definir-antes-do-valor", "O que definir antes do valor"],
    ["o-que-esta-sendo-contratado", "O que está sendo contratado"],
    ["fases", "Fases"],
    ["etapas-que-a-proposta-pode-contemplar", "Etapas que a proposta pode contemplar"],
    ["precos", "Condições comerciais"],
    ["o-que-a-contratante-precisa-fornecer", "O que a contratante precisa fornecer"],
    ["por-que-este-procedimento-e-nao-outro", "Por que este procedimento, e não outro"],
    ["protecao-de-dados", "Proteção de dados"],
    ["limites-do-servico", "Limites do serviço"],
    ["o-contrato-e-a-referencia", "O contrato é a referência"],
    ["aceite", "Aceite"],
    ["comece-com-as-informacoes-essenciais", "Comece com as informações essenciais"]
  ],
  "seguranca-nr1.html": [
    ["resultado-agregado-nao-prontuario-individual", "Resultado agregado, não prontuário individual"],
    ["criterios-antes-da-divulgacao", "Critérios antes da divulgação"],
    ["comunicacao-ao-trabalhador", "Comunicação ao trabalhador"],
    ["governanca-e-documentos", "Governança e documentos"],
    ["revise-privacidade-antes-de-abrir-a-coleta", "Revise privacidade antes de abrir a coleta"]
  ],
  "seguranca.html": [
    ["analise-facial-e-videochamada-sao-percursos-diferentes", "Análise facial e videochamada são percursos diferentes"],
    ["audio-e-transcricao", "Áudio e transcrição"],
    ["protecao-e-permissoes", "Proteção e permissões"],
    ["analise-agregada", "Governança da análise agregada"],
    ["direitos-contratos-e-transparencia", "Direitos, contratos e transparência"],
    ["precisa-avaliar-a-arquitetura-antes-de-contratar", "Precisa avaliar a arquitetura antes de contratar?"]
  ],
  "sobre-contato.html": [
    ["escolha-o-assunto", "Escolha o assunto"],
    ["canal-de-contato", "Canal de contato"]
  ],
  "tecnologia.html": [
    ["voz", "Voz: uma referência para a própria sessão"],
    ["ipm-idm", "IPM e IDM: magnitude e direção"],
    ["face", "Face: do coeficiente ao padrão"],
    ["registro", "Consistência que chega à tela e ao relatório"],
    ["arquitetura-com-responsabilidades-distintas", "Arquitetura com responsabilidades distintas"],
    ["na-tela", "As medidas, na tela"],
    ["leve-o-entendimento-para-a-pratica", "Leve o entendimento para a prática"]
  ],
  "termos.html": [
    ["psique", "FROID Psique"],
    ["nr1", "FROID NR-1"],
    ["precisa-esclarecer-o-escopo-antes-de-contratar", "Precisa esclarecer o escopo antes de contratar?"]
  ]
};

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
      // Links que já vivem dentro de um menu de família (o rótulo e os filhos
      // dele) não ganham submenu de seções: seria menu suspenso dentro de menu
      // suspenso, e o de dentro abriria fora da tela. O submenu de seções fica
      // com os links soltos da fileira — Ética, Segurança e Preços.
      if (link.closest && link.closest(".nav-menu")) return;

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
