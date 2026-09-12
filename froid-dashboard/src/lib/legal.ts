import { apiUrl } from "./api";

export type LegalDocument = {
  key: string;
  version: string;
  sha256: string;
  title: string;
  audiences: string[];
  sections: Array<{ heading: string; body: string }>;
};

export type LegalCatalog = {
  version: string;
  jurisdiction: LegalJurisdiction;
  acceptance_required: boolean;
  supplier: {
    name: string;
    tax_id: string;
    /** CNPJ ou CPF, derivado do documento pelo servidor. */
    tax_id_label: string;
    address: string;
    contact_email: string;
    privacy_email: string;
    configured: boolean;
  };
  documents: Record<string, LegalDocument>;
};

export type LegalJurisdiction = "BR" | "ES" | "FR" | "US";

const catalogPromises = new Map<LegalJurisdiction, Promise<LegalCatalog>>();

export function legalJurisdiction(value: unknown): LegalJurisdiction {
  const token = String(value || "").trim().toLowerCase().replace("_", "-");
  if (["es", "es-es", "esp", "espanha", "españa", "spain"].includes(token)) return "ES";
  if (["fr", "fr-fr", "frança", "france"].includes(token)) return "FR";
  if (["us", "en-us", "usa", "estados unidos", "united states"].includes(token)) return "US";
  return "BR";
}

export function loadLegalCatalog(jurisdiction: LegalJurisdiction = "BR"): Promise<LegalCatalog> {
  let catalogPromise = catalogPromises.get(jurisdiction);
  if (!catalogPromise) {
    catalogPromise = fetch(apiUrl(`/api/legal/documents?jurisdiction=${jurisdiction}`))
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data?.detail || "Documentos jurídicos indisponíveis.");
        return data as LegalCatalog;
      })
      .catch((error) => {
        catalogPromises.delete(jurisdiction);
        throw error;
      });
    catalogPromises.set(jurisdiction, catalogPromise);
  }
  return catalogPromise;
}

export function acceptanceFor(document: LegalDocument, accepted: boolean) {
  return {
    accepted,
    version: document.version,
    sha256: document.sha256,
  };
}

/**
 * O documento numera as próprias cláusulas?
 *
 * Existe porque as duas telas que imprimem documento jurídico numeravam a
 * cláusula pela POSIÇÃO NA LISTA. Enquanto os títulos eram nomes ("Pisos de
 * coorte…") isso passava. Quando o contrato do NR-1 foi reescrito em 16
 * cláusulas numeradas, em 11/09/2026, a folha impressa passaria a dizer
 * "8. 8. Agregação, pisos de coorte e proteção das respostas".
 *
 * O defeito maior não é o número repetido: é que numeração derivada de posição
 * renumera o documento inteiro, em silêncio, no dia em que uma cláusula for
 * retirada — e um contrato cuja cláusula 8 vira 7 invalida toda citação já
 * feita, inclusive as do comprovante de aceite e as do FROID Explica.
 */
export function clausulaTemNumeroProprio(heading: string): boolean {
  return /^\d+(\.\d+)*\.\s/.test(heading);
}

/** O rótulo da cláusula: o número dela quando existe, o da posição quando não. */
export function rotuloDaClausula(heading: string, indice: number): string {
  return clausulaTemNumeroProprio(heading) ? heading : `${indice + 1}. ${heading}`;
}

/**
 * A chave é de uma política de privacidade?
 *
 * Existe porque o cadastro da empresa comparava `chave === "privacy"` em DOIS
 * lugares para separar a caixa da privacidade da caixa do contrato — e em
 * 12/09/2026 a política se separou em `privacy` (Psique) e `privacy_nr1`. As
 * duas comparações passariam a ser falsas para a empresa, a política cairia na
 * lista do contrato e os dois atos voltariam a ser um clique só: exatamente o
 * que aquela separação existe para impedir, desfeito sem erro nenhum.
 *
 * Mesma regra do §2.9: onde alguém casa por NOME, o nome tem uma fonte.
 */
export function ehPoliticaDePrivacidade(chave: string): boolean {
  return chave === "privacy" || chave.startsWith("privacy_");
}

export const legalRouteByKey: Record<string, string> = {
  privacy: "/privacidade",
  privacy_nr1: "/privacidade-nr1",
  terms: "/termos",
  terms_nr1: "/termos-nr1",
  psique_contract: "/contrato-psique",
  patient_tcle: "/tcle-paciente",
  nr1_company_contract: "/contrato-nr1",
};

/**
 * Os documentos que ESTA audiência precisa aceitar, lidos do catálogo.
 *
 * Existe porque a tela do cadastro fixava as chaves no código — `terms`,
 * `privacy`, `nr1_company_contract` — e em 25/08/2026 os termos se separaram em
 * dois. A empresa passaria a registrar aceite dos termos do FROID Psique, nunca
 * aceitaria os dela, e o acesso não liberaria: o servidor exige `terms_nr1` e
 * receberia `terms`. Cadastro que responde "sucesso" e não abre é o pior tipo
 * de defeito, porque parece problema de permissão.
 *
 * Derivar da audiência declarada resolve a classe inteira: documento novo com a
 * audiência certa entra sozinho, e documento que não é daquela audiência não
 * entra nunca. É a mesma regra que o servidor aplica em required_document_keys,
 * lida do lado de cá em vez de reescrita — e o servidor continua sendo quem
 * decide, porque é ele que recusa o acesso se faltar alguma.
 */
export function documentosDaAudiencia(
  catalogo: { documents?: Record<string, LegalDocument> } | null | undefined,
  audiencia: string,
): [string, LegalDocument][] {
  const documentos = catalogo?.documents ?? {};
  return Object.entries(documentos).filter(([, doc]) =>
    (doc.audiences ?? []).includes(audiencia),
  );
}
