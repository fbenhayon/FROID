/**
 * O que o paciente lê sobre um sinal de dissonância.
 *
 * O texto do profissional continua onde está, intacto e completo — ele tem
 * valor clínico real. Este módulo existe porque o MESMO dado, indo para o
 * paciente, precisa de outra língua.
 *
 * A diferença não é de tamanho, é de natureza. O texto do profissional diz
 * "Sorriso falso / falsa calma" e sugere conduta; isso serve a quem tem
 * formação para contextualizar. Dito a alguém sobre si mesmo, sozinho, num PDF
 * que circula, o mesmo texto vira um veredito sem juiz.
 *
 * Três regras, e nenhuma delas é estética:
 *
 *   1. O título descreve o SINAL MEDIDO, nunca a pessoa. "Elevação do canto da
 *      boca sem elevação da bochecha" é o que a câmera viu. "Sorriso falso" é
 *      uma acusação.
 *   2. Nenhuma conduta. Não há o que o paciente "deva" fazer com isso — quem
 *      conduz é o profissional, e o documento aponta para ele.
 *   3. Até 100 palavras, porque foi o que o Fábio pediu e porque texto longo
 *      sobre o próprio corpo, lido à noite e sem companhia, não ajuda ninguém.
 *
 * Localização: os textos ficam aqui e não no template do relatório, para
 * entrarem no mesmo caminho de tradução das demais strings de produto — o FROID
 * já fala inglês, francês e espanhol.
 */

export type DissonancePatientEntry = {
  /** Título técnico produzido para o profissional. Chave de correspondência. */
  professionalTitle: string;
  /** O que a medição observou, em linguagem de sinal. */
  title: string;
  /** Descrição para o paciente. Nunca prescreve, nunca rotula. */
  description: string;
};

const ENTRIES: DissonancePatientEntry[] = [
  {
    professionalTitle: "Risco de retraumatizacao / flooding autonômico",
    title: "Ativação corporal ampla durante a fala",
    description:
      "Durante alguns momentos, vários sinais do corpo se moveram juntos: uma "
      + "vibração fina na voz, tensão na musculatura da fala e movimentos ao "
      + "redor da boca. É o tipo de reação que o corpo produz quando um assunto "
      + "mobiliza mais do que as palavras mostram. A medição registra que "
      + "aconteceu e quando — o que isso significou para você é conversa para a "
      + "próxima sessão.",
  },
  {
    professionalTitle: "Shutdown psíquico / dissociação",
    title: "Queda sustentada da energia da fala",
    description:
      "Em parte da sessão a energia da sua voz permaneceu abaixo da referência "
      + "medida no início, acompanhada de menor movimentação na parte inferior "
      + "do rosto. É um padrão de recolhimento da expressão, e não uma medida do "
      + "que você sentia. Vale levar essa observação ao seu profissional, que "
      + "conhece o contexto do que estava sendo falado.",
  },
  {
    professionalTitle: "Sorriso falso / falsa calma",
    title: "Sorriso na boca sem o movimento ao redor dos olhos",
    description:
      "A leitura facial registrou o movimento que levanta os cantos da boca "
      + "(AU12) sem o movimento que enruga o canto dos olhos (AU6). São dois "
      + "músculos diferentes: o primeiro é voluntário, o segundo costuma "
      + "acompanhar de forma espontânea. Sorrisos por gentileza, por hábito ou "
      + "por cansaço têm essa mesma assinatura. O registro é apenas do que a "
      + "câmera mediu naquele instante.",
  },
  {
    professionalTitle: "Raiva contida / resposta verbal suprimida",
    title: "Compressão dos lábios com energia vocal elevada",
    description:
      "Houve momentos em que os lábios apareceram pressionados enquanto a voz "
      + "carregava mais energia. É uma combinação que costuma acompanhar algo "
      + "que estava sendo dito com esforço, ou algo que ficou por dizer. A "
      + "medição não sabe o quê — sabe apenas que os dois sinais aconteceram "
      + "juntos, e em que minuto.",
  },
  {
    professionalTitle: "Tristeza mascarada",
    title: "Movimento das sobrancelhas com queda do canto da boca",
    description:
      "A leitura facial registrou elevação da parte interna das sobrancelhas "
      + "junto de queda dos cantos da boca. É uma combinação involuntária, "
      + "difícil de produzir de propósito, e por isso costuma ser notada em "
      + "leitura de expressão. O que ela significou naquele momento da conversa "
      + "é justamente o que vale perguntar ao seu profissional.",
  },
  {
    professionalTitle: "Desprezo unilateral",
    title: "Movimento assimétrico de um lado do rosto",
    description:
      "Um dos lados do rosto se moveu mais do que o outro em alguns instantes. "
      + "Assimetria facial é comum e tem muitas origens — desde o hábito de cada "
      + "pessoa até o lado em que a cabeça estava apoiada. O registro existe "
      + "porque a leitura mede os dois lados separadamente, não porque "
      + "signifique algo por si só.",
  },
  {
    professionalTitle: "Microexpressao contraditoria",
    title: "Movimentos faciais de direções diferentes ao mesmo tempo",
    description:
      "A leitura registrou, no mesmo instante, movimentos faciais que costumam "
      + "aparecer em situações distintas. Isso acontece com frequência na fala "
      + "comum: o rosto raramente exprime uma coisa só. O registro marca o "
      + "momento para que ele possa ser retomado com quem acompanha você.",
  },
  {
    professionalTitle: "Dissonância facial-vocal relevante",
    title: "Diferença entre o que a voz e o rosto expressaram",
    description:
      "Em alguns trechos, a energia da voz e o movimento do rosto seguiram "
      + "direções diferentes em relação à referência medida no início da sessão. "
      + "A leitura registra a diferença; ela não interpreta a causa. Essa "
      + "interpretação depende do que estava sendo falado, e isso quem sabe é "
      + "você com o seu profissional.",
  },
];

const BY_TITLE = new Map(ENTRIES.map((entry) => [entry.professionalTitle, entry]));

/** Limite acordado para o texto que vai ao paciente. */
export const PATIENT_DESCRIPTION_WORD_LIMIT = 100;

export function countWords(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

/**
 * Versão para o paciente de um sinal registrado.
 *
 * Devolve `null` quando o título técnico não tem tradução escrita. Devolver
 * `null` é deliberado: sem tradução, o relatório do paciente OMITE o item. A
 * alternativa — cair no texto do profissional — é exatamente o acidente que
 * este módulo existe para impedir, e ele aconteceria justamente no caso novo
 * que ninguém lembrou de traduzir.
 */
export function patientViewFor(professionalTitle: string): DissonancePatientEntry | null {
  return BY_TITLE.get(String(professionalTitle || "").trim()) || null;
}

export function allPatientViews(): DissonancePatientEntry[] {
  return [...ENTRIES];
}
