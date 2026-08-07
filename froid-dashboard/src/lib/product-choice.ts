// Qual dos dois produtos do FROID a pessoa veio contratar.
//
// A escolha decide QUAL FORMULÁRIO aparece — nada além disso. Ela não concede
// acesso, não define papel e não pode ser lida como permissão: quem manda nisso
// é o backend, via access_status. Guardar no navegador é aceitável justamente
// porque não é fronteira de segurança; se fosse, teria de viver no servidor.
//
// É uma ponte até o cadastro guiado da empresa NR-1 existir. Quando ele
// existir, a escolha passa a ser gravada junto com a organização e esta camada
// vira só o cache dela.

export type FroidProduct = "clinical" | "nr1";

const STORAGE_KEY = "froid.product-choice";

export const PRODUCT_LABELS: Record<FroidProduct, string> = {
  clinical: "Sessões clínicas",
  nr1: "Plano NR-1 empresarial",
};

function isProduct(value: unknown): value is FroidProduct {
  return value === "clinical" || value === "nr1";
}

export function readProductChoice(): FroidProduct | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
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
