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
