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

let catalogPromise: Promise<LegalCatalog> | null = null;

export function loadLegalCatalog(): Promise<LegalCatalog> {
  if (!catalogPromise) {
    catalogPromise = fetch(apiUrl("/api/legal/documents"))
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data?.detail || "Documentos jurídicos indisponíveis.");
        return data as LegalCatalog;
      })
      .catch((error) => {
        catalogPromise = null;
        throw error;
      });
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
};
