import React from "react";

type LgpdNoticeProps = {
  compact?: boolean;
  audience?: "professional" | "patient" | "home";
};

const legalBases = [
  "consentimento livre, informado, inequivoco, especifico e destacado quando aplicavel",
  "execucao de contrato e procedimentos preliminares relacionados ao acesso ao FROID",
  "tutela da saude e apoio a procedimento realizado por profissional habilitado",
  "cumprimento de obrigacoes legais ou regulatorias",
  "legitimo interesse estritamente limitado a seguranca, auditoria, prevencao a fraude e melhoria operacional",
  "estudos e melhoria tecnica com dados anonimizados sempre que possivel",
];

const holderRights = [
  "confirmacao da existencia de tratamento",
  "acesso aos dados pessoais",
  "correcao de dados incompletos, inexatos ou desatualizados",
  "anonimizacao, bloqueio ou eliminacao de dados desnecessarios, excessivos ou tratados em desconformidade",
  "portabilidade quando tecnicamente aplicavel",
  "informacao sobre compartilhamentos realizados",
  "revogacao do consentimento e informacao sobre as consequencias da negativa",
  "oposicao a tratamento irregular",
  "revisao de decisoes automatizadas quando houver decisao baseada exclusivamente em tratamento automatizado",
];

export const LgpdNotice: React.FC<LgpdNoticeProps> = ({
  compact = false,
  audience = "professional",
}) => {
  const isPatient = audience === "patient";
  const isHome = audience === "home";

  return (
    <section
      className={`rounded-lg border border-amber-200 bg-amber-50 text-amber-950 ${
        compact ? "p-3 text-xs" : "p-4 text-xs"
      }`}
    >
      <h2 className="text-sm font-black text-amber-950">
        LGPD, dados sensiveis e responsabilidade de uso
      </h2>
      <p className="mt-2 leading-6">
        O FROID foi projetado para operar de acordo com a Lei Geral de Protecao
        de Dados Pessoais, Lei Federal n. 13.709/2018, e com orientacoes da
        Autoridade Nacional de Protecao de Dados. A plataforma trata dados
        pessoais e pode tratar dados pessoais sensiveis, incluindo informacoes
        de saude mental, voz, imagem, biometria facial, biomarcadores acusticos,
        transcricoes, relatorios clinicos, historico de sessoes, identificadores
        tecnicos, registros de auditoria e dados financeiros de acesso.
      </p>

      {!compact && (
        <>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div className="rounded-md border border-amber-200 bg-white/60 p-3">
              <p className="font-black">Finalidades autorizadas</p>
              <p className="mt-1 leading-5">
                cadastro, autenticacao, gestao de convites, realizacao de sessoes,
                processamento de audio/video quando consentido, leitura multimodal,
                geracao de metricas, relatorios, suporte clinico ao profissional,
                faturamento, seguranca, auditoria, prevencao de fraude,
                atendimento a solicitacoes do titular e melhoria do sistema.
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
              <p className="font-black">Seguranca, auditoria e incidentes</p>
              <p className="mt-1 leading-5">
                O FROID adota arquitetura orientada a minimizacao, segregacao,
                controle de acesso, registros de auditoria, criptografia quando
                aplicavel, anonimização para bases populacionais e governanca de
                incidentes. Na hipotese de incidente confirmado que possa causar
                risco ou dano relevante, o controlador deve avaliar e comunicar
                titulares e ANPD nos termos da regulamentacao aplicavel.
              </p>
            </div>
            <div className="rounded-md border border-amber-200 bg-white/60 p-3">
              <p className="font-black">Anonimizacao e IA</p>
              <p className="mt-1 leading-5">
                Dados usados para pesquisa, benchmarks e Data Mart devem ser
                anonimizados ou agregados sempre que possivel. Respostas de IA,
                metricas, IPM, IDM, riscos, biomarcadores e dissonancias sao
                instrumentos de apoio e nao substituem diagnostico, conduta,
                supervisao humana ou julgamento clinico do profissional habilitado.
              </p>
            </div>
          </div>
        </>
      )}

      <p className="mt-3 leading-6">
        {isPatient
          ? "Ao prosseguir, o paciente declara ter recebido informacoes claras sobre a coleta e o tratamento de seus dados, podendo negar ou revogar consentimentos quando aplicavel, ciente de que a negativa pode limitar funcionalidades da sessao."
          : isHome
            ? "A conformidade depende tambem da correta configuracao operacional, da obtencao de consentimentos validos, de contratos adequados e da governanca do profissional ou instituicao usuaria."
            : "O profissional ou instituicao cadastrante declara possuir base legal, autorizacao e consentimentos necessarios para inserir e tratar dados de pacientes, assumindo responsabilidade pela veracidade das informacoes, pela finalidade clinica e pelo uso adequado da plataforma."}
      </p>
      <p className="mt-2 text-[11px] leading-5 text-amber-800">
        Este aviso nao substitui politica de privacidade, contrato, termo de uso,
        consentimento especifico, RIPD/DPIA ou revisao juridica especializada. O
        texto deve ser revisado pelo responsavel juridico/DPO antes de uso em
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
