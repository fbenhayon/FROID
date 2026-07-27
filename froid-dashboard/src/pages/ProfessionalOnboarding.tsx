import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiUrl, publicAppUrl } from "../lib/api";
import type { FroidUser } from "../App";
import { LgpdNotice } from "../components/legal/LgpdNotice";
import {
  acceptanceFor,
  legalJurisdiction,
  loadLegalCatalog,
  type LegalCatalog,
} from "../lib/legal";

type AccessPlan = {
  id: string;
  name: string;
  description: string;
  session_credits: number;
  amount_cents: number;
  display_amount: string;
  total_amount_cents?: number;
  currency?: string;
};

const billingMarkets = [
  { code: "BR", label: "Brasil", currency: "brl", note: "Pacotes comerciais cobrados em reais." },
  { code: "US", label: "Estados Unidos", currency: "usd", note: "Pacotes comerciais cobrados em dólares americanos." },
  { code: "ES", label: "Espanha", currency: "eur", note: "Pacotes comerciais cobrados em euros." },
  { code: "FR", label: "França", currency: "eur", note: "Pacotes comerciais cobrados em euros." },
  { code: "EU", label: "Outros países da União Europeia", currency: "eur", note: "Pacotes comerciais cobrados em euros." },
  { code: "CN", label: "China", currency: "cny", note: "Pacotes comerciais cobrados em yuan renminbi." },
];

type ProfessionalLine = {
  name: string;
  email: string;
  phone: string;
};

type Referral = {
  name: string;
  phone: string;
  email: string;
};

type ValidationIssue = {
  message: string;
  target?: string;
};

interface Props {
  user: FroidUser | null;
  onUserChange: (user: FroidUser | null) => void;
}

const emptyFields: Record<string, string> = {
  fullName: "",
  mobile: "",
  email: "",
  sex: "",
  birthDate: "",
  cpf: "",
  rg: "",
  rgIssuer: "",
  naturality: "",
  nationality: "",
  phone: "",
  postalCode: "",
  street: "",
  number: "",
  district: "",
  complement: "",
  country: "",
  state: "",
  city: "",
  profession: "",
  professionalCouncil: "",
  professionalRegistry: "",
  company: "",
  companyAddress: "",
  professionalTimeMonths: "",
  companyPhone: "",
  taxRegime: "",
  receiptServiceDescription: "",
  receiptCity: "",
  receiptFiscalObservation: "",
  referenceName1: "",
  referencePhone1: "",
  referenceName2: "",
  referencePhone2: "",
  observations: "",
  tradeName: "",
  corporateName: "",
  cnpj: "",
  companyMobile: "",
  companyMainPhone: "",
  companyEmail: "",
  municipalRegistration: "",
  stateRegistration: "",
  foundationDate: "",
  legalRepresentativeName: "",
  legalRepresentativeMobile: "",
  legalRepresentativeEmail: "",
  legalRepresentativeSex: "",
  legalRepresentativeBirthDate: "",
  legalRepresentativeCpf: "",
  legalRepresentativeRg: "",
  legalRepresentativeRgIssuer: "",
  legalRepresentativeRgDate: "",
  legalRepresentativeNaturality: "",
  legalRepresentativeNationality: "",
  legalRepresentativePhone: "",
};

function parseProfessionals(raw: string): ProfessionalLine[] {
  return raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [name = "", email = "", phone = ""] = line.split(",").map((part) => part.trim());
      return { name, email, phone };
    })
    .filter((item) => item.name || item.email || item.phone);
}

function onlyDigits(value: string) {
  return value.replace(/\D/g, "");
}

function whatsappUrl(referral: Referral) {
  const phoneDigits = onlyDigits(referral.phone);
  if (!phoneDigits) return "";
  const phone = phoneDigits.startsWith("55") ? phoneDigits : `55${phoneDigits}`;
  const message = [
    `Ola, ${referral.name || "profissional"}.`,
    "Estou indicando o FROID, uma plataforma de percepção clínica aumentada para apoio a sessões de saúde mental.",
    "Acesse: https://www.froid.com.br",
    referral.email ? `E-mail indicado: ${referral.email}` : "",
  ]
    .filter(Boolean)
    .join("\n");
  return `https://wa.me/${phone}?text=${encodeURIComponent(message)}`;
}

function openWhatsappReferral(referral: Referral) {
  const url = whatsappUrl(referral);
  if (!url) return;
  const opened = window.open(url, "_blank", "noopener,noreferrer");
  if (!opened) window.location.href = url;
}

function formatMoneyFromCents(cents: number, currency = "usd") {
  const locales: Record<string, string> = {
    brl: "pt-BR", usd: "en-US", eur: "fr-FR", cny: "zh-CN",
  };
  return new Intl.NumberFormat(locales[currency] || "en-US", {
    style: "currency", currency: currency.toUpperCase(),
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(Math.max(0, cents) / 100);
}

const Field: React.FC<{
  label: string;
  name: string;
  value: string;
  onChange: (name: string, value: string) => void;
  type?: string;
  required?: boolean;
  placeholder?: string;
  className?: string;
}> = ({ label, name, value, onChange, type = "text", required, placeholder, className = "" }) => (
  <label className={className}>
    <span className="text-[11px] font-black uppercase text-slate-400">
      {label}
      {required && <span className="text-red-500"> *</span>}
    </span>
    <input
      id={`onboarding-${name}`}
      name={name}
      value={value}
      onChange={(event) => onChange(name, event.target.value)}
      type={type}
      required={required}
      aria-required={required || undefined}
      placeholder={placeholder}
      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
    />
  </label>
);

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <section className="rounded-lg border border-slate-700 bg-slate-900 p-4 shadow-sm">
    <h2 className="border-b border-slate-700 pb-2 text-lg font-light text-slate-300">
      {title}
    </h2>
    <div className="mt-4 grid gap-3 md:grid-cols-3">{children}</div>
  </section>
);

export const ProfessionalOnboarding: React.FC<Props> = ({ user, onUserChange }) => {
  const navigate = useNavigate();
  const [accountType, setAccountType] = useState<"individual" | "organization">("individual");
  const [fields, setFields] = useState<Record<string, string>>({
    ...emptyFields,
    email: user?.email || "",
    companyEmail: user?.email || "",
  });
  const [professionalsRaw, setProfessionalsRaw] = useState("");
  const [baseAccessRaw, setBaseAccessRaw] = useState("");
  const [monthlyConsultations, setMonthlyConsultations] = useState(25);
  const [selectedPlan, setSelectedPlan] = useState("pro_10");
  const [billingMarket, setBillingMarket] = useState("BR");
  const [billingCurrency, setBillingCurrency] = useState("brl");
  const requestedCurrencyRef = useRef("brl");
  const [contractedSessions, setContractedSessions] = useState(0);
  const [plans, setPlans] = useState<AccessPlan[]>([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [plansError, setPlansError] = useState("");
  const [referral, setReferral] = useState<Referral>({ name: "", phone: "", email: "" });
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [lgpdAccepted, setLgpdAccepted] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [contractAccepted, setContractAccepted] = useState(false);
  const [orderSummaryAccepted, setOrderSummaryAccepted] = useState(false);
  const [legalCatalog, setLegalCatalog] = useState<LegalCatalog | null>(null);
  const [legalError, setLegalError] = useState("");
  const [autoReplenishAccepted, setAutoReplenishAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [accessStatus, setAccessStatus] = useState<FroidUser["access_status"]>(
    user?.access_status,
  );
  const feedbackRef = useRef<HTMLDivElement | null>(null);

  const professionals = useMemo(() => parseProfessionals(professionalsRaw), [professionalsRaw]);
  const availablePlans = plans;

  useEffect(() => {
    const jurisdiction = legalJurisdiction(
      ["ES", "FR", "US"].includes(billingMarket) ? billingMarket : fields.country,
    );
    loadLegalCatalog(jurisdiction).then(setLegalCatalog).catch((reason) => {
      setLegalError(reason instanceof Error ? reason.message : "Documentos jurídicos indisponíveis.");
    });
  }, [billingMarket, fields.country]);
  const requiredFieldLabels = accountType === "organization"
    ? [
        "Nome fantasia e razão social",
        "CNPJ, celular e e-mail da empresa",
        "Nome, celular, e-mail e CPF do representante legal",
        "CEP, logradouro, número e bairro",
        "Pacote comercial",
      ]
    : [
        "Nome completo, celular, e-mail e CPF",
        "CEP, logradouro, número e bairro",
        "Pacote comercial",
      ];
  const selectedPlanData =
    availablePlans.find((plan) => plan.id === selectedPlan) || availablePlans[0];
  const unitAmountCents = Math.max(0, Number(selectedPlanData?.amount_cents || 0));
  const bonusSessions = 0;
  const totalSessions = Math.max(0, contractedSessions) + bonusSessions;
  const packageTotalCents = Number(
    selectedPlanData?.total_amount_cents || unitAmountCents * Math.max(0, contractedSessions),
  );

  const loadPlans = (_currency = billingCurrency) => {
    requestedCurrencyRef.current = _currency;
    setPlansLoading(true);
    setPlansError("");
    const token = localStorage.getItem("froid_token") || "";
    fetch(apiUrl(`/api/subscriptions/plans?currency=${encodeURIComponent(_currency)}`), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (requestedCurrencyRef.current !== _currency) return;
        if (Array.isArray(data?.packages)) {
          const mapped = data.packages.map((item: any) => {
            const price = item.selected_price || item.prices?.[_currency] || {};
            const unitAmount = Number(price.unit_amount_minor || 0);
            const totalAmount = Number(price.total_amount_minor || 0);
            return {
              id: item.code,
              name: `FROID ${String(item.plan_code || "").toUpperCase()} — ${item.sessions} sessões`,
              description: `${formatMoneyFromCents(unitAmount, _currency)} por sessão`,
              session_credits: item.sessions,
              amount_cents: unitAmount,
              total_amount_cents: totalAmount,
              display_amount: formatMoneyFromCents(totalAmount, _currency),
              currency: _currency,
            };
          });
          setPlans(mapped);
          setSelectedPlan((current) => {
            const selected = mapped.find((plan: AccessPlan) => plan.id === current) || mapped[0];
            setContractedSessions(Number(selected?.session_credits || 0));
            return selected?.id || "";
          });
          if (!mapped.length) setPlansError("Nenhum pacote comercial está disponível.");
        } else {
          setPlans([]);
          setPlansError("Catálogo de pacotes inválido.");
        }
      })
      .catch(() => {
        if (requestedCurrencyRef.current !== _currency) return;
        setPlans([]);
        setPlansError("Não foi possível carregar os pacotes do FROID.");
      })
      .finally(() => {
        if (requestedCurrencyRef.current === _currency) setPlansLoading(false);
      });
  };

  useEffect(() => {
    loadPlans(billingCurrency);
  }, []);

  useEffect(() => {
    const query = window.location.hash.split("?")[1] || "";
    const returnParams = new URLSearchParams(query);
    const subscriptionResult = returnParams.get("subscription");
    const checkoutSessionId = returnParams.get("session_id") || "";
    if (subscriptionResult === "cancelled") {
      setMessage("Pagamento cancelado. Seu cadastro foi preservado.");
      return;
    }
    if (subscriptionResult !== "success") return;
    const token = localStorage.getItem("froid_token") || "";
    if (!token) return;
    let cancelled = false;
    let attempt = 0;
    setMessage("Pagamento recebido. Confirmando a liberação das sessões...");
    const refreshAccess = async () => {
      attempt += 1;
      try {
        if (checkoutSessionId) {
          const confirmation = await fetch(apiUrl("/api/subscriptions/confirm-checkout"), {
            method: "POST",
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ checkout_session_id: checkoutSessionId }),
          });
          const confirmationData = await confirmation.json().catch(() => ({}));
          if (!confirmation.ok) {
            const detail = confirmationData.detail || "Não foi possível confirmar o pagamento.";
            const awaitingStripe = confirmation.status === 409
              && String(detail).toLowerCase().includes("ainda não confirmado");
            if (!awaitingStripe) {
              setError(detail);
              setMessage("Pagamento não liberado. Não faça uma nova cobrança.");
              return;
            }
          }
        }
        const response = await fetch(apiUrl("/api/auth/me"), {
          headers: { Authorization: `Bearer ${token}` },
        });
        const refreshed = response.ok ? await response.json() : null;
        if (cancelled) return;
        if (refreshed?.access_status) {
          setAccessStatus(refreshed.access_status);
          localStorage.setItem("froid_user", JSON.stringify(refreshed));
          onUserChange(refreshed);
        }
        if (refreshed?.access_status?.manual_approval_pending) {
          setMessage("Pagamento confirmado. Seu cadastro aguarda aprovação manual do FROID.");
          return;
        }
        if (refreshed && !refreshed.access_status?.onboarding_required) {
          window.location.replace(`${publicAppUrl()}/#/dashboard`);
          return;
        }
      } catch (confirmationError: any) {
        if (!cancelled && attempt >= 12) {
          setError(confirmationError?.message || "Não foi possível confirmar o pagamento.");
        }
      }
      if (!cancelled && attempt < 12) {
        window.setTimeout(() => void refreshAccess(), 1500);
      } else if (!cancelled) {
        setMessage("Não refaça o pagamento. A cobrança foi recebida, mas a liberação requer conferência.");
      }
    };
    void refreshAccess();
    return () => {
      cancelled = true;
    };
  }, [navigate, onUserChange]);

  const changeBillingMarket = (marketCode: string) => {
    const market = billingMarkets.find((item) => item.code === marketCode) || billingMarkets[0];
    setBillingMarket(market.code);
    setBillingCurrency(market.currency);
    setPlans([]);
    setContractedSessions(0);
    loadPlans(market.currency);
  };

  useEffect(() => {
    const token = localStorage.getItem("froid_token");
    if (!token) return;
    fetch(apiUrl("/api/professional/profile"), {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.access_status) setAccessStatus(data.access_status);
        const profile = data?.profile;
        if (!profile) return;
        setAccountType(profile.account_type === "organization" ? "organization" : "individual");
        setMonthlyConsultations(Number(profile.monthly_consultations || 25));
        setLgpdAccepted(Boolean(profile.lgpd_acknowledged));
        setFields({
          ...emptyFields,
          ...(profile.profile_fields || {}),
          fullName: profile.profile_fields?.fullName || profile.owner_name || user?.name || "",
          email: profile.profile_fields?.email || user?.email || "",
          phone: profile.profile_fields?.phone || profile.phone || "",
          cpf: profile.profile_fields?.cpf || profile.document || "",
          corporateName: profile.profile_fields?.corporateName || profile.organization_name || "",
          cnpj: profile.profile_fields?.cnpj || profile.organization_document || "",
          companyEmail: profile.profile_fields?.companyEmail || user?.email || "",
        });
        if (Array.isArray(profile.professionals)) {
          setProfessionalsRaw(
            profile.professionals
              .map((item: ProfessionalLine) => [item.name, item.email, item.phone].filter(Boolean).join(", "))
              .join("\n"),
          );
        }
        if (Array.isArray(profile.patient_base_access)) {
          setBaseAccessRaw(profile.patient_base_access.join("\n"));
        }
        if (Array.isArray(profile.referrals)) {
          setReferrals(profile.referrals);
        }
      })
      .catch(() => undefined);
  }, [user?.email, user?.name]);

  const updateField = (name: string, value: string) => {
    setFields((prev) => ({ ...prev, [name]: value }));
  };

  const logoutToLogin = () => {
    localStorage.removeItem("froid_token");
    localStorage.removeItem("froid_user");
    onUserChange(null);
    navigate("/login", { replace: true });
  };

  const verifyManualApproval = async () => {
    const token = localStorage.getItem("froid_token") || "";
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(apiUrl("/api/auth/me"), {
        headers: { Authorization: `Bearer ${token}` },
      });
      const refreshed = response.ok ? await response.json() : null;
      if (!response.ok || !refreshed) throw new Error("Não foi possível verificar a aprovação.");
      setAccessStatus(refreshed.access_status);
      localStorage.setItem("froid_user", JSON.stringify(refreshed));
      onUserChange(refreshed);
      if (!refreshed.access_status?.onboarding_required) {
        window.location.replace(`${publicAppUrl()}/#/dashboard`);
        return;
      }
      setMessage("Seu cadastro continua aguardando aprovação manual do FROID.");
    } catch (verificationError: any) {
      setError(verificationError?.message || "Falha ao verificar a aprovação.");
    } finally {
      setLoading(false);
    }
  };

  const selectPlan = (plan: AccessPlan) => {
    setSelectedPlan(plan.id);
    setContractedSessions(Number(plan.session_credits || 1));
  };

  const addReferral = () => {
    if (!referral.name.trim() && !referral.phone.trim() && !referral.email.trim()) return;
    setReferrals((prev) => [referral, ...prev].slice(0, 20));
    setReferral({ name: "", phone: "", email: "" });
  };

  const openReferralWhatsapp = () => {
    if (!referral.phone.trim()) return;
    openWhatsappReferral(referral);
  };

  const validateForm = (): ValidationIssue | null => {
    const requiredFields =
      accountType === "organization"
        ? [
            ["Nome fantasia", "tradeName", fields.tradeName],
            ["Razão social", "corporateName", fields.corporateName],
            ["CNPJ", "cnpj", fields.cnpj],
            ["Celular da empresa", "companyMobile", fields.companyMobile],
            ["E-mail da empresa", "companyEmail", fields.companyEmail],
            ["Nome do representante legal", "legalRepresentativeName", fields.legalRepresentativeName],
            ["Celular do representante legal", "legalRepresentativeMobile", fields.legalRepresentativeMobile],
            ["E-mail do representante legal", "legalRepresentativeEmail", fields.legalRepresentativeEmail],
            ["CPF do representante legal", "legalRepresentativeCpf", fields.legalRepresentativeCpf],
          ]
        : [
            ["Nome completo", "fullName", fields.fullName],
            ["Telefone celular", "mobile", fields.mobile],
            ["E-mail", "email", fields.email],
            ["Número da licença médica", "professionalRegistry", fields.professionalRegistry],
          ];
    // Fase de testes: endereço não é mais exigido no cadastro reduzido.
    const addressFields: Array<[string, string, string]> = [];
    const missing = [...requiredFields, ...addressFields].find(([, , value]) => !String(value || "").trim());
    if (missing) {
      return { message: `Preencha o campo obrigatório: ${missing[0]}.`, target: `onboarding-${missing[1]}` };
    }
    const emailField = accountType === "organization"
      ? ["E-mail da empresa", "companyEmail", fields.companyEmail]
      : ["E-mail", "email", fields.email];
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(emailField[2] || "").trim())) {
      return { message: `Informe um ${emailField[0]} válido.`, target: `onboarding-${emailField[1]}` };
    }
    if (legalCatalog?.acceptance_required && !lgpdAccepted) {
      return { message: "Aceite o aviso de privacidade e responsabilidade profissional para continuar.", target: "lgpd-consent" };
    }
    if (legalCatalog?.acceptance_required && (!termsAccepted || !contractAccepted)) {
      return { message: "Leia e aceite os termos e o contrato de licença aplicável.", target: "legal-contract-consent" };
    }
    if (legalCatalog?.acceptance_required && !orderSummaryAccepted) {
      return { message: "Confirme o resumo comercial desta contratação.", target: "order-summary-consent" };
    }
    if (legalCatalog?.acceptance_required && (!legalCatalog.supplier.configured || legalError)) {
      return { message: legalError || "Identificação jurídica do fornecedor indisponível.", target: "legal-contract-consent" };
    }
    if (plansLoading) {
      return { message: "Aguarde o carregamento dos pacotes comerciais.", target: "planos" };
    }
    if (plansError) {
      return { message: `${plansError} Tente carregar novamente.`, target: "reload-plans" };
    }
    if (!selectedPlanData || contractedSessions < 1) {
      return { message: "Selecione um pacote comercial válido.", target: "planos" };
    }
    return null;
  };

  const focusValidationTarget = (target?: string) => {
    window.requestAnimationFrame(() => {
      const element = target ? document.getElementById(target) : feedbackRef.current;
      element?.scrollIntoView({ behavior: "smooth", block: "center" });
      if (element instanceof HTMLElement && typeof element.focus === "function") {
        element.focus({ preventScroll: true });
      }
    });
  };

  const saveAndCheckout = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage("Verificando as informações obrigatórias...");
    const validationIssue = validateForm();
    if (validationIssue) {
      setError(validationIssue.message);
      setMessage("");
      focusValidationTarget(validationIssue.target);
      return;
    }
    const token = localStorage.getItem("froid_token");
    if (!token) {
      navigate("/login");
      return;
    }

    setLoading(true);
    setError("");
    setMessage("");
    try {
      const patientBaseAccess = baseAccessRaw
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
      const allReferrals = referral.name || referral.phone || referral.email ? [referral, ...referrals] : referrals;

      const profilePayload = {
        account_type: accountType,
        owner_name:
          accountType === "organization"
            ? fields.legalRepresentativeName || fields.corporateName
            : fields.fullName,
        email: user?.email,
        document: accountType === "organization" ? fields.cnpj : fields.cpf,
        phone: accountType === "organization" ? fields.companyMainPhone || fields.companyMobile : fields.phone || fields.mobile,
        organization_name: fields.corporateName,
        organization_document: fields.cnpj,
        professionals,
        patient_base_access: patientBaseAccess,
        referrals: allReferrals,
        profile_fields: fields,
        lgpd_acknowledged: lgpdAccepted,
        lgpd_acknowledged_at: lgpdAccepted ? new Date().toISOString() : "",
        monthly_consultations: monthlyConsultations,
        legal_jurisdiction: legalJurisdiction(
          ["ES", "FR", "US"].includes(billingMarket) ? billingMarket : fields.country,
        ),
        legal_acceptances: legalCatalog ? {
          terms: acceptanceFor(legalCatalog.documents.terms, termsAccepted),
          privacy: acceptanceFor(legalCatalog.documents.privacy, lgpdAccepted),
          [accountType === "organization" ? "organization_contract" : "professional_contract"]:
            acceptanceFor(
              legalCatalog.documents[
                accountType === "organization" ? "organization_contract" : "professional_contract"
              ],
              contractAccepted,
            ),
        } : {},
      };

      const profileRes = await fetch(apiUrl("/api/professional/profile"), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(profilePayload),
      });
      const profileText = await profileRes.text();
      const profileData = profileText ? JSON.parse(profileText) : {};
      if (!profileRes.ok) throw new Error(profileData.detail || "Falha ao salvar cadastro");
      if (profileData?.access_status) {
        let storedUser: Record<string, unknown> = {};
        try {
          storedUser = JSON.parse(localStorage.getItem("froid_user") || "{}");
        } catch {
          storedUser = {};
        }
        const nextUser = {
          ...storedUser,
          ...user,
          email: user?.email || String(storedUser.email || ""),
          name: user?.name || String(storedUser.name || ""),
          access_status: profileData.access_status,
        } as FroidUser;
        localStorage.setItem("froid_user", JSON.stringify(nextUser));
        onUserChange(nextUser);
      }
      setMessage("Cadastro salvo. Encaminhando para o pagamento...");

      const checkoutRes = await fetch(apiUrl("/api/subscriptions/checkout"), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          package_code: selectedPlan,
          currency: billingCurrency,
          auto_replenish_consent: autoReplenishAccepted,
          order_summary_accepted: orderSummaryAccepted,
          checkout_context: "onboarding",
          base_url: publicAppUrl(),
        }),
      });
      const checkoutText = await checkoutRes.text();
      const checkoutData = checkoutText ? JSON.parse(checkoutText) : {};
      if (!checkoutRes.ok) throw new Error(checkoutData.detail || "Falha ao iniciar pagamento");
      if (checkoutData.status === "stripe_not_configured") {
        setMessage(checkoutData.message || "Cadastro salvo. Stripe ainda não configurado.");
      }
      const nextUrl = checkoutData.checkout_url || `${publicAppUrl()}/#/dashboard`;
      if (checkoutData.status === "free_access" || checkoutData.status === "stripe_not_configured") {
        navigate("/dashboard", { replace: true });
      } else {
        window.location.assign(nextUrl);
      }
    } catch (err: any) {
      setError(err.message || "Falha ao concluir cadastro");
    } finally {
      setLoading(false);
    }
  };

  if (
    accessStatus?.manual_approval_pending
    && ["paid", "active", "trialing"].includes(String(accessStatus.payment_status || ""))
  ) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-100">
        <main className="w-full max-w-xl rounded-2xl border border-cyan-900 bg-slate-900 p-7 shadow-2xl">
          <p className="text-xs font-black uppercase tracking-[0.3em] text-emerald-300">
            Pagamento confirmado
          </p>
          <h1 className="mt-3 text-2xl font-black">Cadastro aguardando aprovação FROID</h1>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            Seus dados e créditos estão preservados. Durante esta fase de testes, o acesso
            operacional é liberado pessoalmente pelo responsável do FROID após a conferência
            do cadastro.
          </p>
          <p className="mt-4 rounded-lg border border-amber-800 bg-amber-950/40 px-4 py-3 text-sm font-bold text-amber-100">
            Não realize outro pagamento. A compra já foi confirmada.
          </p>
          {message && <p className="mt-4 text-sm text-cyan-200">{message}</p>}
          {error && <p className="mt-4 text-sm font-bold text-red-300">{error}</p>}
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              disabled={loading}
              onClick={() => void verifyManualApproval()}
              className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-black text-white hover:bg-cyan-600 disabled:opacity-50"
            >
              {loading ? "Verificando..." : "Verificar aprovação"}
            </button>
            <button
              type="button"
              onClick={logoutToLogin}
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-black text-slate-200 hover:bg-slate-800"
            >
              Sair
            </button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <header className="border-b border-slate-700 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
          <Link to="/" className="text-sm font-black tracking-[0.35em] text-cyan-700">
            FROID
          </Link>
          <div className="flex items-center gap-2">
            <Link to="/dashboard" className="rounded-md border border-slate-700 px-3 py-2 text-xs font-black">
              Dashboard
            </Link>
            {user ? (
              <button
                type="button"
                onClick={logoutToLogin}
                className="rounded-md bg-slate-950 px-3 py-2 text-xs font-black text-white"
              >
                Sair
              </button>
            ) : (
              <Link to="/login" className="rounded-md bg-slate-950 px-3 py-2 text-xs font-black text-white">
                Login
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-5 py-8">
        <div className="mb-6">
          <p className="text-xs font-black uppercase tracking-[0.24em] text-cyan-700">
            Cadastro profissional
          </p>
          <h1 className="mt-2 text-3xl font-black">Ficha cadastral FROID</h1>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-300">
            Complete o cadastro da pessoa física ou jurídica, indique usuários,
            aceite as condições LGPD e selecione o plano para liberar o dashboard clínico.
          </p>
          <p className="mt-3 rounded-lg border border-cyan-800 bg-cyan-950/60 px-3 py-2 text-xs font-semibold text-cyan-100">
            Os campos marcados com <span className="font-black text-red-300">*</span>, os aceites jurídicos vigentes e a seleção de um pacote são obrigatórios.
          </p>
        </div>

        <form noValidate onSubmit={saveAndCheckout} className="grid gap-5 xl:grid-cols-[1fr_360px]">
          <div className="space-y-4">
            {accountType === "organization" && (
              <Section title="Informações da Empresa">
                <Field label="Nome fantasia" name="tradeName" value={fields.tradeName} onChange={updateField} required />
                <Field label="Razao social" name="corporateName" value={fields.corporateName} onChange={updateField} required />
                <Field label="CNPJ" name="cnpj" value={fields.cnpj} onChange={updateField} required />
                <Field label="Celular" name="companyMobile" value={fields.companyMobile} onChange={updateField} required />
                <Field label="Telefone" name="companyMainPhone" value={fields.companyMainPhone} onChange={updateField} />
                <Field label="E-mail" name="companyEmail" value={fields.companyEmail} onChange={updateField} type="email" required />
                <Field label="Inscrição municipal" name="municipalRegistration" value={fields.municipalRegistration} onChange={updateField} />
                <Field label="Inscrição estadual" name="stateRegistration" value={fields.stateRegistration} onChange={updateField} />
                <Field label="Fundacao" name="foundationDate" value={fields.foundationDate} onChange={updateField} type="date" />
              </Section>
            )}

            {/* Fase de testes: cadastro reduzido ao essencial. */}
            <Section title="Dados do profissional">
              <Field label="Nome completo" name="fullName" value={fields.fullName} onChange={updateField} required />
              <Field label="E-mail" name="email" value={fields.email} onChange={updateField} type="email" required />
              <Field label="Telefone celular" name="mobile" value={fields.mobile} onChange={updateField} required />
              <Field label="Número da licença médica" name="professionalRegistry" value={fields.professionalRegistry} onChange={updateField} placeholder="CRM / CRP" required />
            </Section>

            {accountType === "organization" && (
              <section className="rounded-lg border border-slate-700 bg-slate-900 p-4 shadow-sm">
                <h2 className="border-b border-slate-700 pb-2 text-lg font-light text-slate-300">
                  Usuários e acesso a base de pacientes
                </h2>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <label>
                    <span className="text-[11px] font-black uppercase text-slate-400">
                      Profissionais autorizados
                    </span>
                    <textarea
                      value={professionalsRaw}
                      onChange={(e) => setProfessionalsRaw(e.target.value)}
                      rows={5}
                      placeholder="Nome, email, telefone&#10;Nome, email, telefone"
                      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500"
                    />
                  </label>
                  <label>
                    <span className="text-[11px] font-black uppercase text-slate-400">
                      Podem acessar a base de pacientes
                    </span>
                    <textarea
                      value={baseAccessRaw}
                      onChange={(e) => setBaseAccessRaw(e.target.value)}
                      rows={5}
                      placeholder="um email por linha"
                      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500"
                    />
                  </label>
                </div>
              </section>
            )}

            <section className="rounded-lg border border-slate-700 bg-slate-900 p-4 shadow-sm">
              <h2 className="border-b border-slate-700 pb-2 text-lg font-light text-slate-300">
                Indicacao de novo usuário
              </h2>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <label>
                  <span className="text-[11px] font-black uppercase text-slate-400">Nome completo</span>
                  <input
                    value={referral.name}
                    onChange={(event) => setReferral((prev) => ({ ...prev, name: event.target.value }))}
                    className="mt-1 w-full rounded-md border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
                  />
                </label>
                <label>
                  <span className="text-[11px] font-black uppercase text-slate-400">Celular</span>
                  <input
                    value={referral.phone}
                    onChange={(event) => setReferral((prev) => ({ ...prev, phone: event.target.value }))}
                    className="mt-1 w-full rounded-md border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
                  />
                </label>
                <label>
                  <span className="text-[11px] font-black uppercase text-slate-400">E-mail</span>
                  <input
                    value={referral.email}
                    onChange={(event) => setReferral((prev) => ({ ...prev, email: event.target.value }))}
                    type="email"
                    className="mt-1 w-full rounded-md border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
                  />
                </label>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={addReferral}
                  className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-black text-slate-300 hover:bg-slate-800"
                >
                  Adicionar indicacao
                </button>
                <button
                  type="button"
                  onClick={openReferralWhatsapp}
                  disabled={!referral.phone.trim()}
                  className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-black text-white hover:bg-emerald-700 disabled:opacity-40"
                >
                  Compor WhatsApp
                </button>
              </div>
              {referrals.length > 0 && (
                <div className="mt-3 grid gap-2 text-xs text-slate-300">
                  {referrals.map((item, index) => (
                    <div
                      key={`${item.email}-${item.phone}-${index}`}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                    >
                      <span>
                        <strong className="text-slate-200">{item.name || "Sem nome"}</strong>
                        {" - "}
                        {item.phone || "sem celular"}
                        {" - "}
                        {item.email || "sem email"}
                      </span>
                      <button
                        type="button"
                        onClick={() => openWhatsappReferral(item)}
                        disabled={!item.phone.trim()}
                        className="rounded-md bg-emerald-600 px-3 py-1.5 text-[11px] font-black text-white hover:bg-emerald-700 disabled:opacity-40"
                      >
                        WhatsApp
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="rounded-lg border border-slate-700 bg-slate-900 p-4 shadow-sm">
              <h2 className="border-b border-slate-700 pb-2 text-lg font-light text-slate-300">
                Observações e responsabilidade LGPD
              </h2>
              <textarea
                value={fields.observations}
                onChange={(event) => updateField("observations", event.target.value)}
                rows={4}
                placeholder="Observações cadastrais relevantes..."
                className="mt-4 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500"
              />
              <div className="mt-4">
                <LgpdNotice audience="professional" />
              </div>
              <p className={`mt-4 rounded-lg border p-3 text-xs font-bold leading-5 ${
                legalCatalog?.acceptance_required
                  ? "border-amber-700 bg-amber-950/60 text-amber-100"
                  : "border-cyan-800 bg-cyan-950/40 text-cyan-100"
              }`}>
                {legalCatalog?.acceptance_required
                  ? "Os documentos abaixo são obrigatórios nesta localidade. Leia e aceite para concluir o cadastro."
                  : "Os documentos abaixo são apresentados para sua leitura e permanecem disponíveis integralmente. Nesta fase inicial, o não aceite não impede o cadastro, o pagamento nem o início da operação."}
              </p>
              <label className="mt-4 flex gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs font-bold leading-5 text-amber-950">
                <input
                  id="lgpd-consent"
                  name="lgpd_consent"
                  type="checkbox"
                  checked={lgpdAccepted}
                  onChange={(event) => setLgpdAccepted(event.target.checked)}
                  required={Boolean(legalCatalog?.acceptance_required)}
                  aria-required={legalCatalog?.acceptance_required || undefined}
                  className="mt-1"
                />
                <span>
                  Li e compreendi a <a className="underline" href="#/privacidade" target="_blank" rel="noreferrer">Política de Privacidade</a>,
                  incluindo tratamento de dados sensíveis, fornecedores e transferência internacional.
                </span>
              </label>
              <div id="legal-contract-consent" className="mt-3 space-y-2">
                <label className="flex gap-3 rounded-lg border border-slate-700 bg-slate-950 p-3 text-xs font-bold leading-5 text-slate-200">
                  <input type="checkbox" checked={termsAccepted} onChange={(event) => setTermsAccepted(event.target.checked)} className="mt-1" />
                  <span>Li e aceito os <a className="text-cyan-200 underline" href="#/termos" target="_blank" rel="noreferrer">Termos Gerais de Uso</a>, inclusive limites clínicos, segurança e propriedade intelectual.</span>
                </label>
                <label className="flex gap-3 rounded-lg border border-slate-700 bg-slate-950 p-3 text-xs font-bold leading-5 text-slate-200">
                  <input type="checkbox" checked={contractAccepted} onChange={(event) => setContractAccepted(event.target.checked)} className="mt-1" />
                  <span>
                    Li e aceito o {accountType === "organization" ? "Contrato para Clínica ou Organização" : "Contrato de Licença para Profissional"}{" "}
                    (<a className="text-cyan-200 underline" href={accountType === "organization" ? "#/contrato-clinica" : "#/contrato-profissional"} target="_blank" rel="noreferrer">abrir versão integral</a>).
                  </span>
                </label>
              </div>
              {legalCatalog && <p className="mt-2 text-[10px] text-slate-500">Documentos versão {legalCatalog.version}. O conteúdo integral e seu hash serão vinculados ao aceite.</p>}
              {legalError && <p className="mt-2 text-xs font-bold text-red-300">{legalError}</p>}
            </section>
          </div>

          <aside id="planos" className="h-fit rounded-lg border border-slate-700 bg-slate-900 p-5 shadow-sm xl:sticky xl:top-4">
            <h2 className="text-lg font-black">Plano e pagamento</h2>
            <p className="mt-1 text-sm text-slate-400">
              O pagamento será processado pelo Stripe e depois o acesso retorna ao dashboard.
            </p>

            <div className="mt-4 rounded-lg border border-slate-700 bg-slate-950 p-3">
              <p className="text-xs font-black uppercase tracking-wide text-cyan-200">
                Informações obrigatórias
              </p>
              <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-slate-300">
                {requiredFieldLabels.map((label) => <li key={label}>{label}</li>)}
              </ul>
            </div>

            <label className="mt-4 block">
              <span className="text-[11px] font-black uppercase text-slate-400">
                Mercado / moeda
              </span>
              <select
                value={billingMarket}
                onChange={(event) => changeBillingMarket(event.target.value)}
                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
              >
                {billingMarkets.map((market) => (
                  <option key={market.code} value={market.code}>
                    {market.label} - {market.currency.toUpperCase()}
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-[11px] text-slate-500">
                {billingMarkets.find((market) => market.code === billingMarket)?.note}
              </span>
            </label>

            <label className="mt-4 block">
              <span className="text-[11px] font-black uppercase text-slate-400">
                Consultas mensais estimadas
              </span>
              <input
                value={monthlyConsultations}
                onChange={(e) => setMonthlyConsultations(Number(e.target.value || 0))}
                type="number"
                min={1}
                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
              />
            </label>

            <div className="mt-4 grid gap-3 rounded-lg border border-slate-700 bg-slate-950 p-3">
              <label className="block">
                <span className="text-[11px] font-black uppercase text-slate-400">
                  Número de sessões contratadas
                </span>
                <input
                  value={contractedSessions}
                  type="number"
                  min={1}
                  readOnly
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
                />
              </label>
              <div className="rounded-md border border-cyan-200 bg-cyan-50 p-3 text-xs font-bold leading-5 text-cyan-950">
                <p>Valor unitario do plano: {formatMoneyFromCents(unitAmountCents, billingCurrency)}</p>
                <p>Total do pacote: {formatMoneyFromCents(packageTotalCents, billingCurrency)}</p>
                <p>Sessões contratadas: {contractedSessions}</p>
                <p>Total liberado: {totalSessions} sessões</p>
                <p>Moeda do checkout: {billingCurrency.toUpperCase()}</p>
              </div>
            </div>

            <label id="order-summary-consent" className="mt-4 flex gap-3 rounded-lg border border-amber-700 bg-amber-950/60 p-3 text-xs font-bold leading-5 text-amber-100">
              <input
                type="checkbox"
                checked={orderSummaryAccepted}
                onChange={(event) => setOrderSummaryAccepted(event.target.checked)}
                className="mt-1"
              />
              <span>
                Confirmo o pacote selecionado, a quantidade de sessões, a moeda e o valor total exibidos acima. Esta confirmação será vinculada à ordem enviada ao Stripe.
              </span>
            </label>

            <label className="mt-4 flex gap-3 rounded-lg border border-cyan-700 bg-cyan-950 p-3 text-xs font-bold leading-5 text-cyan-100">
              <input
                id="auto-replenish-consent"
                name="auto_replenish_consent"
                type="checkbox"
                checked={autoReplenishAccepted}
                onChange={(event) => setAutoReplenishAccepted(event.target.checked)}
                className="mt-1"
              />
              <span>
                  <strong>Opcional:</strong> autorizo o FROID a salvar o método de pagamento e recomprar automaticamente
                o mesmo pacote quando o saldo de sessões chegar a zero, na mesma moeda e pelo
                valor total informado nesta contratação. Qualquer alteração exigirá nova autorização.
              </span>
            </label>

            <div className="mt-4 space-y-3">
              {plansLoading && (
                <p className="text-sm font-bold text-slate-400">Carregando pacotes...</p>
              )}
              {plansError && (
                <div className="space-y-2 rounded-lg border border-red-800 bg-red-950/50 p-3">
                  <p className="text-sm font-bold text-red-200">{plansError}</p>
                  <button
                    id="reload-plans"
                    type="button"
                    onClick={() => loadPlans(billingCurrency)}
                    className="rounded-md border border-red-700 px-3 py-2 text-xs font-black text-red-100 hover:bg-red-900"
                  >
                    Tentar carregar novamente
                  </button>
                </div>
              )}
              {availablePlans.map((plan) => (
                <label
                  key={plan.id}
                  className={`block cursor-pointer rounded-lg border p-4 ${
                    selectedPlan === plan.id
                      ? "border-cyan-500 bg-cyan-950"
                      : "border-slate-700 bg-slate-900"
                  }`}
                >
                  <input
                    type="radio"
                    name="plan"
                    checked={selectedPlan === plan.id}
                    onChange={() => selectPlan(plan)}
                    className="sr-only"
                  />
                  <span className="block text-sm font-black text-slate-100">{plan.name}</span>
                  <span className="mt-1 block text-2xl font-black text-cyan-200">{plan.display_amount}</span>
                  <span className="mt-1 block text-xs text-slate-400">
                    {plan.session_credits} sessões - {plan.description}
                  </span>
                </label>
              ))}
            </div>

            <div ref={feedbackRef} tabIndex={-1} aria-live="assertive">
              {error && (
                <p role="alert" className="mt-4 rounded-lg border border-red-700 bg-red-950/70 p-3 text-sm font-bold text-red-100">
                  {error}
                </p>
              )}
              {message && (
                <p role="status" className="mt-4 rounded-lg border border-amber-700 bg-amber-950/60 p-3 text-sm font-bold text-amber-100">
                  {message}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              aria-busy={loading}
              className="mt-5 w-full rounded-lg bg-cyan-700 px-4 py-3 text-sm font-black text-white hover:bg-cyan-600 focus:outline-none focus:ring-2 focus:ring-cyan-300 disabled:cursor-wait disabled:opacity-60"
            >
              {loading ? "Processando..." : "Enviar informações e pagar"}
            </button>
          </aside>
        </form>
      </main>
    </div>
  );
};


