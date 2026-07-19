import React from "react";
import { normalizeSessionLocale, type SessionLocale } from "../../lib/localization";

type LgpdNoticeProps = {
  compact?: boolean;
  audience?: "professional" | "patient" | "home";
  locale?: SessionLocale;
};

const internationalCompactNotice: Partial<Record<SessionLocale, { title: string; body: string; rights: string; review: string }>> = {
  "en-US": {
    title: "Sensitive health information and professional responsibility",
    body: "FROID may process mental-health information, voice, image, acoustic metrics, transcripts, session reports, technical identifiers, audit records, and access-payment information. Processing is limited to the session purposes authorized by the patient and the qualified professional.",
    rights: "The patient may request access, correction, information about sharing, restriction, deletion where legally applicable, and withdrawal of optional authorizations. FROID outputs support professional review and do not replace diagnosis or professional judgment.",
    review: "Controlled-validation notice. The country-specific privacy notice and contract require final legal review before general commercial release.",
  },
  "fr-FR": {
    title: "Données de santé sensibles et responsabilité professionnelle",
    body: "FROID peut traiter des informations de santé mentale, la voix, l’image, des métriques acoustiques, des transcriptions, des rapports de séance, des identifiants techniques, des journaux d’audit et des informations de paiement. Le traitement est limité aux finalités autorisées par le patient et le professionnel qualifié.",
    rights: "Le patient peut demander l’accès, la rectification, des informations sur les destinataires, la limitation, l’effacement lorsque la loi le permet et le retrait des autorisations facultatives. Les résultats FROID aident le professionnel et ne remplacent ni un diagnostic ni son jugement.",
    review: "Notice de validation contrôlée. La notice de confidentialité et le contrat propres au pays doivent faire l’objet d’une validation juridique finale avant la commercialisation générale.",
  },
  "es-ES": {
    title: "Datos sensibles de salud y responsabilidad profesional",
    body: "FROID puede procesar información de salud mental, voz, imagen, métricas acústicas, transcripciones, informes de sesión, identificadores técnicos, registros de auditoría e información de pago. El tratamiento se limita a las finalidades autorizadas por el paciente y el profesional cualificado.",
    rights: "El paciente puede solicitar acceso, rectificación, información sobre destinatarios, limitación, supresión cuando sea legalmente aplicable y retirada de autorizaciones opcionales. Los resultados de FROID apoyan la revisión profesional y no sustituyen el diagnóstico ni el criterio profesional.",
    review: "Aviso de validación controlada. El aviso de privacidad y el contrato específicos del país requieren revisión jurídica final antes de la comercialización general.",
  },
};

const legalBases = [
  "consentimento livre, informado, inequivoco, específico e destacado quando aplicável",
  "execucao de contrato e procedimentos preliminares relacionados ao acesso ao FROID",
  "tutela da saúde e apoio a procedimento realizado por profissional habilitado",
  "cumprimento de obrigações legais ou regulatorias",
  "legitimo interesse estritamente limitado a segurança, auditoria, prevencao a fraude e melhoria operacional",
  "estudos e melhoria técnica com dados anonimizados sempre que possível",
];

const holderRights = [
  "confirmação da existencia de tratamento",
  "acesso aos dados pessoais",
  "correcao de dados incompletos, inexatos ou desatualizados",
  "anonimizacao, bloqueio ou eliminacao de dados desnecessarios, excessivos ou tratados em desconformidade",
  "portabilidade quando tecnicamente aplicável",
  "informação sobre compartilhamentos realizados",
  "revogacao do consentimento e informação sobre as consequencias da negativa",
  "oposicao a tratamento irregular",
  "revisão de decisões automatizadas quando houver decisao baseada exclusivamente em tratamento automatizado",
];

export const LgpdNotice: React.FC<LgpdNoticeProps> = ({
  compact = false,
  audience = "professional",
  locale = "pt-BR",
}) => {
  const normalizedLocale = normalizeSessionLocale(locale);
  const internationalNotice = internationalCompactNotice[normalizedLocale];
  const isPatient = audience === "patient";
  const isHome = audience === "home";

  if (compact && internationalNotice) {
    return (
      <section className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-950">
        <h2 className="text-sm font-black">{internationalNotice.title}</h2>
        <p className="mt-2 leading-6">{internationalNotice.body}</p>
        <p className="mt-2 leading-6">{internationalNotice.rights}</p>
        <p className="mt-2 text-[11px] leading-5 text-amber-800">{internationalNotice.review}</p>
      </section>
    );
  }

  return (
    <section
      className={`rounded-lg border border-amber-200 bg-amber-50 text-amber-950 ${
        compact ? "p-3 text-xs" : "p-4 text-xs"
      }`}
    >
      <h2 className="text-sm font-black text-amber-950">
        LGPD, dados sensíveis e responsabilidade de uso
      </h2>
      <p className="mt-2 leading-6">
        O FROID foi projetado para operar de acordo com a Lei Geral de Proteção
        de Dados Pessoais, Lei Federal n. 13.709/2018, e com orientações da
        Autoridade Nacional de Proteção de Dados. A plataforma trata dados
        pessoais e pode tratar dados pessoais sensíveis, incluindo informações
        de saúde mental, voz, imagem, biometria facial, biomarcadores acústicos,
        transcricoes, relatórios clínicos, histórico de sessões, identificadores
        técnicos, registros de auditoria e dados financeiros de acesso.
      </p>

      {!compact && (
        <>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div className="rounded-md border border-amber-200 bg-white/60 p-3">
              <p className="font-black">Finalidades autorizadas</p>
              <p className="mt-1 leading-5">
                cadastro, autenticação, gestão de convites, realização de sessões,
                processamento de áudio/video quando consentido, leitura multimodal,
                geracao de métricas, relatórios, suporte clínico ao profissional,
                faturamento, segurança, auditoria, prevencao de fraude,
                atendimento a solicitações do titular e melhoria do sistema.
              </p>
            </div>
            <div className="rounded-md border border-amber-200 bg-white/60 p-3">
              <p className="font-black">Bases legais consideradas</p>
              <ul className="mt-1 list-disc space-y-1 pl-4">
                {legalBases.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>

          <div className="mt-3 rounded-md border border-amber-200 bg-white/60 p-3">
            <p className="font-black">Direitos do titular</p>
            <p className="mt-1 leading-5">
              O titular pode exercer, nos termos da LGPD, os seguintes direitos:
            </p>
            <ul className="mt-2 grid list-disc gap-1 pl-4 md:grid-cols-2">
              {holderRights.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>

          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div className="rounded-md border border-amber-200 bg-white/60 p-3">
              <p className="font-black">Segurança, auditoria e incidentes</p>
              <p className="mt-1 leading-5">
                O FROID adota arquitetura orientada a minimizacao, segregacao,
                controle de acesso, registros de auditoria, criptografia quando
                aplicável, anonimização para bases populacionais e governanca de
                incidentes. Na hipótese de incidente confirmado que possa causar
                risco ou dano relevante, o controlador deve avaliar e comunicar
                titulares e ANPD nos termos da regulamentacao aplicável.
              </p>
            </div>
            <div className="rounded-md border border-amber-200 bg-white/60 p-3">
              <p className="font-black">Anonimizacao e IA</p>
              <p className="mt-1 leading-5">
                Dados usados para pesquisa, benchmarks e Data Mart devem ser
                anonimizados ou agregados sempre que possível. Respostas de IA,
                métricas, IPM, IDM, riscos, biomarcadores e dissonâncias são
                instrumentos de apoio e não substituem diagnóstico, conduta,
                supervisao humana ou julgamento clínico do profissional habilitado.
              </p>
            </div>
          </div>
        </>
      )}

      <p className="mt-3 leading-6">
        {isPatient
          ? "Ao prosseguir, o paciente declara ter recebido informações claras sobre a coleta e o tratamento de seus dados, podendo negar ou revogar consentimentos quando aplicável, ciente de que a negativa pode limitar funcionalidades da sessão."
          : isHome
            ? "A conformidade depende também da correta configuração operacional, da obtencao de consentimentos validos, de contratos adequados e da governanca do profissional ou instituicao usuaria."
            : "O profissional ou instituicao cadastrante declara possuir base legal, autorizacao e consentimentos necessários para inserir e tratar dados de pacientes, assumindo responsabilidade pela veracidade das informações, pela finalidade clínica e pelo uso adequado da plataforma."}
      </p>
      <p className="mt-2 text-[11px] leading-5 text-amber-800">
        Este aviso não substitui política de privacidade, contrato, termo de uso,
        consentimento específico, RIPD/DPIA ou revisão jurídica especializada. O
        texto deve ser revisado pelo responsável juridico/DPO antes de uso em
        producao.
      </p>
      <div className="mt-2 flex flex-wrap gap-2 text-[11px] font-bold">
        <a
          href="https://www.gov.br/anpd/pt-br"
          target="_blank"
          rel="noreferrer"
          className="underline"
        >
          ANPD
        </a>
        <a
          href="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm"
          target="_blank"
          rel="noreferrer"
          className="underline"
        >
          Lei 13.709/2018
        </a>
      </div>
    </section>
  );
};
