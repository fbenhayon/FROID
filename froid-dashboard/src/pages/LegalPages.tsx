import { useEffect, useState, type ReactNode } from "react";
import { loadLegalCatalog, type LegalCatalog, type LegalDocument } from "../lib/legal";

/**
 * Folha impressa: A4 branco, sem navegação, sem botões, sem fundo escuro.
 *
 * O documento jurídico só termina o trabalho dele quando chega ao jurídico do
 * cliente, e isso acontece em papel ou PDF. Imprimir a tela como ela é gastaria
 * tinta com menu e devolveria texto claro sobre fundo escuro, ilegível.
 *
 * `break-inside: avoid` nas seções existe por um motivo prático de leitura
 * jurídica: cláusula partida entre duas páginas é onde a citação erra o número.
 */
const CSS_IMPRESSAO = `
@media print {
  @page { size: A4; margin: 18mm 16mm; }
  html, body { background: #fff !important; }
  .froid-nao-imprime { display: none !important; }
  .froid-impresso { background: #fff !important; color: #000 !important; }
  .froid-impresso * { background: transparent !important; color: #000 !important;
    border-color: #999 !important; box-shadow: none !important; }
  .froid-clausula { break-inside: avoid; page-break-inside: avoid; }
  .froid-rodape-impressao { display: block !important; }
}
.froid-rodape-impressao { display: none; }
`;

function voltar() {
  // history.back() respeita de onde a pessoa veio — do cadastro, do painel, de
  // um link externo. Um destino fixo mandaria todo mundo para o mesmo lugar, e
  // quem estava no meio do cadastro perderia o formulário.
  if (typeof window === "undefined") return;
  if (window.history.length > 1) {
    window.history.back();
    return;
  }
  window.location.hash = "#/";
}

function LegalShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="froid-impresso min-h-screen bg-slate-950 text-slate-100">
      <style>{CSS_IMPRESSAO}</style>
      <header className="froid-nao-imprime border-b border-slate-800 bg-slate-950/95">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-5 py-4">
          <div className="flex items-center gap-3">
            {/* Faltava saída. A pessoa abria o contrato durante o cadastro e
                ficava presa: o único caminho era o logotipo, que leva para
                fora do fluxo e faz perder o formulário preenchido. */}
            <button
              type="button"
              onClick={voltar}
              className="rounded border border-slate-700 px-3 py-1.5 text-xs font-black text-slate-200 hover:bg-slate-800"
            >
              ← Voltar
            </button>
            <a href="#/" className="text-sm font-black uppercase tracking-[0.28em] text-cyan-300">FROID</a>
          </div>
          <nav className="flex flex-wrap gap-3 text-xs font-bold text-slate-300">
            <a className="hover:text-cyan-200" href="#/privacidade">Privacidade</a>
            <a className="hover:text-cyan-200" href="#/termos">Termos · Psique</a>
            <a className="hover:text-cyan-200" href="#/termos-nr1">Termos · NR-1</a>
            <a className="hover:text-cyan-200" href="#/contrato-profissional">Profissional</a>
            <a className="hover:text-cyan-200" href="#/contrato-clinica">Clínica</a>
            <a className="hover:text-cyan-200" href="#/contrato-nr1">Contrato NR-1</a>
            <a className="hover:text-cyan-200" href="#/tcle-paciente">TCLE</a>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-5 py-10">
        <p className="froid-nao-imprime text-[11px] font-black uppercase tracking-[0.28em] text-cyan-300">Documentação jurídica versionada</p>
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
      <div className="mt-5 flex flex-wrap items-center gap-2 text-[10px] font-bold uppercase text-slate-400">
        <span className="rounded border border-slate-700 px-2 py-1">Versão {document.version}</span>
        {/* O hash INTEIRO na versão impressa, e abreviado na tela.
            Na tela ele é referência visual; no papel é a prova — meia impressão
            digital não confere nada, e é justamente no documento levado ao
            jurídico do cliente que a conferência vai acontecer. */}
        <span className="rounded border border-slate-700 px-2 py-1">
          <span className="froid-nao-imprime">SHA-256 {document.sha256.slice(0, 16)}…</span>
          <span className="hidden froid-rodape-impressao">SHA-256 {document.sha256}</span>
        </span>
        <span className="rounded border border-slate-700 px-2 py-1 froid-rodape-impressao hidden">
          {document.sections.length} cláusulas
        </span>
        <button
          type="button"
          onClick={() => window.print()}
          className="froid-nao-imprime rounded border border-cyan-700 bg-cyan-950 px-3 py-1 font-black text-cyan-200 hover:bg-cyan-900"
        >
          Imprimir / salvar em PDF
        </button>
      </div>
      {!catalog.supplier.configured && (
        <p className="mt-5 rounded border border-amber-700 bg-amber-950 p-3 text-xs text-amber-100">Configuração jurídica do fornecedor pendente. Esta versão não deve ser ativada para contratação.</p>
      )}
      <article className="mt-6 space-y-5 rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm leading-7 text-slate-300 shadow-sm">
        {document.sections.map((section, indice) => (
          <section key={section.heading} className="froid-clausula">
            <h2 className="text-base font-black text-white">
              {/* Cláusula numerada só na impressão: no papel é assim que se
                  cita, e é assim que o jurídico do cliente vai referenciar. */}
              <span className="hidden froid-rodape-impressao">{indice + 1}. </span>
              {section.heading}
            </h2>
            <p className="mt-2 whitespace-pre-line">{section.body}</p>
          </section>
        ))}
        <section className="border-t border-slate-800 pt-4 text-xs text-slate-400">
          <p>Contato: {catalog.supplier.contact_email || "configuração pendente"}</p>
          <p>Privacidade: {catalog.supplier.privacy_email || "configuração pendente"}</p>
        </section>
        <section className="froid-rodape-impressao hidden border-t border-slate-800 pt-4 text-xs text-slate-400">
          <p>
            Documento gerado a partir da versão vigente em{" "}
            {new Date().toLocaleString("pt-BR")}. A íntegra publicada e a
            impressão digital SHA-256 acima identificam o texto exato aqui
            reproduzido.
          </p>
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
