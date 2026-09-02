// Quem a pessoa é no FROID — a pergunta que decide o cadastro inteiro.
//
// Eram duas perguntas: aqui escolhia-se o produto (clínico ou NR-1) e, quem
// escolhesse clínico, encontrava DENTRO do formulário um segundo par de opções
// ("pessoa física" / "pessoa jurídica") que era o que de fato virava
// account_type no servidor. Duas perguntas sobre a mesma coisa, separadas por
// uma tela de cadastro, e a segunda escondida no meio dela.
//
// Agora é uma pergunta só, com as três respostas possíveis lado a lado. A
// escolha continua decidindo QUAL FORMULÁRIO aparece — ela não concede acesso,
// não define papel e não pode ser lida como permissão. Quem manda nisso é o
// backend, via access_status e account_type; guardar no navegador é aceitável
// justamente porque não é fronteira de segurança. A fronteira que importa —
// empresa NR-1 nunca virar clínica — é conferida no servidor, em
// _assert_account_type_transition.

export type FroidProduct = "individual" | "clinic" | "nr1";

/** account_type correspondente, como o backend o nomeia. */
export type FroidAccountType = "individual" | "organization" | "nr1_company";

const STORAGE_KEY = "froid.product-choice";

export const PRODUCT_LABELS: Record<FroidProduct, string> = {
  individual: "Profissional autônomo",
  clinic: "Clínica",
  nr1: "Plano NR-1 empresarial",
};

const ACCOUNT_TYPES: Record<FroidProduct, FroidAccountType> = {
  individual: "individual",
  clinic: "organization",
  nr1: "nr1_company",
};

export function accountTypeForProduct(product: FroidProduct): FroidAccountType {
  return ACCOUNT_TYPES[product];
}

export function productForAccountType(
  accountType: string | null | undefined,
): FroidProduct | null {
  if (accountType === "nr1_company") return "nr1";
  if (accountType === "organization") return "clinic";
  if (accountType === "individual") return "individual";
  return null;
}

/** Para onde a escolha leva. Empresa e cadastro clínico não compartilham
 *  formulário: os campos e o contrato aceito são outros. */
export function pathForProduct(product: FroidProduct): string {
  return product === "nr1" ? "/access/empresa" : "/access/register";
}

function isProduct(value: unknown): value is FroidProduct {
  return value === "individual" || value === "clinic" || value === "nr1";
}

export function readProductChoice(): FroidProduct | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    // O valor legado "clinical" não é convertido de propósito: ele não
    // distingue autônomo de clínica, que é justamente a distinção que passou a
    // valer. Adivinhar aqui rebaixaria uma clínica a profissional individual
    // sem ninguém perceber; devolver null custa um clique e não mente.
    return isProduct(stored) ? stored : null;
  } catch {
    // Navegador com armazenamento bloqueado. Sem escolha registrada a pessoa
    // volta a ver a tela de escolha — irritante, nunca destrutivo.
    return null;
  }
}

export function saveProductChoice(product: FroidProduct): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, product);
  } catch {
    /* idem */
  }
}

export function clearProductChoice(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* idem */
  }
}

/**
 * Para onde uma pessoa autenticada vai. Uma regra, um lugar.
 *
 * Estava escrita em TRÊS: `defaultAuthenticatedPath` no App, e mais duas cópias
 * abreviadas em LoginPage e AccountAccessPages, cada uma decidindo sozinha que
 * `onboarding_required` significa "vá escolher um produto". Em 25/08/2026 a
 * regra ganhou uma exceção — o administrador da plataforma vai para /admin,
 * porque na escolha de produto as duas portas estão fechadas para ele — e a
 * exceção entrou só na cópia do App. O administrador continuou caindo na tela
 * de escolha a cada login, e a correção parecia não ter funcionado.
 *
 * O tipo é estrutural de propósito: `FroidUser` mora no App, e importá-lo aqui
 * criaria ciclo com quem chama. O que esta função precisa saber é só isto.
 */
export type UsuarioRoteavel = {
  access_status?: {
    onboarding_required?: boolean;
    admin?: boolean;
    /** Decide a casa da conta depois do cadastro: `nr1_company` vai para o
     *  painel de conformidade, e nao para o painel clinico. */
    account_type?: string;
    /** Os campos abaixo separam "ainda não se cadastrou" de "acabou o saldo".
     *  Os dois produzem `onboarding_required`, e mandam a pessoa para lugares
     *  diferentes — confundi-los foi o que prendeu o Fábio em /admin. */
    has_profile?: boolean;
    remaining_sessions?: number;
    total_sessions?: number;
    used_sessions?: number;
    pending_settlement_count?: number;
    trial_exhausted?: boolean;
  };
} | null | undefined;

/** O acesso parou por saldo, e não por cadastro incompleto?
 *
 *  A diferença decide o que a pessoa vê. Quem nunca preencheu o cadastro
 *  precisa do formulário; quem já é cliente e ficou sem sessão precisa saber
 *  disso — e hoje era mandado para uma tela sem relação com o problema, sem
 *  nenhuma explicação.
 *
 *  Exige `has_profile`: sem perfil não há saldo que possa ter acabado, e o
 *  caminho certo continua sendo o cadastro. */
export function bloqueadoPorSaldo(user: UsuarioRoteavel): boolean {
  const acesso = user?.access_status;
  if (!acesso?.onboarding_required) return false;
  if (!acesso.has_profile) return false;
  if ((acesso.pending_settlement_count ?? 0) > 0) return true;
  if (acesso.trial_exhausted) return true;
  return (acesso.remaining_sessions ?? 0) <= 0;
}

export function onboardingRequired(user: UsuarioRoteavel): boolean {
  return Boolean(user?.access_status?.onboarding_required);
}

/** Quem ainda vai se cadastrar precisa dizer para qual produto, antes do
 *  formulário — os dois cadastros pedem coisas diferentes. Quem já escolheu
 *  segue direto, para não reperguntar a cada recarga da página. */
export function needsProductChoice(
  user: UsuarioRoteavel,
  choice: FroidProduct | null,
): boolean {
  return onboardingRequired(user) && choice === null;
}

/** Para onde vai a conta que ja terminou o cadastro.
 *
 *  Mandava todo mundo para /dashboard, que e o painel CLINICO — entao a
 *  empresa contratante do NR-1 entrava e via "Saldo: 5 sessoes", "Meus
 *  Pacientes", "Gestao da clinica" e o FROID Explica clinico. Alem de inutil
 *  para ela, e a tela que mais contradiz o que o produto promete: o
 *  empregador nao tem, e nao pode ter, pacientes.
 *
 *  O tipo da conta e decidido no cadastro e gravado no servidor: `nr1_company`
 *  produz organizacao `enterprise`, e a casa dela e o painel de conformidade.
 */
export function homeDoProduto(user: UsuarioRoteavel): string {
  return user?.access_status?.account_type === "nr1_company" ? "/nr1" : "/dashboard";
}

export function defaultAuthenticatedPath(
  user: UsuarioRoteavel,
  choice: FroidProduct | null,
): string {
  if (!onboardingRequired(user)) return homeDoProduto(user);
  // O operador da plataforma vai para onde ele tem o que fazer.
  //
  // Um administrador que nunca comprou plano de sessões para si mesmo tem
  // `onboarding_required` verdadeiro para sempre. Na escolha de produto as duas
  // portas estão fechadas para ele: a opção de empresa aparece indisponível
  // porque a conta já é clínica, e a clínica o levaria a comprar um plano que
  // ele não quer. Ficava em círculo, sem conseguir aprovar ninguém — e aprovar
  // é o passo que libera todo cadastro de empresa.
  if (user?.access_status?.admin) return "/admin";
  if (needsProductChoice(user, choice)) return "/access/produto";
  // Respeitar a escolha aqui não é detalhe: mandar todo mundo para
  // /access/register fazia a empresa NR-1 que voltasse no meio do cadastro
  // reaparecer no formulário clínico, que pede CRP e plano de sessões.
  return pathForProduct(choice as FroidProduct);
}
