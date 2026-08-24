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

export const legalRouteByKey: Record<string, string> = {
  privacy: "/privacidade",
  terms: "/termos",
  professional_contract: "/contrato-profissional",
  organization_contract: "/contrato-clinica",
  patient_tcle: "/tcle-paciente",
  nr1_company_contract: "/contrato-nr1",
};
