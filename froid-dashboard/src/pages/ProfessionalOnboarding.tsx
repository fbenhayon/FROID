import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiUrl, publicAppUrl } from "../lib/api";
import type { FroidUser } from "../App";
import { LgpdNotice } from "../components/legal/LgpdNotice";

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
  { code: "US", label: "Estados Unidos / internacional", currency: "usd", note: "Pacotes comerciais cobrados em dólares americanos." },
  { code: "EU", label: "União Europeia", currency: "eur", note: "Pacotes comerciais cobrados em euros." },
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
      value={value}
      onChange={(event) => onChange(name, event.target.value)}
      type={type}
      required={required}
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
  const [autoReplenishAccepted, setAutoReplenishAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const professionals = useMemo(() => parseProfessionals(professionalsRaw), [professionalsRaw]);
  const availablePlans = plans;
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
    const subscriptionResult = new URLSearchParams(query).get("subscription");
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
        const response = await fetch(apiUrl("/api/auth/me"), {
          headers: { Authorization: `Bearer ${token}` },
        });
        const refreshed = response.ok ? await response.json() : null;
        if (cancelled) return;
        if (refreshed && !refreshed.access_status?.onboarding_required) {
          localStorage.setItem("froid_user", JSON.stringify(refreshed));
          onUserChange(refreshed);
          navigate("/dashboard", { replace: true });
          return;
        }
      } catch {
        // Stripe may deliver the signed webhook shortly after the browser returns.
      }
      if (!cancelled && attempt < 12) {
        window.setTimeout(() => void refreshAccess(), 1500);
      } else if (!cancelled) {
        setMessage("Pagamento em conciliação. Atualize esta página em instantes.");
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

  const validateForm = () => {
    const requiredFields =
      accountType === "organization"
        ? [
            ["Razao social", fields.corporateName],
            ["CNPJ", fields.cnpj],
            ["Celular da empresa", fields.companyMobile],
            ["E-mail da empresa", fields.companyEmail],
            ["Nome do representante legal", fields.legalRepresentativeName],
            ["Celular do representante legal", fields.legalRepresentativeMobile],
            ["E-mail do representante legal", fields.legalRepresentativeEmail],
            ["CPF do representante legal", fields.legalRepresentativeCpf],
          ]
        : [
            ["Nome completo", fields.fullName],
            ["Celular", fields.mobile],
            ["E-mail", fields.email],
            ["CPF", fields.cpf],
          ];
    const addressFields = [
      ["CEP", fields.postalCode],
      ["Logradouro", fields.street],
      ["Número", fields.number],
      ["Bairro", fields.district],
    ];
    const missing = [...requiredFields, ...addressFields].find(([, value]) => !String(value || "").trim());
    if (missing) return `Preencha o campo obrigatorio: ${missing[0]}.`;
    if (!lgpdAccepted) return "Aceite os termos LGPD para continuar.";
    if (!autoReplenishAccepted) return "Autorize a recarga automática para continuar.";
    if (!selectedPlanData || contractedSessions < 1) {
      return "Selecione um pacote comercial válido.";
    }
    return "";
  };

  const saveAndCheckout = async (e: React.FormEvent) => {
    e.preventDefault();
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      setMessage("");
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
          auto_replenish_consent: true,
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
            Complete o cadastro da pessoa física ou juridica, indique usuários,
            aceite as condiÃ§Ãµes LGPD e selecione o plano para liberar o dashboard clínico.
          </p>
        </div>

        <form noValidate onSubmit={saveAndCheckout} className="grid gap-5 xl:grid-cols-[1fr_360px]">
          <div className="space-y-4">
            <section className="rounded-lg border border-slate-700 bg-slate-900 p-4 shadow-sm">
              <span className="text-[11px] font-black uppercase text-slate-400">Tipo de cadastro</span>
              <div className="mt-2 flex flex-wrap gap-3 text-sm font-bold">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    checked={accountType === "individual"}
                    onChange={() => setAccountType("individual")}
                  />
                  Pessoa Física
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    checked={accountType === "organization"}
                    onChange={() => setAccountType("organization")}
                  />
                  Pessoa Juridica
                </label>
              </div>
            </section>

            {accountType === "organization" && (
              <Section title="Informações da Empresa">
                <Field label="Nome fantasia" name="tradeName" value={fields.tradeName} onChange={updateField} required />
                <Field label="Razao social" name="corporateName" value={fields.corporateName} onChange={updateField} required />
                <Field label="CNPJ" name="cnpj" value={fields.cnpj} onChange={updateField} required />
                <Field label="Celular" name="companyMobile" value={fields.companyMobile} onChange={updateField} required />
                <Field label="Telefone" name="companyMainPhone" value={fields.companyMainPhone} onChange={updateField} />
                <Field label="E-mail" name="companyEmail" value={fields.companyEmail} onChange={updateField} type="email" required />
                <Field label="InscriÃ§Ã£o municipal" name="municipalRegistration" value={fields.municipalRegistration} onChange={updateField} />
                <Field label="InscriÃ§Ã£o estadual" name="stateRegistration" value={fields.stateRegistration} onChange={updateField} />
                <Field label="Fundacao" name="foundationDate" value={fields.foundationDate} onChange={updateField} type="date" />
              </Section>
            )}

            <Section title={accountType === "organization" ? "Dados Pessoais do Representante Legal" : "Dados Pessoais"}>
              <Field label="Nome completo" name={accountType === "organization" ? "legalRepresentativeName" : "fullName"} value={accountType === "organization" ? fields.legalRepresentativeName : fields.fullName} onChange={updateField} required />
              <Field label="Celular" name={accountType === "organization" ? "legalRepresentativeMobile" : "mobile"} value={accountType === "organization" ? fields.legalRepresentativeMobile : fields.mobile} onChange={updateField} required />
              <Field label="E-mail" name={accountType === "organization" ? "legalRepresentativeEmail" : "email"} value={accountType === "organization" ? fields.legalRepresentativeEmail : fields.email} onChange={updateField} type="email" required />
              <Field label="Sexo" name={accountType === "organization" ? "legalRepresentativeSex" : "sex"} value={accountType === "organization" ? fields.legalRepresentativeSex : fields.sex} onChange={updateField} />
              <Field label="Data de nascimento" name={accountType === "organization" ? "legalRepresentativeBirthDate" : "birthDate"} value={accountType === "organization" ? fields.legalRepresentativeBirthDate : fields.birthDate} onChange={updateField} type="date" />
              <Field label="CPF" name={accountType === "organization" ? "legalRepresentativeCpf" : "cpf"} value={accountType === "organization" ? fields.legalRepresentativeCpf : fields.cpf} onChange={updateField} required />
              <Field label="RG" name={accountType === "organization" ? "legalRepresentativeRg" : "rg"} value={accountType === "organization" ? fields.legalRepresentativeRg : fields.rg} onChange={updateField} />
              <Field label="Emissor RG" name={accountType === "organization" ? "legalRepresentativeRgIssuer" : "rgIssuer"} value={accountType === "organization" ? fields.legalRepresentativeRgIssuer : fields.rgIssuer} onChange={updateField} />
              {accountType === "organization" && (
                <Field label="Emissao RG" name="legalRepresentativeRgDate" value={fields.legalRepresentativeRgDate} onChange={updateField} type="date" />
              )}
              <Field label="Naturalidade" name={accountType === "organization" ? "legalRepresentativeNaturality" : "naturality"} value={accountType === "organization" ? fields.legalRepresentativeNaturality : fields.naturality} onChange={updateField} />
              <Field label="Nacionalidade" name={accountType === "organization" ? "legalRepresentativeNationality" : "nationality"} value={accountType === "organization" ? fields.legalRepresentativeNationality : fields.nationality} onChange={updateField} />
              <Field label="Telefone" name={accountType === "organization" ? "legalRepresentativePhone" : "phone"} value={accountType === "organization" ? fields.legalRepresentativePhone : fields.phone} onChange={updateField} />
            </Section>

            <Section title="Informação do Endereço">
              <Field label="CEP" name="postalCode" value={fields.postalCode} onChange={updateField} required />
              <Field label="Logradouro" name="street" value={fields.street} onChange={updateField} required />
              <Field label="Número" name="number" value={fields.number} onChange={updateField} required />
              <Field label="Bairro" name="district" value={fields.district} onChange={updateField} required />
              <Field label="Complemento" name="complement" value={fields.complement} onChange={updateField} />
              <Field label="Pais" name="country" value={fields.country} onChange={updateField} />
              <Field label="Estado" name="state" value={fields.state} onChange={updateField} />
              <Field label="Cidade" name="city" value={fields.city} onChange={updateField} />
            </Section>

            <Section title="Dados fiscais para fatura e recibo">
              <Field label={accountType === "organization" ? "Atividade principal" : "Profissao"} name="profession" value={fields.profession} onChange={updateField} placeholder="Psicologa(o), Medica(o) Psiquiatra..." />
              <Field label="Conselho profissional" name="professionalCouncil" value={fields.professionalCouncil} onChange={updateField} placeholder="CRP, CRM..." />
              <Field label="Registro profissional" name="professionalRegistry" value={fields.professionalRegistry} onChange={updateField} placeholder="Número do CRP/CRM" />
              <Field label="Descricao padrão do serviço" name="receiptServiceDescription" value={fields.receiptServiceDescription} onChange={updateField} placeholder="Sessão de psicoterapia individual, consulta psiquiátrica..." />
              <Field label="Local de emissao" name="receiptCity" value={fields.receiptCity} onChange={updateField} placeholder="Cidade/UF" />
              <Field label="ObservaÃ§Ã£o fiscal padrão" name="receiptFiscalObservation" value={fields.receiptFiscalObservation} onChange={updateField} placeholder="Referência Receita Saúde/NFS-e quando aplicÃ¡vel" />
              {accountType === "organization" && (
                <Field label="Regime tributÃ¡rio" name="taxRegime" value={fields.taxRegime} onChange={updateField} />
              )}
            </Section>

            {accountType === "individual" && (
              <Section title="Dados Profissionais">
                <Field label="Empresa" name="company" value={fields.company} onChange={updateField} />
                <Field label="Endereço da empresa" name="companyAddress" value={fields.companyAddress} onChange={updateField} />
                <Field label="Tempo meses" name="professionalTimeMonths" value={fields.professionalTimeMonths} onChange={updateField} type="number" />
                <Field label="Telefone da empresa" name="companyPhone" value={fields.companyPhone} onChange={updateField} />
              </Section>
            )}

            <Section title="Referências Pessoais">
              <Field label="Nome da referência pessoal 1" name="referenceName1" value={fields.referenceName1} onChange={updateField} />
              <Field label="Contato da referência pessoal 1" name="referencePhone1" value={fields.referencePhone1} onChange={updateField} />
              <Field label="Nome da referência pessoal 2" name="referenceName2" value={fields.referenceName2} onChange={updateField} />
              <Field label="Contato da referência pessoal 2" name="referencePhone2" value={fields.referencePhone2} onChange={updateField} />
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
                ObservaÃ§Ãµes e responsabilidade LGPD
              </h2>
              <textarea
                value={fields.observations}
                onChange={(event) => updateField("observations", event.target.value)}
                rows={4}
                placeholder="ObservaÃ§Ãµes cadastrais relevantes..."
                className="mt-4 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500"
              />
              <div className="mt-4">
                <LgpdNotice audience="professional" />
              </div>
              <label className="mt-4 flex gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs font-bold leading-5 text-amber-950">
                <input
                  type="checkbox"
                  checked={lgpdAccepted}
                  onChange={(event) => setLgpdAccepted(event.target.checked)}
                  required
                  className="mt-1"
                />
                <span>
                  Li, compreendi e aceito o aviso de privacidade, responsabilidade
                  profissional, tratamento de dados pessoais e dados sensíveis nos termos
                  da LGPD, declarando possuir autorizacao e base legal para operar o FROID.
                </span>
              </label>
            </section>
          </div>

          <aside id="planos" className="h-fit rounded-lg border border-slate-700 bg-slate-900 p-5 shadow-sm xl:sticky xl:top-4">
            <h2 className="text-lg font-black">Plano e pagamento</h2>
            <p className="mt-1 text-sm text-slate-400">
              O pagamento será processado pelo Stripe e depois o acesso retorna ao dashboard.
            </p>

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

            <label className="mt-4 flex gap-3 rounded-lg border border-cyan-700 bg-cyan-950 p-3 text-xs font-bold leading-5 text-cyan-100">
              <input
                type="checkbox"
                checked={autoReplenishAccepted}
                onChange={(event) => setAutoReplenishAccepted(event.target.checked)}
                required
                className="mt-1"
              />
              <span>
                Autorizo o FROID a salvar o método de pagamento e recomprar automaticamente
                o mesmo pacote quando o saldo de sessões chegar a zero, na mesma moeda e pelo
                valor total informado nesta contratação. Qualquer alteração exigirá nova autorização.
              </span>
            </label>

            <div className="mt-4 space-y-3">
              {plansLoading && (
                <p className="text-sm font-bold text-slate-400">Carregando pacotes...</p>
              )}
              {plansError && (
                <p className="text-sm font-bold text-red-400">{plansError}</p>
              )}
              {availablePlans.map((plan) => (
                <label
                  key={plan.id}
                  className={`block cursor-pointer rounded-lg border p-4 ${
                    selectedPlan === plan.id
                      ? "border-cyan-500 bg-cyan-50"
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
                  <span className="mt-1 block text-2xl font-black text-cyan-800">{plan.display_amount}</span>
                  <span className="mt-1 block text-xs text-slate-400">
                    {plan.session_credits} sessões - {plan.description}
                  </span>
                </label>
              ))}
            </div>

            {error && <p className="mt-4 text-sm font-bold text-red-600">{error}</p>}
            {message && <p className="mt-4 text-sm font-bold text-amber-100">{message}</p>}

            <button
              disabled={
                loading || plansLoading || !selectedPlanData
                || !lgpdAccepted || !autoReplenishAccepted
              }
              className="mt-5 w-full rounded-lg bg-slate-950 px-4 py-3 text-sm font-black text-white hover:bg-slate-800 disabled:opacity-40"
            >
              {loading ? "Processando..." : "Enviar informações e pagar"}
            </button>
          </aside>
        </form>
      </main>
    </div>
  );
};


