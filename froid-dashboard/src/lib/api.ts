const DEFAULT_API_URL = "http://localhost:8000";

export function apiUrl(path: string) {
  const base = ((import.meta as any).env?.VITE_API_URL || DEFAULT_API_URL)
    .replace(/\/+$/, "");
  const cleanPath = path.startsWith("/") ? path : `/${path}`;

  return `${base}${cleanPath}`;
}
