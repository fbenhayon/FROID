import React from "react";
import { normalizeSessionLocale, type SessionLocale } from "../../lib/localization";

// Providências CONCRETAS de segurança que o FROID adota, em linguagem acessível
// e — importante — verdadeiras (refletem controles reais do código: TLS,
// criptografia autenticada Fernet/AES+HMAC de tokens e conteúdos clínicos,
// hashing de senha PBKDF2, controle de acesso por titularidade, trilha de
// auditoria, consentimento LGPD, anonimização/k-anonimato do datamart).
// Exibido no momento do cadastro para tranquilizar quem informa seus dados.

type Audience = "patient" | "professional";

type Copy = {
  title: string;
  intro: string;
  items: string[];
  footer: string;
  link: string;
};

const CONTENT: Record<Audience, Partial<Record<SessionLocale, Copy>>> = {
  patient: {
    "pt-BR": {
      title: "Como protegemos as suas informações",
      intro:
        "Seus dados de saúde são tratados como sensíveis. Estas são as providências que adotamos para mantê-los confidenciais:",
      items: [
        "Conexão criptografada (HTTPS/TLS) em toda a sessão — áudio, vídeo e dados trafegam protegidos.",
        "Informações sensíveis (transcrições, relatórios e credenciais) são guardadas cifradas, com criptografia autenticada (AES + HMAC) e chaves que podem ser rotacionadas.",
        "Acesso restrito à titularidade: apenas o seu profissional acessa os seus dados, e todo acesso fica registrado em trilha de auditoria.",
        "Nada é analisado sem o seu consentimento explícito (TCLE/LGPD) — e você pode revogá-lo a qualquer momento.",
        "Seus direitos LGPD são garantidos: acessar, corrigir e solicitar a exclusão dos seus dados quando aplicável.",
        "Estatísticas coletivas usam apenas dados anonimizados e agregados (nunca grupos pequenos) — não identificam você.",
        "Sua senha é protegida por hashing (PBKDF2-SHA256); nunca a armazenamos em texto legível.",
      ],
      footer:
        "Estas medidas descrevem controles técnicos aplicados na plataforma e não substituem a política de privacidade completa.",
      link: "Ver política de segurança e privacidade",
    },
    "en-US": {
      title: "How we protect your information",
      intro:
        "Your health data is treated as sensitive. These are the measures we take to keep it confidential:",
      items: [
        "Encrypted connection (HTTPS/TLS) throughout the session — audio, video and data travel protected.",
        "Sensitive information (transcripts, reports and credentials) is stored encrypted with authenticated encryption (AES + HMAC) and rotatable keys.",
        "Ownership-restricted access: only your professional can see your data, and every access is written to an audit trail.",
        "Nothing is analyzed without your explicit consent (informed consent/LGPD) — which you can withdraw at any time.",
        "Your data-protection rights are guaranteed: access, correction and deletion where applicable.",
        "Aggregate statistics use only anonymized, aggregated data (never small groups) — they do not identify you.",
        "Your password is protected by hashing (PBKDF2-SHA256); we never store it in readable form.",
      ],
      footer:
        "These measures describe technical controls applied in the platform and do not replace the full privacy policy.",
      link: "See security and privacy policy",
    },
    "es-ES": {
      title: "Cómo protegemos su información",
      intro:
        "Sus datos de salud se tratan como sensibles. Estas son las medidas que adoptamos para mantenerlos confidenciales:",
      items: [
        "Conexión cifrada (HTTPS/TLS) durante toda la sesión — audio, vídeo y datos viajan protegidos.",
        "La información sensible (transcripciones, informes y credenciales) se almacena cifrada con cifrado autenticado (AES + HMAC) y claves rotables.",
        "Acceso restringido a la titularidad: solo su profesional accede a sus datos, y todo acceso queda registrado en una traza de auditoría.",
        "Nada se analiza sin su consentimiento explícito (consentimiento informado/LGPD) — que puede revocar en cualquier momento.",
        "Sus derechos de protección de datos están garantizados: acceso, corrección y supresión cuando corresponda.",
        "Las estadísticas colectivas usan solo datos anonimizados y agregados (nunca grupos pequeños) — no lo identifican.",
        "Su contraseña se protege mediante hashing (PBKDF2-SHA256); nunca la almacenamos en texto legible.",
      ],
      footer:
        "Estas medidas describen controles técnicos aplicados en la plataforma y no sustituyen la política de privacidad completa.",
      link: "Ver política de seguridad y privacidad",
    },
    "fr-FR": {
      title: "Comment nous protégeons vos informations",
      intro:
        "Vos données de santé sont traitées comme sensibles. Voici les mesures que nous prenons pour préserver leur confidentialité :",
      items: [
        "Connexion chiffrée (HTTPS/TLS) pendant toute la séance — audio, vidéo et données circulent protégés.",
        "Les informations sensibles (transcriptions, rapports et identifiants) sont stockées chiffrées avec un chiffrement authentifié (AES + HMAC) et des clés renouvelables.",
        "Accès restreint à la titularité : seul votre professionnel accède à vos données, et chaque accès est inscrit dans une piste d’audit.",
        "Rien n’est analysé sans votre consentement explicite (consentement éclairé/LGPD) — que vous pouvez retirer à tout moment.",
        "Vos droits en matière de protection des données sont garantis : accès, rectification et effacement lorsque applicable.",
        "Les statistiques collectives n’utilisent que des données anonymisées et agrégées (jamais de petits groupes) — elles ne vous identifient pas.",
        "Votre mot de passe est protégé par hachage (PBKDF2-SHA256) ; nous ne le stockons jamais en clair.",
      ],
      footer:
        "Ces mesures décrivent des contrôles techniques appliqués sur la plateforme et ne remplacent pas la politique de confidentialité complète.",
      link: "Voir la politique de sécurité et de confidentialité",
    },
  },
  professional: {
    "pt-BR": {
      title: "Segurança dos dados dos seus pacientes",
      intro:
        "O FROID trata dados de saúde como sensíveis. Providências técnicas aplicadas na plataforma:",
      items: [
        "Tráfego criptografado (HTTPS/TLS) e conteúdos sensíveis (transcrições, relatórios e tokens) armazenados com criptografia autenticada (AES + HMAC) e rotação de chaves.",
        "Controle de acesso por titularidade e isolamento por conta: cada profissional acessa apenas os próprios pacientes.",
        "Trilha de auditoria de acessos, alterações, exportações e negativas de acesso, vinculada à conta que executou a ação.",
        "Senhas protegidas por hashing (PBKDF2-SHA256); tokens de sessão com expiração.",
        "Bases populacionais anonimizadas/pseudonimizadas, com bloqueio de coortes pequenas (k-anonimato) para consultas agregadas.",
        "Portal de direitos do titular (LGPD) para acesso, correção e exclusão de dados.",
      ],
      footer:
        "Responsabilidade compartilhada: o FROID protege a infraestrutura da plataforma; o profissional é responsável pelos consentimentos obtidos e pela gestão de acesso da sua equipe.",
      link: "Ver política de segurança e privacidade",
    },
  },
};

type Props = {
  audience?: Audience;
  locale?: SessionLocale;
  className?: string;
};

const SITE_SECURITY_URL = "/seguranca.html";

export const SecurityAssurance: React.FC<Props> = ({
  audience = "patient",
  locale = "pt-BR",
  className = "",
}) => {
  const normalized = normalizeSessionLocale(locale);
  const byAudience = CONTENT[audience] || CONTENT.patient;
  const copy = byAudience[normalized] || byAudience["pt-BR"] || CONTENT.patient["pt-BR"]!;

  return (
    <section
      className={`rounded-lg border border-emerald-800/70 bg-emerald-950/30 p-4 text-emerald-50 ${className}`}
      aria-label={copy.title}
    >
      <div className="flex items-center gap-2">
        <span className="text-lg" aria-hidden>
          🔒
        </span>
        <h2 className="text-sm font-black text-emerald-100">{copy.title}</h2>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-emerald-100/90">{copy.intro}</p>
      <ul className="mt-2 space-y-1.5 text-xs leading-relaxed">
        {copy.items.map((item) => (
          <li key={item} className="flex gap-2">
            <span className="mt-0.5 shrink-0 text-emerald-400" aria-hidden>
              ✓
            </span>
            <span className="text-emerald-50/90">{item}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[11px] leading-5 text-emerald-200/70">{copy.footer}</p>
      <a
        href={SITE_SECURITY_URL}
        target="_blank"
        rel="noreferrer"
        className="mt-1 inline-block text-[11px] font-bold text-emerald-300 underline"
      >
        {copy.link}
      </a>
    </section>
  );
};
