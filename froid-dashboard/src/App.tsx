import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { Dashboard } from "./pages/Dashboard";
import { LiveSession } from "./pages/LiveSession";
import { History } from "./pages/History";
import { Settings } from "./pages/Settings";
import { LoginPage } from "./pages/LoginPage";
import { apiUrl } from "./lib/api";

export type FroidUser = {
  email: string;
  name?: string;
  picture?: string;
  provider?: string;
};

function App() {
  const [user, setUser] = useState<FroidUser | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("froid_token");
    if (!token) {
      setCheckingSession(false);
      return;
    }

    fetch(apiUrl("/api/auth/me"), {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setUser(data);
        else localStorage.removeItem("froid_token");
      })
      .catch(() => localStorage.removeItem("froid_token"))
      .finally(() => setCheckingSession(false));
  }, []);

  const isAuthenticated = useMemo(() => !!user, [user]);

  if (checkingSession) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-sm font-semibold text-slate-300">
        Carregando acesso FROID...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage onLogin={setUser} />;
  }

  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard user={user} />} />
        <Route
          path="/session/:sessionId"
          element={<LiveSession user={user} />}
        />
        <Route path="/history" element={<History user={user} />} />
        <Route path="/settings" element={<Settings user={user} />} />
      </Routes>
    </HashRouter>
  );
}

export default App;
