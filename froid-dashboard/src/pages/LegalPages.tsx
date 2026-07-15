import type { ReactNode } from "react";

function LegalShell({
  title,
  eyebrow,
  children,
}: {
  title: string;
  eyebrow: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950/95">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-5 py-4">
          <a href="/#/" className="text-sm font-black uppercase tracking-[0.28em] text-cyan-300">
            FROID
          </a>
          <nav className="flex flex-wrap gap-3 text-xs font-bold text-slate-300">
            <a className="hover:text-cyan-200" href="/#/">
              Inicio
            </a>
            <a className="hover:text-cyan-200" href="/#/privacidade">
              Privacidade
            </a>
            <a className="hover:text-cyan-200" href="/#/termos">
              Termos
            </a>
            <a className="rounded border border-cyan-800 px-3 py-1 text-cyan-100 hover:bg-cyan-950" href="/login">
              Entrar
            </a>
            <a className="rounded bg-cyan-700 px-3 py-1 text-white hover:bg-cyan-800" href="/cadastro">
              Cadastrar
            </a>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-5 py-10">
        <p className="text-[11px] font-black uppercase tracking-[0.28em] text-cyan-300">
          {eyebrow}
        </p>
        <h1 className="mt-3 text-3xl font-black text-white">{title}</h1>
        <div className="mt-8 space-y-6 rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm leading-7 text-slate-300 shadow-sm">
          {children}
        </div>
      </main>
    </div>
  );
}

export function PrivacyPage() {
  return (
    <LegalShell title="Politica de Privacidade" eyebrow="Legal e LGPD">
      <p>
        O FROID trata dados pessoais e dados sensiveis de saude com finalidade
        clinica, operacional e de seguranca, sempre como ferramenta de apoio ao
        profissional habilitado. O sistema nao substitui diagnostico, avaliacao
        clinica ou decisao terapeutica.
      </p>

      <section>
        <h2 className="text-base font-black text-white">Dados tratados</h2>
        <p className="mt-2">
          Podem ser tratados dados de cadastro do profissional, dados cadastrais
          do paciente, agenda de sessoes, audio, video, transcricao, anotacoes
          clinicas, metricas acusticas, metricas faciais, indicadores derivados,
          relatorios de sessao e registros de auditoria.
        </p>
      </section>

      <section>
        <h2 className="text-base font-black text-white">Google Agenda</h2>
        <p className="mt-2">
          Quando o profissional conecta o Google Agenda, o FROID solicita acesso
          para identificar a conta Google, listar agendas de propriedade do
          profissional e criar, consultar, alterar ou remover eventos apenas nas
          agendas que esse profissional possui e seleciona para uso clinico.
          Recomendamos criar uma agenda dedicada chamada FROID - Sessoes.
        </p>
      </section>

      <section>
        <h2 className="text-base font-black text-white">Finalidades</h2>
        <p className="mt-2">
          Os dados sao usados para autenticar usuarios, organizar sessoes,
          apoiar a escuta clinica em tempo real, gerar relatorios, permitir
          continuidade longitudinal do atendimento, cumprir obrigacoes legais e
          melhorar a seguranca e qualidade tecnica da plataforma.
        </p>
      </section>

      <section>
        <h2 className="text-base font-black text-white">Base anonima e pesquisa</h2>
        <p className="mt-2">
          Informacoes agregadas e anonimizadas podem compor base estatistica
          para pesquisa, melhoria algoritmica e comparacoes populacionais,
          observando governanca, minimizacao, controles de acesso e criterios
          de anonimato.
        </p>
      </section>

      <section>
        <h2 className="text-base font-black text-white">Direitos do titular</h2>
        <p className="mt-2">
          O titular pode solicitar acesso, correcao, portabilidade, informacoes
          sobre tratamento, revogacao de consentimento e exclusao de dados,
          conforme aplicavel pela LGPD. Solicite atendimento pelo contato do
          FROID informado no site.
        </p>
      </section>
    </LegalShell>
  );
}

export function TermsPage() {
  return (
    <LegalShell title="Termos de Uso" eyebrow="Condicoes de utilizacao">
      <p>
        Estes termos regulam o uso do FROID por profissionais de saude mental,
        pacientes convidados e usuarios autorizados. Ao utilizar a plataforma, o
        usuario declara compreender sua finalidade de apoio clinico e seus
        limites tecnicos.
      </p>

      <section>
        <h2 className="text-base font-black text-white">Natureza do servico</h2>
        <p className="mt-2">
          O FROID e uma plataforma de percepcao clinica aumentada. Seus
          indicadores, graficos, transcricoes, relatorios e respostas do FROID
          Explica devem ser interpretados pelo profissional responsavel em
          conjunto com anamnese, contexto, vinculo terapeutico e julgamento
          clinico.
        </p>
      </section>

      <section>
        <h2 className="text-base font-black text-white">Responsabilidade profissional</h2>
        <p className="mt-2">
          O profissional e responsavel por obter consentimentos, verificar a
          adequacao do uso ao seu conselho profissional, informar o paciente e
          decidir como incorporar os dados do FROID em sua pratica.
        </p>
      </section>

      <section>
        <h2 className="text-base font-black text-white">Agenda e convites</h2>
        <p className="mt-2">
          A integracao com Google Agenda serve para organizar sessoes e preparar
          convites. O profissional deve selecionar uma agenda adequada, de
          preferencia dedicada ao FROID, e manter seus compromissos revisados.
        </p>
      </section>

      <section>
        <h2 className="text-base font-black text-white">Limites</h2>
        <p className="mt-2">
          O FROID nao emite diagnostico autonomo, nao substitui atendimento
          medico ou psicologico e nao deve ser usado como unico fundamento para
          decisoes clinicas, legais, laborais, securitarias ou emergenciais.
        </p>
      </section>
    </LegalShell>
  );
}
