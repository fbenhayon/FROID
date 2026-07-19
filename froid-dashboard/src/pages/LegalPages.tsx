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
              Início
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
    <LegalShell title="Política de Privacidade" eyebrow="Legal e LGPD">
      <p>
        O FROID trata dados pessoais e dados sensíveis de saúde com finalidade
        clínica, operacional e de segurança, sempre como ferramenta de apoio ao
        profissional habilitado. O sistema não substitui diagnóstico, avaliação
        clínica ou decisao terapêutica.
      </p>

      <section>
        <h2 className="text-base font-black text-white">Dados tratados</h2>
        <p className="mt-2">
          Podem ser tratados dados de cadastro do profissional, dados cadastrais
          do paciente, agenda de sessões, áudio, vídeo, transcrição, anotações
          clínicas, métricas acústicas, métricas faciais, indicadores derivados,
          relatórios de sessão e registros de auditoria.
        </p>
      </section>

      <section>
        <h2 className="text-base font-black text-white">Google Agenda</h2>
        <p className="mt-2">
          Quando o profissional conecta o Google Agenda, o FROID solicita acesso
          para identificar a conta Google, listar agendas de propriedade do
          profissional e criar, consultar, alterar ou remover eventos apenas nas
          agendas que esse profissional possui e seleciona para uso clínico.
          Recomendamos criar uma agenda dedicada chamada FROID - Sessões.
        </p>
      </section>

      <section>
        <h2 className="text-base font-black text-white">Finalidades</h2>
        <p className="mt-2">
          Os dados são usados para autenticar usuários, organizar sessões,
          apoiar a escuta clínica em tempo real, gerar relatórios, permitir
          continuidade longitudinal do atendimento, cumprir obrigações legais e
          melhorar a segurança e qualidade técnica da plataforma.
        </p>
      </section>

      <section>
        <h2 className="text-base font-black text-white">Base anonima e pesquisa</h2>
        <p className="mt-2">
          Informações agregadas e anonimizadas podem compor base estatística
          para pesquisa, melhoria algoritmica e comparações populacionais,
          observando governanca, minimizacao, controles de acesso e criterios
          de anonimato.
        </p>
      </section>

      <section>
        <h2 className="text-base font-black text-white">Direitos do titular</h2>
        <p className="mt-2">
          O titular pode solicitar acesso, correcao, portabilidade, informações
          sobre tratamento, revogacao de consentimento e exclusao de dados,
          conforme aplicável pela LGPD. Solicite atendimento pelo contato do
          FROID informado no site.
        </p>
      </section>
    </LegalShell>
  );
}

export function TermsPage() {
  return (
    <LegalShell title="Termos de Uso" eyebrow="Condições de utilização">
      <p>
        Estes termos regulam o uso do FROID por profissionais de saúde mental,
        pacientes convidados e usuários autorizados. Ao utilizar a plataforma, o
        usuário declara compreender sua finalidade de apoio clínico e seus
        limites técnicos.
      </p>

      <section>
        <h2 className="text-base font-black text-white">Natureza do serviço</h2>
        <p className="mt-2">
          O FROID e uma plataforma de percepção clínica aumentada. Seus
          indicadores, gráficos, transcricoes, relatórios e respostas do FROID
          Explica devem ser interpretados pelo profissional responsável em
          conjunto com anamnese, contexto, vinculo terapêutico e julgamento
          clínico.
        </p>
      </section>

      <section>
        <h2 className="text-base font-black text-white">Responsabilidade profissional</h2>
        <p className="mt-2">
          O profissional e responsável por obter consentimentos, verificar a
          adequacao do uso ao seu conselho profissional, informar o paciente e
          decidir como incorporar os dados do FROID em sua prática.
        </p>
      </section>

      <section>
        <h2 className="text-base font-black text-white">Agenda e convites</h2>
        <p className="mt-2">
          A integracao com Google Agenda serve para organizar sessões e preparar
          convites. O profissional deve selecionar uma agenda adequada, de
          preferencia dedicada ao FROID, e manter seus compromissos revisados.
        </p>
      </section>

      <section>
        <h2 className="text-base font-black text-white">Limites</h2>
        <p className="mt-2">
          O FROID não emite diagnóstico autônomo, não substitui atendimento
          médico ou psicologico e não deve ser usado como único fundamento para
          decisões clínicas, legais, laborais, securitarias ou emergenciais.
        </p>
      </section>
    </LegalShell>
  );
}
