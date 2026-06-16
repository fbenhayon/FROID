const DEFAULT_API_URL = "http://localhost:8000";
const DEFAULT_WS_URL = "ws://localhost:8000";
const LOCAL_API_URL = "http://127.0.0.1:8000";
const LOCAL_WS_URL = "ws://127.0.0.1:8000";

function isSecureBrowserContext() {
  return typeof window !== "undefined" && window.location.protocol === "https:";
}

function isLocalBrowserContext() {
  if (typeof window === "undefined") return false;
  return ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
}

function currentOrigin() {
  return typeof window !== "undefined" ? window.location.origin : "";
}

function currentWsOrigin() {
  if (typeof window === "undefined") return "";
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}`;
}

function cleanPath(path: string) {
  return path.startsWith("/") ? path : `/${path}`;
}

export function apiUrl(path: string) {
  const envBase = ((import.meta as any).env?.VITE_API_URL || "").trim();
  const localEnvBase = ((import.meta as any).env?.VITE_LOCAL_API_URL || "").trim();
  const base =
    isLocalBrowserContext()
      ? localEnvBase || LOCAL_API_URL
      : isSecureBrowserContext() && (!envBase || envBase.startsWith("http://"))
      ? currentOrigin()
      : envBase || DEFAULT_API_URL;

  return `${base.replace(/\/+$/, "")}${cleanPath(path)}`;
}

export function wsUrl(path: string) {
  const envBase = ((import.meta as any).env?.VITE_WS_URL || "").trim();
  const localEnvBase = ((import.meta as any).env?.VITE_LOCAL_WS_URL || "").trim();
  const base =
    isLocalBrowserContext()
      ? localEnvBase || LOCAL_WS_URL
      : isSecureBrowserContext() && (!envBase || envBase.startsWith("ws://"))
      ? currentWsOrigin()
      : envBase || DEFAULT_WS_URL;

  return `${base.replace(/\/+$/, "")}${cleanPath(path)}`;
}
