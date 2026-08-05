import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { lazy, Suspense, useEffect, useMemo, useState, type ReactNode } from "react";
import { AgendaReminderBanner } from "./components/panels/AgendaReminderBanner";
import { LoginPage } from "./pages/LoginPage";
import { HomePage } from "./pages/HomePage";
import { apiUrl } from "./lib/api";
import { rememberProfessionalEmail } from "./lib/professional-prompts";

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
const PatientInvitePage = lazy(() => import("./pages/PatientInvitePage").then((module) => ({ default: module.PatientInvitePage })));
const PatientSessionPage = lazy(() => import("./pages/PatientSessionPage").then((module) => ({ default: module.PatientSessionPage })));
const PatientPortalPage = lazy(() => import("./pages/PatientPortalPage").then((module) => ({ default: module.PatientPortalPage })));
const PrivacyRequests = lazy(() => import("./pages/PrivacyRequests").then((module) => ({ default: module.PrivacyRequests })));
const PrivacyPage = lazy(() => import("./pages/LegalPages").then((module) => ({ default: module.PrivacyPage })));
const TermsPage = lazy(() => import("./pages/LegalPages").then((module) => ({ default: module.TermsPage })));
const ProfessionalContractPage = lazy(() => import("./pages/LegalPages").then((module) => ({ default: module.ProfessionalContractPage })));
const OrganizationContractPage = lazy(() => import("./pages/LegalPages").then((module) => ({ default: module.OrganizationContractPage })));
const PatientTclePage = lazy(() => import("./pages/LegalPages").then((module) => ({ default: module.PatientTclePage })));
const FroidProfessionalsPage = lazy(() => import("./pages/FroidInstitutionalPages").then((module) => ({ default: module.FroidProfessionalsPage })));
const Nr1Aep = lazy(() => import("./pages/Nr1Aep").then((module) => ({ default: module.Nr1Aep })));
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
  };
};

function onboardingRequired(user: FroidUser | null) {
  return Boolean(user?.access_status?.onboarding_required);
}

function defaultAuthenticatedPath(user: FroidUser | null) {
  return onboardingRequired(user) ? "/access/register" : "/dashboard";
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
        <Navigate to="/access/register" replace />
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
        <Route path="/tcle-paciente" element={<PatientTclePage />} />
        <Route path="/froid/ciencia" element={<FroidSciencePage />} />
        <Route path="/froid/tecnologia" element={<FroidTechnologyPage />} />
        <Route path="/froid/profissionais" element={<FroidProfessionalsPage />} />
        <Route
          path="/login"
          element={
            isAuthenticated ? (
              <Navigate to={defaultAuthenticatedPath(user)} replace />
            ) : (
              <LoginPage onLogin={setUser} afterLoginPath="/dashboard" />
            )
          }
        />
        <Route
          path="/access/register"
          element={protectedElement(
            !onboardingRequired(user) ? (
              <Navigate to="/dashboard" replace />
            ) : (
              <ProfessionalOnboarding user={user} onUserChange={setUser} />
            ),
          )}
        />
        <Route
          path="/dashboard"
          element={
            protectedElement(
              onboardingRequired(user) ? (
                <Navigate to="/access/register" replace />
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
