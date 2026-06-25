export type ProfessionalPrompt = {
  id: string;
  title: string;
  text: string;
  createdAt: string;
};

const STORAGE_KEY = "froid_professional_prompts_v1";
const CURRENT_EMAIL_KEY = "froid_user_email";
export const PROFESSIONAL_PROMPTS_EVENT = "froid:professional-prompts-updated";

function normalizeEmail(email?: string) {
  const direct = (email || "").trim().toLowerCase();
  if (direct) return direct;
  if (typeof window === "undefined") return "local";
  return (window.localStorage.getItem(CURRENT_EMAIL_KEY) || "local").trim().toLowerCase();
}

function readStore(): Record<string, ProfessionalPrompt[]> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeStore(store: Record<string, ProfessionalPrompt[]>) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

export function rememberProfessionalEmail(email?: string) {
  const normalized = normalizeEmail(email);
  if (typeof window !== "undefined" && normalized !== "local") {
    window.localStorage.setItem(CURRENT_EMAIL_KEY, normalized);
  }
}

export function loadProfessionalPrompts(email?: string): ProfessionalPrompt[] {
  const owner = normalizeEmail(email);
  const store = readStore();
  return Array.isArray(store[owner]) ? store[owner] : [];
}

export function saveProfessionalPrompts(email: string | undefined, prompts: ProfessionalPrompt[]) {
  const owner = normalizeEmail(email);
  const store = readStore();
  store[owner] = prompts;
  writeStore(store);
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent(PROFESSIONAL_PROMPTS_EVENT, {
        detail: { email: owner },
      }),
    );
  }
}

export function createProfessionalPrompt(title: string, text: string): ProfessionalPrompt {
  return {
    id: `prompt-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    title: title.trim(),
    text: text.trim(),
    createdAt: new Date().toISOString(),
  };
}
