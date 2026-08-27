// O conteúdo do FROID Explica NR-1.
//
// Por que é dado no front, e não resposta gerada por modelo:
//
// Este material é consultado NA FRENTE do cliente, no meio de uma reunião em
// que se decide um contrato — e às vezes na frente de um auditor. Nesse
// contexto, "quase sempre responde certo" não é uma propriedade aceitável.
// Resposta gerada depende de indexação, de chave de API, de latência e de o
// modelo não inventar um subitem da norma que não existe. Cada uma dessas
// coisas é um jeito de a tela falhar no pior momento possível.
//
// Aqui a resposta é a mesma sempre, foi revisada uma vez, cita a fonte quando
// há fonte, e funciona sem rede.
//
// A camada generativa continua fazendo sentido para a pergunta que ninguém
// previu, e é o passo seguinte — um endpoint próprio, isolado do acervo
// clínico. Este arquivo é o que sustenta a conversa enquanto isso não existe,
// e continuará sendo a resposta canônica depois que existir: o corpus em
// `froid-server/knowledge/approved/` diz as mesmas coisas, e o teste
// `test_nr1_corpus_do_explica.py` impede que os números divirjam.
//
// REGRA AO EDITAR: número que aparece aqui existe no código do módulo. Ao
// mudar piso, margem ou corte de censo, este arquivo entra na mesma varredura
// que a calculadora pública e o espelho TypeScript.

export type TemaExplica =
  | "lei"
  | "obrigacoes"
  | "porte"
  | "operacao"
  | "resultado"
  | "privacidade"
  | "trabalhador";

export type VerbeteExplica = {
  id: string;
  tema: TemaExplica;
  pergunta: string;
  /** Parágrafos. Texto puro: a tela não interpreta marcação. */
  resposta: string[];
  /** Subitem da norma ou publicação oficial, quando há. */
  referencia?: string;
  /** Termos que não aparecem na pergunta mas que alguém digitaria. */
  chaves?: string[];
};

export const TEMAS: Array<{ id: TemaExplica; titulo: string; resumo: string }> = [
  {
    id: "lei",
    titulo: "A lei",
    resumo: "O que mudou, desde quando vale e o que acontece se não cumprir.",
  },
  {
    id: "obrigacoes",
    titulo: "O que a empresa precisa entregar",
    resumo: "Os documentos, quem assina, de quanto em quanto tempo revisar.",
  },
  {
    id: "porte",
    titulo: "Quantas respostas eu preciso",
    resumo: "Os dois portões, o porte da empresa e por que a filial não publica sozinha.",
  },
  {
    id: "operacao",
    titulo: "Como operar a campanha",
    resumo: "Da estrutura ao inventário, e o que não tem volta.",
  },
  {
    id: "resultado",
    titulo: "Como ler o resultado",
    resumo: "Gradação, faixas, recorte sem avaliação conclusiva e prova de eficácia.",
  },
  {
    id: "privacidade",
    titulo: "Privacidade e a fronteira",
    resumo: "O que o empregador nunca vê, e por que isso é estrutural.",
  },
  {
    id: "trabalhador",
    titulo: "O que o trabalhador pergunta",
    resumo: "As perguntas como elas chegam, com a resposta pronta para repassar.",
  },
];

export const VERBETES: VerbeteExplica[] = [
  // ---------------------------------------------------------------- a lei
  {
    id: "o-que-mudou",
    tema: "lei",
    pergunta: "O que exatamente mudou na NR-1?",
    resposta: [
      "A Portaria MTE nº 1.419/2024 deu nova redação ao capítulo 1.5 da NR-1 e incluiu expressamente os fatores de risco psicossociais no inventário de riscos.",
      "Não é uma obrigação nova e isolada: é a ampliação do escopo de um processo que a empresa já era obrigada a conduzir. Quem já fazia o gerenciamento de riscos passa a ter de tratar também os riscos psicossociais com a mesma formalidade das demais categorias.",
      "A avaliação deve considerar as condições de trabalho nos termos da NR-17, e os fatores psicossociais se ligam diretamente à organização do trabalho.",
    ],
    referencia: "NR-1, capítulo 1.5, na redação da Portaria MTE nº 1.419/2024; subitem 1.5.3.2.1",
    chaves: ["mudança", "novidade", "portaria", "1419"],
  },
  {
    id: "desde-quando",
    tema: "lei",
    pergunta: "Desde quando isso vale?",
    resposta: [
      "Desde 26 de maio de 2026. A vigência estava prevista para 2025 e foi prorrogada pela Portaria MTE nº 765/2025.",
      "O período de dupla visita orientativa já passou. A partir dele o descumprimento comporta auto de infração.",
    ],
    referencia: "Portaria MTE nº 765, de 15/05/2025",
    chaves: ["prazo", "vigência", "quando começa", "26 de maio"],
  },
  {
    id: "multas",
    tema: "lei",
    pergunta: "Qual a multa se a empresa não fizer?",
    resposta: [
      "A omissão na identificação, avaliação e controle dos riscos psicossociais caracteriza descumprimento da NR-1 e da NR-17, e sujeita a organização a auto de infração nos termos do art. 201 da CLT.",
      "Conforme a NR-28, as multas se situam na faixa de R$ 2.396,35 a R$ 6.708,08. Irregularidades graves podem levar a embargo ou interdição.",
      "Há ainda o risco que costuma custar mais caro que a multa: denúncia ou surto de absenteísmo por adoecimento mental aciona o Ministério Público do Trabalho, que pode instaurar inquérito civil, exigir Termo de Ajustamento de Conduta ou ajuizar ação civil pública.",
      "Esta informação é contextual e não constitui parecer jurídico. A análise do caso concreto cabe à assessoria jurídica da organização.",
    ],
    referencia: "NR-28; art. 201 da CLT",
    chaves: ["penalidade", "fiscalização", "autuação", "MPT", "processo"],
  },
  {
    id: "quem-esta-obrigado",
    tema: "lei",
    pergunta: "Toda empresa está obrigada, inclusive a pequena?",
    resposta: [
      "A avaliação dos riscos psicossociais alcança toda organização com empregados.",
      "Microempresas e empresas de pequeno porte de grau de risco 1 e 2 são dispensadas de elaborar o PGR — mas NÃO são dispensadas do gerenciamento de riscos nem da Avaliação Ergonômica Preliminar. Estar dispensado do programa não é estar dispensado da obrigação.",
      "Na prática, para a empresa pequena o caminho é a AEP, que não depende de número mínimo de respondentes.",
    ],
    chaves: ["ME", "EPP", "pequena empresa", "dispensa", "MEI"],
  },
  {
    id: "objeto-da-avaliacao",
    tema: "lei",
    pergunta: "A avaliação é sobre as pessoas ou sobre o trabalho?",
    resposta: [
      "Sobre o trabalho. É o ponto que mais gera erro, e o Guia do MTE é explícito: não se trata de verificar sintomas individuais ou a sensação do que está ocorrendo no trabalhador, nem de medir sinal biológico, mas de verificar as condições de trabalho a que ele está submetido.",
      "Fatores psicossociais da vida pessoal, fora do trabalho, não entram no gerenciamento de riscos da empresa.",
      "Consequência prática: o resultado não classifica pessoas. Ele descreve condições — carga, prazo, autonomia, clareza de papel, apoio, relações, assédio, ambiente.",
    ],
    referencia: "Guia de Fatores de Riscos Psicossociais (MTE, 2025)",
    chaves: ["objeto", "pessoa", "sintoma", "diagnóstico"],
  },

  // -------------------------------------------------------- obrigações
  {
    id: "tres-documentos",
    tema: "obrigacoes",
    pergunta: "Quais documentos a fiscalização vai pedir?",
    resposta: [
      "Três, e o terceiro é o que quase sempre falta.",
      "1. Inventário de riscos, com as nove informações mínimas do subitem 1.5.7.3.2.",
      "2. Plano de ação, com cronograma, responsável, forma de acompanhamento e forma de aferição por medida.",
      "3. Documento de critérios do GRO, que declara como severidade e probabilidade foram graduadas e como os riscos foram classificados. O texto da norma cita dois documentos mínimos; o Manual do MTE relaciona este terceiro como igualmente obrigatório.",
      "O FROID gera os três a partir da campanha encerrada.",
    ],
    referencia: "Subitens 1.5.7.3.2, 1.5.7.1 'b' e 1.5.5.2.2; Manual do MTE (2026)",
    chaves: ["inventário", "plano de ação", "critérios", "auditoria", "documentos"],
  },
  {
    id: "questionario-basta",
    tema: "obrigacoes",
    pergunta: "Aplicar o questionário já cumpre a norma?",
    resposta: [
      "Não, e dizer isso antes que perguntem é o que protege a empresa.",
      "O MTE não indica metodologia e afirma que questionários não comprovam a gestão de riscos de forma isolada. O questionário caracteriza a exposição; a identificação de perigos e a avaliação de riscos acontecem pela AEP — Avaliação Ergonômica Preliminar, prevista na NR-17 —, alimentada também por observação da atividade real e diálogo com os trabalhadores.",
      "O FROID se posiciona exatamente aí: entrega a caracterização da exposição como insumo da AEP, e registra cada evidência com o método declarado. Uma AEP apoiada apenas em questionário aparece sinalizada como tal, em vez de passar despercebida até a fiscalização.",
    ],
    chaves: ["AEP", "suficiente", "só questionário", "metodologia"],
  },
  {
    id: "exame-medico",
    tema: "obrigacoes",
    pergunta: "O exame médico periódico ou a pesquisa de clima já não cobrem isso?",
    resposta: [
      "Não. O MTE respondeu expressamente que a avaliação médica periódica, mesmo sob sigilo, não substitui a identificação de perigos e a avaliação de riscos: são instrumentos distintos.",
      "Pesquisa de clima ou de satisfação também não equivale à AEP. O resultado precisa ser tecnicamente analisado e integrado ao inventário.",
    ],
    referencia: "FAQ NR-1 (CGNOR/DSST/SIT)",
    chaves: ["PCMSO", "clima", "engajamento", "RH", "substitui"],
  },
  {
    id: "quem-assina",
    tema: "obrigacoes",
    pergunta: "Precisa de psicólogo? Quem assina?",
    resposta: [
      "A norma não exige profissão específica nem impõe metodologia. O que ela exige é coerência técnica, e que a escolha seja justificada e documentada.",
      "A responsabilidade pelo gerenciamento de riscos permanece integralmente da organização, que deve conduzi-lo com profissional ou equipe de conhecimento técnico adequado.",
      "O FROID não assume essa responsabilidade e não substitui o SESMT, a CIPA, o médico do trabalho nem a assessoria jurídica.",
    ],
    chaves: ["responsável", "assinatura", "psicólogo", "engenheiro", "SESMT"],
  },
  {
    id: "revisao",
    tema: "obrigacoes",
    pergunta: "De quanto em quanto tempo tem de refazer?",
    resposta: [
      "A revisão é a cada dois anos, ou até três para organizações com sistema de gestão de SST certificado.",
      "Mas há gatilhos que antecipam: implementação de medidas, mudanças nos processos, ineficácia constatada, acidente ou doença, alteração legal e solicitação justificada da CIPA.",
      "Sobre a pergunta recorrente 'qual o prazo da segunda avaliação?': quando o gatilho é a implementação de uma medida, não há prazo em data — o gatilho é o evento. A revisão do risco residual é marcada e antecipa a revisão programada, nunca a adia.",
      "O histórico de atualizações do inventário deve ser mantido por vinte anos.",
    ],
    referencia: "Subitens 1.5.4.4.6 e 1.5.7.3.3.1",
    chaves: ["periodicidade", "prazo", "revisar", "20 anos", "guarda"],
  },
  {
    id: "esocial",
    tema: "obrigacoes",
    pergunta: "Isso tem alguma relação com o eSocial?",
    resposta: [
      "Tem, e por um caminho que costuma ser mal compreendido. A exigência não é gerar eventos do eSocial a partir da avaliação.",
      "A exigência é de coerência: o PGR deve estar integrado aos eventos de SST já enviados (S-2210, S-2220 e S-2240), e a identificação de riscos psicossociais no inventário precisa ser coerente com o que a empresa mandou ao governo — sob pena de autuação por inconsistência de dados.",
    ],
    chaves: ["S-2210", "S-2240", "integração", "governo"],
  },
  {
    id: "participacao",
    tema: "obrigacoes",
    pergunta: "Precisa comprovar que os trabalhadores participaram?",
    resposta: [
      "Sim. Atas da CIPA, listas de presença, consultas formais e a comunicação do inventário e do plano aos trabalhadores. A ausência desses registros pode gerar presunção de omissão patronal.",
      "O aviso de finalidade da campanha — o texto que cada trabalhador lê antes da primeira pergunta — faz parte dessa comunicação e fica gravado junto com a campanha.",
    ],
    referencia: "Subitem 1.5.3.3",
    chaves: ["CIPA", "comunicação", "ata", "participação"],
  },

  // ------------------------------------------------------------- porte
  {
    id: "dois-portoes",
    tema: "porte",
    pergunta: "Por que existe um número mínimo de respostas?",
    resposta: [
      "São dois portões, eles protegem coisas diferentes, e os dois valem sempre.",
      "O portão do anonimato exige 15 respostas substantivas por campanha e 10 por recorte. São números absolutos: não dependem do tamanho da empresa e não se movem. Protegem a pessoa — abaixo desse tamanho, saber a média do grupo já é quase saber o que cada um respondeu.",
      "O portão da representatividade exige que a coorte seja grande o bastante para falar pelo efetivo declarado: amostra para proporção com correção de população finita, a 95% de confiança e margem de 5 pontos. Protege a afirmação — sem ele o relatório descreveria quem respondeu, e não o trabalho da organização.",
      "O segundo é escolha metodológica do FROID, não exigência da norma: o MTE não prescreve metodologia. O primeiro é o que torna a promessa de anonimato verdadeira.",
    ],
    chaves: ["piso", "mínimo", "anonimato", "representatividade", "amostra"],
  },
  {
    id: "quantas-respostas",
    tema: "porte",
    pergunta: "Quantas respostas a minha empresa precisa?",
    resposta: [
      "Depende do efetivo, e a curva achata: dobrar a empresa não dobra a exigência.",
      "28 pessoas exigem 28 (censo). 50 exigem 50 (censo). 100 exigem 80. 250 exigem 152. 500 exigem 218. 1.000 exigem 278. 3.000 exigem 341.",
      "Abaixo de 98 pessoas a amostra exigida alcança o quadro inteiro — ou seja, só publica em censo. De 98 em diante começa a sobrar folga entre quem responde e quem precisa responder.",
      "A tela de campanha calcula esse número no momento em que o efetivo é digitado. Não estime de memória em proposta comercial.",
    ],
    chaves: ["quantos", "amostra", "efetivo", "tamanho", "censo"],
  },
  {
    id: "faixa-pequena",
    tema: "porte",
    pergunta: "Empresa de 15 a 49 pessoas consegue fazer campanha?",
    resposta: [
      "Consegue, mas a redução do piso concede o direito de tentar, não desconto na exigência. Nessa faixa a fórmula pede todo mundo, e uma única recusa suspende aquele resultado.",
      "A conversa honesta é: a campanha vale se a adesão for garantida; a AEP não depende de piso, é obrigatória de todo modo e deve correr em paralelo, para que a empresa não fique sem documento se a coleta não fechar.",
      "Abaixo de 15 pessoas nenhuma campanha publica resultado, por mais adesão que haja. O caminho é a AEP.",
    ],
    chaves: ["pequena", "censo", "15", "49", "adesão"],
  },
  {
    id: "filial-nao-publica",
    tema: "porte",
    pergunta: "Por que minha filial não tem relatório próprio?",
    resposta: [
      "Porque a exigência vale por recorte, e não só para a organização.",
      "Uma rede com 250 pessoas em 11 endereços de cerca de 23 pessoas cada tem uma campanha perfeitamente válida — 152 respostas para o total — e nenhum endereço que publique retrato próprio, porque cada um precisaria de censo.",
      "Isso não produz relatório vazio: cada recorte reprovado entra no mesmo inventário como linha declarada insuficiente, com o portão que falhou e o caminho de remédio.",
      "Prometer 'relatório por filial' numa empresa com esse desenho é a promessa que quebra no fim da coleta. O que se entrega é o retrato da organização mais a declaração honesta do que não pôde ser avaliado por endereço.",
    ],
    chaves: ["filial", "estabelecimento", "unidade", "recorte", "endereço"],
  },
  {
    id: "setor-pequeno",
    tema: "porte",
    pergunta: "Meu setor tem 6 pessoas. Posso juntar com outro?",
    resposta: [
      "Pode, com uma condição que não é formalidade.",
      "Agrupar só é legítimo entre pessoas que fazem trabalho semelhante, sob as mesmas condições e a mesma chefia. A NR-1 avalia condição de trabalho, e uma coorte só significa alguma coisa se as pessoas dentro dela estiverem expostas ao mesmo.",
      "Juntar setores diferentes apenas para alcançar o piso produz uma média que não descreve nenhum dos dois, e faz o risco do grupo menor desaparecer dentro do maior — que é exatamente o oposto do que o agrupamento deveria conseguir.",
      "A tela de cadastro soma os setores pequenos do mesmo endereço e diz se agrupá-los resolveria. Quando nem somados alcançam o piso, ela diz isso também.",
    ],
    chaves: ["setor", "departamento", "juntar", "fundir", "agrupar"],
  },
  {
    id: "resposta-substantiva",
    tema: "porte",
    pergunta: "O que conta como resposta?",
    resposta: [
      "A resposta que cobre ao menos metade das dimensões do instrumento.",
      "Quem abandonou no meio ainda conta; quem tocou em uma pergunta, não. Sem essa regra o piso deixaria de significar 'tantas pessoas avaliaram este trabalho' e passaria a significar 'tantas requisições chegaram'.",
      "Ao dimensionar a distribuição, lembre que a exigência é de respostas substantivas — não de convites enviados nem de questionários iniciados.",
    ],
    chaves: ["substantiva", "parcial", "abandonou", "completa", "válida"],
  },

  // ---------------------------------------------------------- operação
  {
    id: "ordem-dos-atos",
    tema: "operacao",
    pergunta: "Qual é a sequência, do começo ao documento?",
    resposta: [
      "1. Cadastrar a estrutura: estabelecimentos (endereços) e setores. É sobre ela que os recortes são calculados.",
      "2. Criar a campanha, que nasce em rascunho e não coleta nada.",
      "3. Abrir a coleta — segundo ato, deliberado, e é ele que começa a valer a janela.",
      "4. Emitir os convites, um link único por pessoa.",
      "5. Distribuir os links. Quem distribui é a empresa, nunca o FROID.",
      "6. Encerrar a coleta — é o encerramento que torna o resultado legível.",
      "7. Gerar o inventário e, a partir dele, o plano de ação.",
    ],
    chaves: ["passo a passo", "sequência", "como faço", "começar"],
  },
  {
    id: "nao-edita",
    tema: "operacao",
    pergunta: "Dá para corrigir a campanha depois de criada?",
    resposta: [
      "Não. A campanha não tem rota de atualização, e três campos ficam congelados no que foi gravado: o efetivo do período de referência, o aviso de finalidade e a janela de coleta.",
      "Trocar qualquer um deles exige campanha nova. Vale conferir os três antes de criar.",
    ],
    chaves: ["editar", "corrigir", "alterar", "errei"],
  },
  {
    id: "nomes",
    tema: "operacao",
    pergunta: "Quando eu carrego os nomes dos funcionários?",
    resposta: [
      "Nunca. O FROID não recebe nome de trabalhador em momento nenhum — não há campo, não há importação, não existe.",
      "A empresa fornece a matrícula ou código interno. O servidor a transforma em pseudônimo criptográfico e devolve um link por matrícula. O par matrícula–link não é gravado em lugar nenhum do nosso lado: do link guarda-se apenas o resumo criptográfico.",
      "O que pedir ao RH do cliente é a lista de matrícula e setor, não a relação nominal. É um pedido mais fácil de aceitar, porque o RH não entrega dado pessoal a fornecedor nenhum.",
    ],
    chaves: ["nome", "lista", "cadastro", "funcionário", "matrícula", "CPF"],
  },
  {
    id: "atribuir-setor",
    tema: "operacao",
    pergunta: "Como atribuo cada pessoa ao setor ou à filial dela?",
    resposta: [
      "Na lista de convites, escrevendo 'matrícula;setor' — o segundo campo é casado pelo nome ou pelo código interno da unidade, sem diferenciar maiúscula. A lista aceita ponto e vírgula, vírgula ou tabulação, para poder vir colada de planilha.",
      "Sem o segundo campo o convite fica sem setor: a pessoa responde e conta para a campanha, mas não forma recorte próprio.",
      "A atribuição acontece na emissão do convite. Trocar o setor de quem já foi convidado exige campanha nova — reemitir mantém o setor original.",
    ],
    chaves: ["setor", "filial", "unidade", "planilha", "CSV", "importar"],
  },
  {
    id: "distribuir",
    tema: "operacao",
    pergunta: "Como o RH envia os links para os trabalhadores?",
    resposta: [
      "Pelo arquivo 'matrícula;link' que a tela oferece depois da emissão. O RH já sabe quem é cada matrícula.",
      "As formas usuais são mala direta (Word/Outlook ou a ferramenta de e-mail da empresa, com o link como campo de mesclagem), envio individual por mensagem, ou papel — um comprovante por pessoa, útil em operação sem e-mail nominal.",
      "O FROID não dispara e-mail de convite: seria preciso o endereço de cada trabalhador, e é justamente esse dado que o desenho evita pedir.",
      "O que não funciona: publicar um único link no mural, no grupo ou na intranet. O primeiro que responder consome aquele convite e os demais recebem 'convite indisponível'.",
    ],
    chaves: ["enviar", "e-mail", "WhatsApp", "distribuição", "mala direta"],
  },
  {
    id: "apagar-csv",
    tema: "operacao",
    pergunta: "Por que o sistema manda apagar o arquivo de links?",
    resposta: [
      "Porque ele é o único lugar do mundo onde matrícula e link aparecem juntos. Do nosso lado esse par não existe, e é essa ausência que sustenta o anonimato.",
      "O par precisa existir do lado da empresa — sem ele ninguém consegue entregar o convite à pessoa certa. Mas enquanto o arquivo existir, quem o tiver pode abrir cada link e ver qual recusa, descobrindo quem já respondeu. Não o que respondeu: isso ninguém consegue, nem nós.",
      "Não há correção técnica possível para isso. O controle é de guarda: distribuiu, apagou. O arquivo baixa com o aviso no próprio nome.",
    ],
    chaves: ["CSV", "arquivo", "planilha", "segurança", "guardar"],
  },
  {
    id: "perdeu-link",
    tema: "operacao",
    pergunta: "A pessoa perdeu o link. E agora?",
    resposta: [
      "A tela de campanha tem a reemissão: cola-se a matrícula e ela recebe um link novo.",
      "Três coisas a saber. O link anterior morre no instante em que o novo é gravado. Quem já respondeu não recebe link novo — um segundo link faria a mesma pessoa contar duas vezes na coorte. E a resposta não diz por que alguém não foi reemitido: 'sem convite pendente' cobre quem já respondeu e quem nunca foi convidado, e o sistema não afirma qual dos dois.",
      "O setor atribuído na emissão original é mantido.",
    ],
    chaves: ["reemitir", "perdeu", "apagou", "novo link", "reenviar"],
  },
  {
    id: "uso-unico",
    tema: "operacao",
    pergunta: "O link funciona mais de uma vez?",
    resposta: [
      "Não. Respondido, para de funcionar — inclusive em outro aparelho.",
      "Não há amarração a dispositivo: o mesmo link ainda não respondido abre no celular, no computador, onde for. O que não se repete é a resposta.",
      "A mensagem de recusa é deliberadamente igual para token inválido, convite já usado, fora da janela e campanha encerrada. Distinguir os casos permitiria descobrir quem respondeu perguntando ao sistema.",
    ],
    chaves: ["indisponível", "erro", "não abre", "duas vezes", "celular"],
  },
  {
    id: "encerrar",
    tema: "operacao",
    pergunta: "O que acontece ao encerrar a coleta?",
    resposta: [
      "Encerrar não tem volta: não existe rota que devolva uma campanha encerrada ao estado aberto, e os convites pendentes param de funcionar.",
      "Em troca, é o encerramento que libera o resultado. Enquanto a coleta está aberta o painel mostra apenas adesão — e isso é proteção, não limitação: uma coorte que ainda cresce pode ser deduzida uma resposta por vez, observando o agregado antes e depois de cada nova resposta.",
      "Ordem prática: responda tudo o que precisa ser respondido, depois encerre.",
    ],
    chaves: ["fechar", "encerrar", "terminar", "reabrir"],
  },
  {
    id: "excluir",
    tema: "operacao",
    pergunta: "Como excluo uma unidade ou uma campanha?",
    resposta: [
      "Não se exclui. O inventário aponta para a unidade e precisa sobreviver vinte anos — apagar a linha deixaria o documento antigo referenciando algo que não existe mais.",
      "Unidade sai da estrutura por arquivamento, campanha encerra mas permanece no histórico, e o banco recusa a exclusão das linhas que o inventário referencia.",
      "As respostas brutas são outra coisa: a norma exige vinte anos do inventário, não das respostas que o produziram. Há ferramenta própria para purgá-las depois da consolidação.",
    ],
    referencia: "Subitem 1.5.7.3.3.1",
    chaves: ["apagar", "deletar", "arquivar", "remover", "excluir"],
  },

  // --------------------------------------------------------- resultado
  {
    id: "gradacao",
    tema: "resultado",
    pergunta: "De onde vêm a severidade e a probabilidade?",
    resposta: [
      "A norma define os dois eixos de forma contraintuitiva, e errar isso inverte o documento inteiro.",
      "Severidade vem da magnitude da possível lesão ou agravo — havendo várias, vale a maior. Não vem do escore do questionário.",
      "Probabilidade vem das exigências da atividade combinadas com a eficácia das medidas já implementadas. Não vem da prevalência de sintomas.",
      "O escore do questionário caracteriza a exposição e entra como insumo. Ele não é nota da pessoa nem do setor.",
    ],
    referencia: "Subitens 1.5.4.4.4.1 e 1.5.4.4.5.3",
    chaves: ["severidade", "probabilidade", "matriz", "escore", "nota"],
  },
  {
    id: "faixas",
    tema: "resultado",
    pergunta: "Por que a proporção aparece em faixa e não em número exato?",
    resposta: [
      "Porque o painel publica o tamanho exato da coorte. Se publicasse junto a proporção exata, bastaria multiplicar uma pela outra para recuperar a contagem de pessoas: numa coorte de 15, uma proporção de 0,067 é exatamente uma pessoa — e numa empresa desse tamanho isso está a um passo de um nome.",
      "Por isso a proporção sai em faixas de 20 pontos, e a primeira começa em zero de propósito: para conter tanto nenhuma quanto uma pessoa em qualquer coorte a partir do piso.",
      "A gradação continua usando o valor exato, que não sai do banco. Essas faixas não são parametrizáveis pelo cliente: controle de privacidade que o contratante afrouxa não é controle.",
    ],
    chaves: ["faixa", "percentual", "proporção", "exato", "banda"],
  },
  {
    id: "recorte-declarado",
    tema: "resultado",
    pergunta: "O que significa 'recorte sem avaliação conclusiva'?",
    resposta: [
      "É o recorte que não venceu um dos portões. Ele não some do relatório: entra no mesmo inventário como linha declarada insuficiente, dizendo qual portão falhou e qual o remédio.",
      "Reprovado no anonimato, nenhuma adesão resolve e o caminho é a AEP. Reprovado na representatividade, subir a adesão publica o recorte.",
      "Linha declarada insuficiente NÃO é risco baixo. É ausência de avaliação, que é uma terceira coisa — e a obrigação de gerenciar o risco permanece integral.",
      "A razão de declarar em vez de omitir é de leitura: painel vazio é lido como 'não há risco aqui', que é a única conclusão que a ausência de dado nunca autoriza.",
    ],
    chaves: ["insuficiente", "suprimido", "vazio", "declarado", "sem resultado"],
  },
  {
    id: "inventario-sem-dado",
    tema: "resultado",
    pergunta: "Se a coleta não fechar, a empresa fica sem documento?",
    resposta: [
      "Não. O inventário sai mesmo assim, com as linhas declaradas insuficientes dentro do mesmo documento — nunca em anexo.",
      "Foi decisão de produto: a empresa que pagou o ciclo precisa ter o que mostrar a uma fiscalização que continua cobrando dela, e o que ela mostra é honesto.",
      "O que o inventário não faz é sair com a coleta ainda aberta. Ali não é insuficiência de evidência: é resultado que ainda não existe.",
    ],
    chaves: ["não fechou", "adesão baixa", "documento", "entregável"],
  },
  {
    id: "eficacia",
    tema: "resultado",
    pergunta: "Como o FROID prova que a medida funcionou?",
    resposta: [
      "Comparando cada unidade contra a própria linha de base — nunca contra uma média de mercado.",
      "Ao comparar duas campanhas, o sistema calcula a diferença padronizada e também a margem de erro dela, que depende de quantas pessoas responderam. A classificação usa o limite conservador do intervalo, não o valor central: se o intervalo alcança o zero, o veredito é 'sem mudança', ainda que o número central sugira melhora.",
      "Isso é o oposto do que um fornecedor faria para agradar. E é o único jeito de a afirmação 'a medida funcionou' significar alguma coisa diante de uma fiscalização — que é justamente o que a norma passou a exigir ao mandar considerar a eficácia das medidas já implementadas.",
    ],
    referencia: "Subitem 1.5.4.4.5.3",
    chaves: ["eficácia", "melhorou", "comparação", "antes e depois", "prova"],
  },
  {
    id: "plano-de-acao",
    tema: "resultado",
    pergunta: "Como o plano de ação é montado?",
    resposta: [
      "Cada medida entra com cronograma, responsável, forma de acompanhamento e forma de aferição de resultados — os quatro que a norma exige e sem os quais o sistema não deixa concluir.",
      "A prioridade segue o nível de risco e, em seguida, o número de trabalhadores possivelmente atingidos.",
      "Recorte declarado insuficiente não semeia medida no plano: o plano segue a classificação do risco, e ali não houve classificação.",
    ],
    referencia: "Subitens 1.5.5.2.1, 1.5.5.2.1.1 e 1.5.5.2.2",
    chaves: ["plano", "medidas", "cronograma", "prioridade"],
  },
  {
    id: "criterios-proprios",
    tema: "resultado",
    pergunta: "Posso usar a matriz de risco que já uso no meu PGR?",
    resposta: [
      "Pode. Os critérios de gradação são dado por organização, e a escala pode ser reescalada para a matriz que a empresa já usa no resto do programa — 3×3, 4×4, 5×5.",
      "Enquanto isso não é feito, vale o padrão FROID, ancorado na norma e no Guia do MTE. O inventário é válido assim: alinhar à matriz da empresa é refinamento posterior e não pré-requisito.",
      "O objetivo do alinhamento é a coerência que a NR-1 espera entre todos os riscos do programa, e ela pode ser estabelecida depois sem refazer a avaliação.",
    ],
    chaves: ["matriz", "critérios", "escala", "3x3", "5x5", "PGR"],
  },

  // -------------------------------------------------------- privacidade
  {
    id: "empregador-nao-ve",
    tema: "privacidade",
    pergunta: "O empregador consegue ver a resposta de uma pessoa?",
    resposta: [
      "Não, e não é uma questão de configuração de permissão.",
      "As tabelas com as respostas individuais não têm regra de leitura, e o papel com que o sistema funciona não tem permissão sobre elas. A única saída possível do banco é uma função de agregação que já aplica os pisos mínimos de grupo.",
      "Não existe tela, relatório, exportação ou chamada que devolva a resposta de uma pessoa — nem para o empregador, nem para o FROID.",
      "Isso é demonstrável ao vivo: entrando com a conta da empresa e tentando abrir o painel clínico, o sistema recusa.",
    ],
    chaves: ["privacidade", "anonimato", "individual", "ver resposta", "LGPD"],
  },
  {
    id: "base-legal",
    tema: "privacidade",
    pergunta: "Qual a base legal? Precisa de consentimento?",
    resposta: [
      "A base legal é o cumprimento de obrigação legal do empregador — LGPD, art. 7º, II, e art. 11, II, 'a' —, e não o consentimento do trabalhador.",
      "A escolha é deliberada: a relação de hierarquia comprometeria a validade de um consentimento pedido pelo empregador. O trabalhador é informado, e não consultado, sobre o levantamento; responder continua sendo voluntário.",
      "O servidor anexa essa base legal ao aviso de finalidade de toda campanha, para que ela não dependa de alguém lembrar de escrevê-la.",
    ],
    referencia: "LGPD, art. 7º, II e art. 11, II, 'a'",
    chaves: ["LGPD", "consentimento", "base legal", "termo"],
  },
  {
    id: "fronteira-clinica",
    tema: "privacidade",
    pergunta: "E se o trabalhador também for paciente de um profissional da empresa?",
    resposta: [
      "A fronteira vale nos dois sentidos. Em organização do tipo corporativo, os papéis do lado do empregador perdem as permissões clínicas — inclusive a de atribuir a si mesmo um funcionário como paciente, que seria o caminho indireto para ler o prontuário.",
      "O registro da sessão fica sob sigilo do profissional responsável. Para o empregador, só existe o agregado.",
      "Rastreamento clínico individual não é, e não pode ser, o instrumento principal de gestão desses riscos — e o MTE é explícito nisso.",
    ],
    chaves: ["prontuário", "sessão", "clínico", "psicólogo da empresa"],
  },
  {
    id: "voz-e-face",
    tema: "privacidade",
    pergunta: "O FROID captura voz ou face do trabalhador?",
    resposta: [
      "No módulo NR-1, não. A coleta é apenas questionário online.",
      "A capacidade de medir sinal acústico e facial existe no produto clínico do FROID, com paciente identificado e profissional de saúde responsável pela leitura. Ela não é aplicada a trabalhador a pedido do empregador, e essa decisão é de produto, não de configuração.",
    ],
    chaves: ["voz", "face", "biometria", "câmera", "áudio"],
  },

  // ------------------------------------------------------- trabalhador
  {
    id: "chefe-vai-ver",
    tema: "trabalhador",
    pergunta: "\"Meu chefe vai ver o que eu respondi?\"",
    resposta: [
      "Não. As respostas individuais não são acessíveis a ninguém na empresa — e não por política, mas porque o banco de dados não tem caminho de leitura para elas.",
      "O que a empresa recebe são resultados por grupo, e apenas a partir de um tamanho mínimo de grupo.",
    ],
    chaves: ["chefe", "gestor", "medo", "represália"],
  },
  {
    id: "sou-obrigado",
    tema: "trabalhador",
    pergunta: "\"Sou obrigado a responder?\"",
    resposta: [
      "Responder é voluntário. A empresa é que é obrigada a perguntar.",
      "O aviso que abre o questionário diz isso com todas as letras: você está sendo informado, e não consultado. A base legal é a obrigação legal do empregador, não o seu consentimento.",
    ],
    chaves: ["obrigatório", "voluntário", "recusar", "não quero"],
  },
  {
    id: "percebem-que-nao-respondi",
    tema: "trabalhador",
    pergunta: "\"Se eu não responder, alguém percebe?\"",
    resposta: [
      "O sistema mostra à empresa quantas pessoas responderam, nunca quais.",
      "Há uma ressalva honesta: enquanto o RH tiver em mãos o arquivo com o par matrícula–link, ele pode abrir um link e ver se ainda funciona, deduzindo que aquela pessoa já respondeu. É por isso que a orientação ao RH é apagar esse arquivo assim que os convites forem distribuídos — e por isso que essa orientação está escrita na tela e no contrato.",
    ],
    chaves: ["não respondi", "cobrança", "quem faltou"],
  },
  {
    id: "estou-mal",
    tema: "trabalhador",
    pergunta: "\"Estou mal. Isso me ajuda em quê?\"",
    resposta: [
      "O questionário não aciona ninguém, e não aciona de propósito: como a resposta é anônima, ninguém consegue chegar até quem sinalizou sofrimento, e um sistema que tentasse acionar precisaria quebrar o anonimato para funcionar.",
      "A contrapartida é desacoplar: todo questionário termina oferecendo um canal de apoio, igual para todo mundo, independentemente do que foi respondido. Uma campanha não pode nem ser aberta sem canal de apoio configurado — o banco recusa.",
      "Perguntar a alguém como ele está sem ter para onde encaminhá-lo é pior do que não perguntar.",
    ],
    chaves: ["ajuda", "apoio", "sofrimento", "canal", "acolhimento"],
  },
  {
    id: "quanto-tempo",
    tema: "trabalhador",
    pergunta: "\"Quanto tempo leva para responder?\"",
    resposta: [
      "Cerca de sete minutos, 39 perguntas, distribuídas em 13 dimensões — uma para cada perigo da listagem do Guia do MTE de 2025.",
      "Não precisa terminar de uma vez, mas uma resposta só conta para o resultado se cobrir ao menos metade dos temas.",
    ],
    chaves: ["tempo", "quantas perguntas", "duração"],
  },
  {
    id: "meu-setor-nao-aparece",
    tema: "trabalhador",
    pergunta: "\"Por que meu setor não aparece no relatório?\"",
    resposta: [
      "Porque ele é pequeno demais para publicar sem expor quem respondeu. Isso protege o trabalhador, não a empresa.",
      "O setor aparece no documento como 'sem avaliação conclusiva', com o motivo, justamente para que ninguém leia a ausência como 'aqui está tudo bem'.",
    ],
    chaves: ["meu setor", "não aparece", "sumiu"],
  },
];
