import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { lazy, Suspense, useEffect, useMemo, useState, type ReactNode } from "react";
import { AgendaReminderBanner } from "./components/panels/AgendaReminderBanner";
import { LoginPage } from "./pages/LoginPage";
import { HomePage } from "./pages/HomePage";
import { apiUrl } from "./lib/api";
import { rememberProfessionalEmail } from "./lib/professional-prompts";
import {
  clearProductChoice,
  pathForProduct,
  readProductChoice,
  saveProductChoice,
  type FroidProduct,
} from "./lib/product-choice";

const Dashboard = lazy(() => import("./pages/Dashboard").then((module) => ({ default: module.Dashboard })));
const ProfessionalDashboardSummary = lazy(() => import("./pages/ProfessionalDashboardSummary").then((module) => ({ default: module.ProfessionalDashboardSummary })));
const LiveSession = lazy(() => import("./pages/LiveSession").then((module) => ({ default: module.LiveSession })));
const History = lazy(() => import("./pages/History").then((module) => ({ default: module.History })));
const Settings = lazy(() => import("./pages/Settings").then((module) => ({ default: module.Settings })));
const ClinicManagement = lazy(() => import("./pages/ClinicManagement").then((module) => ({ default: module.ClinicManagement })));
const AdminDashboard = lazy(() => import("./pages/AdminDashboard").then((module) => ({ default: module.AdminDashboard })));
const AdminProfessionalDetail = lazy(() => import("./pages/AdminProfessionalDetail").then((module) => ({ default: module.AdminProfessionalDetail })));
const AdminPatientDetail = lazy(() => import("./pages/AdminPatientDetail").then((module) => ({ default: module.AdminPatientDetail })));
const SessionReport = lazy(() => import("./pages/SessionReport").then((module) => ({ default: module.SessionReport })));
const PatientDetail = lazy(() => import("./pages/PatientDetail").then((module) => ({ default: module.PatientDetail })));
const NewPatient = lazy(() => import("./pages/NewPatient").then((module) => ({ default: module.NewPatient })));
const ProfessionalOnboarding = lazy(() => import("./pages/ProfessionalOnboarding").then((module) => ({ default: module.ProfessionalOnboarding })));
const ProductChoice = lazy(() => import("./pages/ProductChoice").then((module) => ({ default: module.ProductChoice })));
const VerifyEmailPage = lazy(() => import("./pages/AccountAccessPages").then((module) => ({ default: module.VerifyEmailPage })));
const PasswordResetPage = lazy(() => import("./pages/AccountAccessPages").then((module) => ({ default: module.PasswordResetPage })));
const Nr1CompanyOnboarding = lazy(() => import("./pages/Nr1CompanyOnboarding").then((module) => ({ default: module.Nr1CompanyOnboarding })));
const PatientInvitePage = lazy(() => import("./pages/PatientInvitePage").then((module) => ({ default: module.PatientInvitePage })));
const PatientSessionPage = lazy(() => import("./pages/PatientSessionPage").then((module) => ({ default: module.PatientSessionPage })));
const PatientPortalPage = lazy(() => import("./pages/PatientPortalPage").then((module) => ({ default: module.PatientPortalPage })));
const PrivacyRequests = lazy(() => import("./pages/PrivacyRequests").then((module) => ({ default: module.PrivacyRequests })));
const PrivacyPage = lazy(() => import("./pages/LegalPages").then((module) => ({ default: module.PrivacyPage })));
const TermsPage = lazy(() => import("./pages/LegalPages").then((module) => ({ default: module.TermsPage })));
const ProfessionalContractPage = lazy(() => import("./pages/LegalPages").then((module) => ({ default: module.ProfessionalContractPage })));
const OrganizationContractPage = lazy(() => import("./pages/LegalPages").then((module) => ({ default: module.OrganizationContractPage })));
const Nr1TermsPage = lazy(() => import("./pages/LegalPages").then((module) => ({ default: module.Nr1TermsPage })));
const Nr1ContractPage = lazy(() => import("./pages/LegalPages").then((module) => ({ default: module.Nr1ContractPage })));
const PatientTclePage = lazy(() => import("./pages/LegalPages").then((module) => ({ default: module.PatientTclePage })));
const FroidProfessionalsPage = lazy(() => import("./pages/FroidInstitutionalPages").then((module) => ({ default: module.FroidProfessionalsPage })));
const Nr1Aep = lazy(() => import("./pages/Nr1Aep").then((module) => ({ default: module.Nr1Aep })));
const Nr1ActionPlan = lazy(() => import("./pages/Nr1ActionPlan").then((module) => ({ default: module.Nr1ActionPlan })));
const Nr1Dashboard = lazy(() => import("./pages/Nr1Dashboard").then((module) => ({ default: module.Nr1Dashboard })));
const Nr1Effectiveness = lazy(() => import("./pages/Nr1Effectiveness").then((module) => ({ default: module.Nr1Effectiveness })));
const ValidationStudy = lazy(() => import("./pages/ValidationStudy").then((module) => ({ default: module.ValidationStudy })));
const Nr1QuestionnairePage = lazy(() => import("./pages/Nr1QuestionnairePage").then((module) => ({ default: module.Nr1QuestionnairePage })));
const FroidSciencePage = lazy(() => import("./pages/FroidInstitutionalPages").then((module) => ({ default: module.FroidSciencePage })));
const FroidTechnologyPage = lazy(() => import("./pages/FroidInstitutionalPages").then((module) => ({ default: module.FroidTechnologyPage })));

export type FroidUser = {
  email: string;
  name?: string;
  picture?: string;
  provider?: string;
  active_organization_id?: string;
  organizations?: Array<{
    organization_id: string;
    organization_name?: string;
    roles?: string[];
  }>;
  access_status?: {
    has_profile?: boolean;
    /** Tipo já gravado no servidor. Vazio enquanto não há perfil. É ele que
     *  diz se a escolha de produto ainda está em aberto: a travessia entre
     *  cadastro clínico e empresa NR-1 é recusada pelo backend, e a tela
     *  precisa saber disso antes de deixar alguém preencher um formulário
     *  inteiro. */
    account_type?: "individual" | "organization" | "nr1_company" | "";
    lgpd_acknowledged?: boolean;
    selected_plan?: string;
    payment_status?: string;
    onboarding_required?: boolean;
    total_sessions?: number;
    used_sessions?: number;
    remaining_sessions?: number;
    admin?: boolean;
    manual_approval_required?: boolean;
    manual_approval_status?: "pending" | "approved" | "rejected" | "suspended";
    manual_approval_pending?: boolean;
    manual_approval_ready?: boolean;
    /** Sessões de cortesia do cadastro. `on_trial` é falso assim que houver
     *  qualquer compra — inclusive se o saldo comprado zerar depois, porque a
     *  partir dali vale a regra do cliente pagante. */
    on_trial?: boolean;
    trial_sessions?: number;
    trial_used?: number;
    trial_remaining?: number;
    trial_exhausted?: boolean;
    trial_notice?: string;
    trial_contact_email?: string;
  };
};

function onboardingRequired(user: FroidUser | null) {
  return Boolean(user?.access_status?.onboarding_required);
}

/** Quem ainda vai se cadastrar precisa dizer para qual produto, antes do
 *  formulário — os dois cadastros pedem coisas diferentes. Quem já escolheu
 *  segue direto, para não reperguntar a cada recarga da página.
 *
 *  A escolha entra por parâmetro, e não é lida do armazenamento aqui dentro,
 *  por um motivo que custou uma sessão de depuração: os `element` das rotas são
 *  calculados no render do App, que está ACIMA do HashRouter e portanto não
 *  re-renderiza quando a navegação acontece. Lendo o localStorage aqui, o
 *  elemento de /access/register congelava com o valor do primeiro render — e
 *  devolvia para a escolha para sempre, deixando o cadastro clínico
 *  inalcançável. Sendo estado do React, a mudança re-renderiza o App e as rotas
 *  recalculam. */
function needsProductChoice(
  user: FroidUser | null,
  choice: FroidProduct | null,
) {
  return onboardingRequired(user) && choice === null;
}

function defaultAuthenticatedPath(
  user: FroidUser | null,
  choice: FroidProduct | null,
) {
  if (!onboardingRequired(user)) return "/dashboard";
  if (needsProductChoice(user, choice)) return "/access/produto";
  // Respeitar a escolha aqui não é detalhe: mandar todo mundo para
  // /access/register fazia a empresa NR-1 que voltasse no meio do cadastro
  // reaparecer no formulário clínico, que pede CRP e plano de sessões — a
  // mesma confusão que a tela de escolha existe para acabar.
  return pathForProduct(choice as FroidProduct);
}

function localDevUser(): FroidUser | null {
  if (typeof window === "undefined") return null;
  if (!import.meta.env.DEV) return null;
  const isLocalhost = ["localhost", "127.0.0.1", "::1"].includes(
    window.location.hostname,
  );
  if (!isLocalhost || localStorage.getItem("froid_token") !== "dev-local") {
    return null;
  }
  try {
    const stored = JSON.parse(localStorage.getItem("froid_user") || "{}");
    return {
      email: stored.email || "dev@froid.local",
      name: stored.name || "Profissional FROID",
      provider: "local-dev",
      // Carried through so organization-scoped screens (NR-1, LGPD) can be
      // developed locally; without a tenant they render empty.
      active_organization_id: stored.active_organization_id,
      organizations: Array.isArray(stored.organizations) ? stored.organizations : undefined,
      // Idem para o estado de acesso: sem ele, onboarding_required nunca chega
      // ao roteador e as telas de cadastro ficam inalcançáveis em
      // desenvolvimento — que foi como a escolha de produto quase passou sem
      // ninguém conseguir vê-la rodando.
      access_status: stored.access_status,
    };
  } catch {
    return {
      email: "dev@froid.local",
      name: "Profissional FROID",
      provider: "local-dev",
    };
  }
}

function normalizeDirectPublicPath() {
  if (typeof window === "undefined") return;
  if (window.location.hash) return;
  const directRoutes: Record<string, string> = {
    "/login": "/login",
    "/entrar": "/login",
    "/cadastro": "/access/register",
    "/access/register": "/access/register",
    "/privacidade": "/privacidade",
    "/politica-de-privacidade": "/privacidade",
    "/termos": "/termos",
    "/termos-de-uso": "/termos",
    "/paciente": "/paciente",
    "/paciente/login": "/paciente",
    "/paciente/portal": "/paciente",
    "/avaliacao": "/avaliacao",
    "/app/login": "/login",
    "/app/entrar": "/login",
    "/app/cadastro": "/access/register",
    "/app/paciente": "/paciente",
    "/app/paciente/login": "/paciente",
    "/app/paciente/portal": "/paciente",
    "/app/avaliacao": "/avaliacao",
  };
  const target = directRoutes[window.location.pathname.toLowerCase()];
  if (!target) return;
  // Keep the query string: the NR-1 questionnaire carries its single-use token
  // there, and dropping it would turn a valid invitation into a dead link.
  const search = window.location.search || "";
  window.history.replaceState(null, "", `/app/#${target}${search}`);
}

function App() {
  const [user, setUser] = useState<FroidUser | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    normalizeDirectPublicPath();
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("froid_token");
    if (!token) {
      setCheckingSession(false);
      return;
    }

    const devUser = localDevUser();
    if (devUser) {
      setUser(devUser);
      rememberProfessionalEmail(devUser.email);
      setCheckingSession(false);
      return;
    }

    fetch(apiUrl("/api/auth/me"), {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          setUser(data);
          rememberProfessionalEmail(data.email);
        } else localStorage.removeItem("froid_token");
      })
      .catch(() => localStorage.removeItem("froid_token"))
      .finally(() => setCheckingSession(false));
  }, []);

  const isAuthenticated = useMemo(() => !!user, [user]);

  // Espelho em estado do que está gravado no navegador. Ver o comentário de
  // needsProductChoice: precisa ser estado para as rotas recalcularem.
  const [productChoice, setProductChoice] = useState<FroidProduct | null>(
    () => readProductChoice(),
  );

  const chooseProduct = (product: FroidProduct) => {
    saveProductChoice(product);
    setProductChoice(product);
  };

  const resetProductChoice = () => {
    clearProductChoice();
    setProductChoice(null);
  };

  const logout = () => {
    const token = localStorage.getItem("froid_token") || "";
    if (token && token !== "dev-local") {
      void fetch(apiUrl("/api/auth/logout"), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => undefined);
    }
    localStorage.removeItem("froid_token");
    localStorage.removeItem("froid_user");
    // A escolha de produto é do navegador, não da conta. Sem limpar aqui, quem
    // entrasse depois nesta mesma máquina herdaria a escolha de quem saiu e
    // pularia a tela — caindo no formulário do produto errado.
    resetProductChoice();
    setUser(null);
    window.location.hash = "#/login";
  };

  const protectedElement = (element: ReactNode) => {
    if (checkingSession) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-slate-950 text-sm font-semibold text-slate-300">
          Carregando acesso FROID...
        </div>
      );
    }
    if (!isAuthenticated) {
      const currentPath =
        typeof window !== "undefined"
          ? window.location.hash.replace(/^#/, "") || "/dashboard"
          : "/dashboard";
      return <LoginPage onLogin={setUser} afterLoginPath={currentPath} />;
    }
    return element;
  };

  const clinicalElement = (element: ReactNode) =>
    protectedElement(
      onboardingRequired(user) ? (
        <Navigate to={defaultAuthenticatedPath(user, productChoice)} replace />
      ) : (
        element
      ),
    );

  return (
    <HashRouter>
      <AgendaReminderBanner enabled={isAuthenticated && !onboardingRequired(user)} />
      <Suspense
        fallback={(
          <div className="flex min-h-screen items-center justify-center bg-slate-950 text-sm font-semibold text-slate-300">
            Carregando módulo FROID...
          </div>
        )}
      >
        <Routes>
        <Route path="/convite/:token" element={<PatientInvitePage />} />
        <Route
          path="/paciente/sessao/:sessionId"
          element={<PatientSessionPage />}
        />
        {/* Anonymous NR-1 questionnaire. Public on purpose: the worker has no
            FROID login, and the single-use token in the link is the whole
            authorization. */}
        <Route path="/avaliacao" element={<Nr1QuestionnairePage />} />
        <Route path="/paciente" element={<PatientPortalPage />} />
        <Route path="/paciente/login" element={<PatientPortalPage />} />
        <Route path="/paciente/portal" element={<PatientPortalPage />} />
        <Route
          path="/"
          element={<HomePage />}
        />
        <Route path="/privacidade" element={<PrivacyPage />} />
        <Route path="/termos" element={<TermsPage />} />
        <Route path="/contrato-profissional" element={<ProfessionalContractPage />} />
        <Route path="/contrato-clinica" element={<OrganizationContractPage />} />
        <Route path="/termos-nr1" element={<Nr1TermsPage />} />
        <Route path="/contrato-nr1" element={<Nr1ContractPage />} />
        <Route path="/tcle-paciente" element={<PatientTclePage />} />
        <Route path="/froid/ciencia" element={<FroidSciencePage />} />
        <Route path="/froid/tecnologia" element={<FroidTechnologyPage />} />
        <Route path="/froid/profissionais" element={<FroidProfessionalsPage />} />
        <Route
          path="/login"
          element={
            isAuthenticated ? (
              <Navigate to={defaultAuthenticatedPath(user, productChoice)} replace />
            ) : (
              <LoginPage onLogin={setUser} afterLoginPath="/dashboard" />
            )
          }
        />
        {/* Acesso de quem não tem conta Google. Público de propósito: são
            exatamente as telas de quem ainda não tem sessão para proteger. A
            verificação e a recuperação valem mesmo com alguém já logado — é
            comum abrir o link do e-mail na janela onde outra conta está
            aberta, e a sessão nova simplesmente substitui a anterior.

            /registrar é a MESMA tela de /login, aberta na aba de cadastro: o
            link antigo continua valendo e quem chega por ele não cai numa
            página separada de onde teria que voltar para entrar. */}
        <Route
          path="/registrar"
          element={
            isAuthenticated ? (
              <Navigate to={defaultAuthenticatedPath(user, productChoice)} replace />
            ) : (
              <LoginPage onLogin={setUser} afterLoginPath="/dashboard" initialMode="criar" />
            )
          }
        />
        <Route path="/verificar-email" element={<VerifyEmailPage onLogin={setUser} />} />
        <Route path="/recuperar-senha" element={<PasswordResetPage onLogin={setUser} />} />
        <Route
          path="/access/produto"
          element={protectedElement(
            !onboardingRequired(user) ? (
              // Quem já concluiu o cadastro não volta a escolher produto: a
              // conta dele já existe com um tipo definido.
              <Navigate to="/dashboard" replace />
            ) : (
              <ProductChoice
                user={user}
                onLogout={logout}
                onChoose={chooseProduct}
                onReset={resetProductChoice}
                choice={productChoice}
              />
            ),
          )}
        />
        <Route
          path="/access/empresa"
          element={protectedElement(
            needsProductChoice(user, productChoice) ? (
              // Sem escolher o produto não se sabe qual cadastro vale.
              <Navigate to="/access/produto" replace />
            ) : (
              // Continua alcançável depois de concluído: a empresa volta aqui
              // para acrescentar uma filial ou corrigir um efetivo, e por isso
              // esta rota NÃO checa onboarding_required como as outras.
              <Nr1CompanyOnboarding
                user={user}
                onUserChange={setUser}
                onLogout={logout}
              />
            ),
          )}
        />
        <Route
          path="/access/register"
          element={protectedElement(
            !onboardingRequired(user) ? (
              <Navigate to="/dashboard" replace />
            ) : needsProductChoice(user, productChoice) ? (
              // Chegar direto na ficha clínica por link antigo ou favorito não
              // pode pular a escolha — é ela que decide quais campos valem.
              <Navigate to="/access/produto" replace />
            ) : productChoice === "nr1" ? (
              // Escolheu empresa e caiu aqui por link antigo: o formulário
              // clínico pede CRP e plano de sessões, que não é o cadastro dela.
              <Navigate to="/access/empresa" replace />
            ) : (
              <ProfessionalOnboarding
                user={user}
                onUserChange={setUser}
                choice={productChoice}
              />
            ),
          )}
        />
        <Route
          path="/dashboard"
          element={
            protectedElement(
              onboardingRequired(user) ? (
                // Era um /access/register fixo, que manda a empresa NR-1 para o
                // formulario clinico — o que pede CRP e plano de sessoes e nao e
                // o cadastro dela. defaultAuthenticatedPath ja respeita a
                // escolha de produto e leva a /access/empresa.
                <Navigate to={defaultAuthenticatedPath(user, productChoice)} replace />
              ) : (
                <Dashboard user={user} onLogout={logout} />
              ),
            )
          }
        />
        <Route
          path="/dashboard/resumido"
          element={clinicalElement(<ProfessionalDashboardSummary user={user} onLogout={logout} />)}
        />
        <Route
          path="/clinica"
          element={clinicalElement(<ClinicManagement user={user} />)}
        />
        <Route
          path="/session/:sessionId"
          element={clinicalElement(<LiveSession user={user} />)}
        />
        <Route
          path="/session/:sessionId/report"
          element={clinicalElement(<SessionReport user={user} />)}
        />
        <Route
          path="/patients/new"
          element={clinicalElement(<NewPatient />)}
        />
        <Route
          path="/patients/:patientKey"
          element={clinicalElement(<PatientDetail />)}
        />
        <Route
          path="/history"
          element={clinicalElement(<History user={user} />)}
        />
        <Route
          path="/settings"
          element={clinicalElement(<Settings user={user} />)}
        />
        <Route
          path="/privacy-requests"
          element={clinicalElement(<PrivacyRequests user={user} />)}
        />
        <Route path="/validade" element={clinicalElement(<ValidationStudy user={user} />)} />
        <Route path="/nr1" element={clinicalElement(<Nr1Dashboard user={user} />)} />
        <Route path="/nr1/aep" element={clinicalElement(<Nr1Aep user={user} />)} />
        <Route path="/nr1/plano-de-acao" element={clinicalElement(<Nr1ActionPlan user={user} />)} />
        <Route
          path="/nr1/eficacia"
          element={clinicalElement(<Nr1Effectiveness user={user} />)}
        />
        <Route
          path="/admin"
          element={clinicalElement(<AdminDashboard user={user} />)}
        />
        <Route
          path="/admin/professional/:professionalEmail"
          element={clinicalElement(<AdminProfessionalDetail user={user} />)}
        />
        <Route
          path="/admin/patient/:patientId"
          element={clinicalElement(<AdminPatientDetail user={user} />)}
        />
        </Routes>
      </Suspense>
    </HashRouter>
  );
}

export default App;
