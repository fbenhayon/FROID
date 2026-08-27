/**
 * As siglas do universo da NR-1, por extenso.
 *
 * O módulo corporativo carrega mais sigla por parágrafo que qualquer outra
 * parte do FROID, e a plateia dele não é a mesma do produto clínico: quem abre
 * essas telas é RH, jurídico ou diretoria, e AEP, GRO e PGR não fazem parte do
 * vocabulário deles. Uma tela que diz "gerar a AEP" para quem nunca viu a sigla
 * transfere ao leitor o trabalho de descobrir do que se trata — e, numa
 * apresentação comercial, quem não entende não pergunta: conclui que o produto
 * não é para ele.
 *
 * Duas formas de usar, e a escolha não é estética:
 *
 *   `<Sigla nome="AEP" />` — mostra AEP e, ao passar o mouse ou tocar, revela
 *   o significado. Para uso repetido no meio de um texto já denso.
 *
 *   `porExtenso("AEP")` — devolve "Avaliação Ergonômica Preliminar (AEP)".
 *   Para a PRIMEIRA aparição numa tela, num título ou num documento que será
 *   impresso, onde não existe mouse para passar por cima.
 */

export const SIGLAS: Record<string, { nome: string; nota?: string }> = {
  "NR-1": {
    nome: "Norma Regulamentadora nº 1",
    nota: "Disposições gerais e gerenciamento de riscos ocupacionais.",
  },
  "NR-17": {
    nome: "Norma Regulamentadora nº 17",
    nota: "Ergonomia. É dela que vêm os métodos AEP e AET.",
  },
  "NR-28": {
    nome: "Norma Regulamentadora nº 28",
    nota: "Fiscalização e penalidades.",
  },
  AEP: {
    nome: "Avaliação Ergonômica Preliminar",
    nota:
      "Método da NR-17 pelo qual a identificação de perigos e a avaliação de " +
      "riscos psicossociais efetivamente acontecem. Obrigatória para toda " +
      "organização com empregados, inclusive as dispensadas do PGR.",
  },
  AET: {
    nome: "Análise Ergonômica do Trabalho",
    nota:
      "Análise aprofundada, exigida quando a AEP não basta — item 17.3.2 da NR-17.",
  },
  GRO: {
    nome: "Gerenciamento de Riscos Ocupacionais",
    nota:
      "O processo contínuo de identificar perigos, avaliar riscos e controlá-los. " +
      "A responsabilidade por ele é sempre da organização.",
  },
  PGR: {
    nome: "Programa de Gerenciamento de Riscos",
    nota:
      "A documentação formal do GRO. Tem dois documentos mínimos: o inventário " +
      "de riscos e o plano de ação.",
  },
  CIPA: {
    nome: "Comissão Interna de Prevenção de Acidentes e de Assédio",
  },
  SESMT: {
    nome:
      "Serviço Especializado em Engenharia de Segurança e em Medicina do Trabalho",
  },
  PCMSO: {
    nome: "Programa de Controle Médico de Saúde Ocupacional",
    nota: "Norma Regulamentadora nº 7. Cuida da saúde da pessoa; o GRO cuida do trabalho.",
  },
  LGPD: {
    nome: "Lei Geral de Proteção de Dados",
    nota: "Lei nº 13.709/2018.",
  },
  DPO: {
    nome: "encarregado pelo tratamento de dados pessoais",
    nota: "Do inglês data protection officer.",
  },
  MTE: { nome: "Ministério do Trabalho e Emprego" },
  CAT: { nome: "Comunicação de Acidente de Trabalho" },
  DORT: { nome: "Distúrbios Osteomusculares Relacionados ao Trabalho" },
  EPI: {
    nome: "Equipamento de Proteção Individual",
    nota:
      "Último degrau da hierarquia de medidas. Não se aplica a risco " +
      "psicossocial: não existe EPI contra a forma como o trabalho é organizado.",
  },
  TCLE: { nome: "Termo de Consentimento Livre e Esclarecido" },
  CNPJ: { nome: "Cadastro Nacional da Pessoa Jurídica" },
  CPF: { nome: "Cadastro de Pessoas Físicas" },
  ME: { nome: "Microempresa" },
  EPP: { nome: "Empresa de Pequeno Porte" },
  MEI: { nome: "Microempreendedor Individual" },
  eSocial: {
    nome: "Sistema de Escrituração Digital das Obrigações Fiscais, Previdenciárias e Trabalhistas",
  },
  SST: { nome: "Segurança e Saúde no Trabalho" },
  ISO: {
    nome: "Organização Internacional de Normalização",
    nota:
      "A ISO 45003:2021 trata de saúde psicológica no trabalho e é uma das " +
      "âncoras do instrumento FROID.",
  },
  CFP: { nome: "Conselho Federal de Psicologia" },
  MPT: {
    nome: "Ministério Público do Trabalho",
    nota:
      "Pode instaurar inquérito civil, exigir Termo de Ajustamento de Conduta " +
      "ou ajuizar ação civil pública.",
  },
  TAC: { nome: "Termo de Ajustamento de Conduta" },
  CLT: { nome: "Consolidação das Leis do Trabalho" },
};

/** "Avaliação Ergonômica Preliminar (AEP)", para a primeira aparição. */
export function porExtenso(sigla: string): string {
  const verbete = SIGLAS[sigla];
  return verbete ? `${verbete.nome} (${sigla})` : sigla;
}

/** O texto completo do verbete, para tooltip e para o glossário. */
export function descricao(sigla: string): string {
  const verbete = SIGLAS[sigla];
  if (!verbete) return sigla;
  return verbete.nota ? `${verbete.nome} — ${verbete.nota}` : verbete.nome;
}
