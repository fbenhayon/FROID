import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Dashboard } from "./pages/Dashboard";
import { AgendaReminderBanner } from "./components/panels/AgendaReminderBanner";
import { LiveSession } from "./pages/LiveSession";
import { History } from "./pages/History";
import { Settings } from "./pages/Settings";
import { AdminDashboard } from "./pages/AdminDashboard";
import { AdminProfessionalDetail } from "./pages/AdminProfessionalDetail";
import { SessionReport } from "./pages/SessionReport";
import { PatientDetail } from "./pages/PatientDetail";
import { NewPatient } from "./pages/NewPatient";
import { LoginPage } from "./pages/LoginPage";
import { HomePage } from "./pages/HomePage";
import { PrivacyPage, TermsPage } from "./pages/LegalPages";
import {
  FroidProfessionalsPage,
  FroidSciencePage,
  FroidTechnologyPage,
} from "./pages/FroidInstitutionalPages";
import { ProfessionalOnboarding } from "./pages/ProfessionalOnboarding";
import { PatientInvitePage } from "./pages/PatientInvitePage";
import { PatientSessionPage } from "./pages/PatientSessionPage";
import { PatientPortalPage } from "./pages/PatientPortalPage";
import { apiUrl } from "./lib/api";
import { rememberProfessionalEmail } from "./lib/professional-prompts";

export type FroidUser = {
  email: string;
  name?: string;
  picture?: string;
  provider?: string;
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
    "/app/login": "/login",
    "/app/entrar": "/login",
    "/app/cadastro": "/access/register",
    "/app/paciente": "/paciente",
    "/app/paciente/login": "/paciente",
    "/app/paciente/portal": "/paciente",
  };
  const target = directRoutes[window.location.pathname.toLowerCase()];
  if (!target) return;
  window.history.replaceState(null, "", `/app/#${target}`);
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
      <Routes>
        <Route path="/convite/:token" element={<PatientInvitePage />} />
        <Route
          path="/paciente/sessao/:sessionId"
          element={<PatientSessionPage />}
        />
        <Route path="/paciente" element={<PatientPortalPage />} />
        <Route path="/paciente/login" element={<PatientPortalPage />} />
        <Route path="/paciente/portal" element={<PatientPortalPage />} />
        <Route
          path="/"
          element={<HomePage />}
        />
        <Route path="/privacidade" element={<PrivacyPage />} />
        <Route path="/termos" element={<TermsPage />} />
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
          element={protectedElement(<ProfessionalOnboarding user={user} onUserChange={setUser} />)}
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
          path="/admin"
          element={clinicalElement(<AdminDashboard user={user} />)}
        />
        <Route
          path="/admin/professional/:professionalEmail"
          element={clinicalElement(<AdminProfessionalDetail user={user} />)}
        />
      </Routes>
    </HashRouter>
  );
}

export default App;
