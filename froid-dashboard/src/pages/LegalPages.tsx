import { useEffect, useState, type ReactNode } from "react";
import { loadLegalCatalog, type LegalCatalog, type LegalDocument } from "../lib/legal";

function LegalShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950/95">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-5 py-4">
          <a href="#/" className="text-sm font-black uppercase tracking-[0.28em] text-cyan-300">FROID</a>
          <nav className="flex flex-wrap gap-3 text-xs font-bold text-slate-300">
            <a className="hover:text-cyan-200" href="#/privacidade">Privacidade</a>
            <a className="hover:text-cyan-200" href="#/termos">Termos</a>
            <a className="hover:text-cyan-200" href="#/contrato-profissional">Profissional</a>
            <a className="hover:text-cyan-200" href="#/contrato-clinica">Clínica</a>
            <a className="hover:text-cyan-200" href="#/tcle-paciente">TCLE</a>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-5 py-10">
        <p className="text-[11px] font-black uppercase tracking-[0.28em] text-cyan-300">Documentação jurídica versionada</p>
        <h1 className="mt-3 text-3xl font-black text-white">{title}</h1>
        {children}
      </main>
    </div>
  );
}

export function LegalDocumentPage({ documentKey }: { documentKey: string }) {
  const [catalog, setCatalog] = useState<LegalCatalog | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    loadLegalCatalog().then(setCatalog).catch((reason) => {
      setError(reason instanceof Error ? reason.message : "Documento indisponível.");
    });
  }, []);

  const document: LegalDocument | undefined = catalog?.documents?.[documentKey];
  if (error) return <LegalShell title="Documento indisponível"><p className="mt-8 rounded border border-red-800 bg-red-950 p-4 text-red-100">{error}</p></LegalShell>;
  if (!catalog || !document) return <LegalShell title="Carregando..."><p className="mt-8 text-slate-400">Carregando versão jurídica vigente...</p></LegalShell>;

  return (
    <LegalShell title={document.title}>
      <div className="mt-5 flex flex-wrap gap-2 text-[10px] font-bold uppercase text-slate-400">
        <span className="rounded border border-slate-700 px-2 py-1">Versão {document.version}</span>
        <span className="rounded border border-slate-700 px-2 py-1">SHA-256 {document.sha256.slice(0, 16)}…</span>
      </div>
      {!catalog.supplier.configured && (
        <p className="mt-5 rounded border border-amber-700 bg-amber-950 p-3 text-xs text-amber-100">Configuração jurídica do fornecedor pendente. Esta versão não deve ser ativada para contratação.</p>
      )}
      <article className="mt-6 space-y-5 rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm leading-7 text-slate-300 shadow-sm">
        {document.sections.map((section) => (
          <section key={section.heading}>
            <h2 className="text-base font-black text-white">{section.heading}</h2>
            <p className="mt-2 whitespace-pre-line">{section.body}</p>
          </section>
        ))}
        <section className="border-t border-slate-800 pt-4 text-xs text-slate-400">
          <p>Contato: {catalog.supplier.contact_email || "configuração pendente"}</p>
          <p>Privacidade: {catalog.supplier.privacy_email || "configuração pendente"}</p>
        </section>
      </article>
    </LegalShell>
  );
}

export function PrivacyPage() { return <LegalDocumentPage documentKey="privacy" />; }
export function TermsPage() { return <LegalDocumentPage documentKey="terms" />; }
export function ProfessionalContractPage() { return <LegalDocumentPage documentKey="professional_contract" />; }
export function OrganizationContractPage() { return <LegalDocumentPage documentKey="organization_contract" />; }
// As duas páginas do lado da empresa. `legalRouteByKey` já apontava para
// /contrato-nr1 desde 22/08/2026 e a rota nunca existiu: o link do contrato no
// cadastro dava 404, e daria na frente do cliente.
export function Nr1TermsPage() { return <LegalDocumentPage documentKey="terms_nr1" />; }
export function Nr1ContractPage() { return <LegalDocumentPage documentKey="nr1_company_contract" />; }
export function PatientTclePage() { return <LegalDocumentPage documentKey="patient_tcle" />; }
