import React from "react";
import { Link } from "react-router-dom";
import { LgpdNotice } from "../components/legal/LgpdNotice";

const heroImage = "/froid-home/facs-matrizes-emocionais.png";
const auImage = "/froid-home/facs-unidades-acao.png";

const navItems = [
  { label: "Ciencia", to: "/froid/ciencia" },
  { label: "Tecnologia", to: "/froid/tecnologia" },
  { label: "Profissionais", to: "/froid/profissionais" },
];

const abilities = [
  {
    title: "Transcricao clinica em tempo real",
    brief:
      "Registra a fala na cadencia da sessao, separando profissional e paciente, para leitura, revisao e relatorio posterior.",
  },
  {
    title: "Bioacustica vocal do paciente",
    brief:
      "Extrai F0, ZCR, Jitter, Shimmer, energia, pausas, cadencia, MFCC7, MFCC9 e sub-harmonicos vocais da trilha do paciente.",
  },
  {
    title: "FACS, AUs e microexpressoes",
    brief:
      "Mapeia unidades de acao facial, intensidade, assimetria, duracao e combinacoes expressivas associadas a matrizes emocionais.",
  },
  {
    title: "IPM e IDM",
    brief:
      "O IPM mede a intensidade global da mobilizacao emocional; o IDM aponta a direcao dominante do desequilibrio no mapa zonal.",
  },
  {
    title: "Dissonancias e consonancias",
    brief:
      "Cruza voz, face, narrativa, zonas, riscos e baseline para apontar divergencias relevantes e coerencias expressivas.",
  },
  {
    title: "Cortes, temas e resumos",
    brief:
      "Consolida janelas obrigatorias de 10 minutos e cortes profissionais com tema, resumo e metricas correspondentes.",
  },
  {
    title: "Relatorio da Consulta",
    brief:
      "Organiza baseline, medias, cortes, dissonancias, observacoes clinicas e selecao do profissional em um documento de revisao.",
  },
  {
    title: "FROID Explica",
    brief:
      "Permite ao profissional perguntar sobre achados, metricas, fontes tecnicas e possiveis relacoes clinicas durante ou apos a sessao.",
  },
  {
    title: "Data Mart anonimo",
    brief:
      "Transforma metricas anonimizadas em base populacional para benchmarks, pesquisa, comparacao longitudinal e descoberta de padroes.",
  },
];

const dnaPoints = [
  "O FROID nasce para complementar, e nao substituir, o raciocinio do profissional de saude mental.",
  "Sua funcao e estabelecer pontes entre psique, linguagem, corpo, voz, expressao facial e dinamica temporal da sessao.",
  "A plataforma observa bilhoes de combinacoes possiveis entre sinais que, isoladamente, podem parecer discretos, mas em conjunto revelam coerencias, contradicoes e caminhos de investigacao.",
  "A base anonima permite que o sistema amadureca por padroes agregados, sempre com governanca, auditoria, LGPD e validacao profissional.",
  "O FROID aponta associacoes e hipoteses clinicas; a decisao, a interpretacao final e a conduta pertencem ao profissional habilitado.",
];

const signalGroups = [
  "Voz: intensidade, frequencia, tensao, pausas, velocidade, sub-harmonicos e biomarcadores acusticos.",
  "Face: AUs, assimetria, onset, apex, offset, microexpressoes, combinacoes e matrizes emocionais.",
  "Semantica: tema, sentido da fala, valencia, contradicoes narrativas, resumo e evolucao por cortes.",
  "Temporalidade: baseline de 60 segundos, cortes de 10 minutos, cortes profissionais e medias finais.",
  "Sintese: IPM, IDM, riscos, dissonancias, consonancias, relatorio e FROID Explica.",
];

function Header() {
  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-slate-950/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4">
        <Link to="/" className="text-sm font-black tracking-[0.42em] text-cyan-300">
          FROID
        </Link>
        <nav className="hidden items-center gap-1 text-xs font-black text-slate-300 md:flex">
          {navItems.map((item) => (
            <Link key={item.to} to={item.to} className="rounded px-3 py-2 hover:bg-white/10">
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <Link to="/login" className="rounded border border-white/20 px-3 py-2 text-xs font-black text-slate-100 hover:bg-white/10">
            Login
          </Link>
          <Link to="/access/register" className="rounded bg-cyan-400 px-3 py-2 text-xs font-black text-slate-950 hover:bg-cyan-300">
            Cadastro
          </Link>
        </div>
      </div>
    </header>
  );
}

function SectionHeading({
  eyebrow,
  title,
  text,
}: {
  eyebrow: string;
  title: string;
  text: string;
}) {
  return (
    <div className="max-w-4xl">
      <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">{eyebrow}</p>
      <h2 className="mt-3 text-2xl font-black leading-tight text-white md:text-4xl">{title}</h2>
      <p className="mt-4 text-sm leading-7 text-slate-300 md:text-base">{text}</p>
    </div>
  );
}

function AbilityCard({ title, brief, index }: { title: string; brief: string; index: number }) {
  return (
    <article className="rounded-lg border border-white/10 bg-slate-900 p-5 shadow-lg shadow-slate-950/20">
      <div className="flex items-center gap-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-cyan-400/15 text-xs font-black text-cyan-200">
          {String(index + 1).padStart(2, "0")}
        </span>
        <h3 className="text-base font-black text-white">{title}</h3>
      </div>
      <p className="mt-4 text-sm leading-7 text-slate-300">{brief}</p>
    </article>
  );
}

function ImagePanel({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white p-3 shadow-2xl shadow-cyan-950/30">
      <img src={src} alt={alt} className="h-auto max-h-[620px] w-full object-contain" />
    </div>
  );
}

export const HomePage: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <Header />

      <main>
        <section
          className="relative border-b border-white/10 bg-slate-950"
          style={{
            backgroundImage: `linear-gradient(90deg, rgba(2,6,23,0.98) 0%, rgba(2,6,23,0.92) 40%, rgba(2,6,23,0.35) 100%), url(${heroImage})`,
            backgroundPosition: "right center",
            backgroundRepeat: "no-repeat",
            backgroundSize: "min(78vw, 1120px) auto",
          }}
        >
          <div className="mx-auto flex min-h-[78vh] max-w-7xl items-center px-5 py-16">
            <div className="max-w-3xl">
              <p className="text-xs font-black uppercase tracking-[0.38em] text-cyan-300">
                Frequency Recognition of Internal Dynamics
              </p>
              <h1 className="mt-5 text-4xl font-black leading-[1.03] text-white md:text-6xl">
                A inteligencia de observacao clinica para decifrar dissonancias humanas.
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-8 text-slate-200 md:text-lg">
                O FROID integra bioacustica vocal, FACS, unidades de acao facial,
                transcricao, IPM, IDM, zonas emocionais, cortes temporais e IA explicativa
                para apoiar profissionais na leitura da coerencia entre psique, fala,
                corpo e expressao.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link to="/access/register" className="rounded-lg bg-cyan-400 px-5 py-3 text-sm font-black text-slate-950 hover:bg-cyan-300">
                  Cadastrar profissional
                </Link>
                <Link to="/froid/ciencia" className="rounded-lg border border-cyan-300/50 px-5 py-3 text-sm font-black text-cyan-100 hover:bg-cyan-300/10">
                  Ver ciencia FROID
                </Link>
              </div>
              <p className="mt-5 text-xs font-black uppercase tracking-[0.2em] text-cyan-100">
                20 sessoes gratuitas para os primeiros 100 profissionais. 10 sessoes para os proximos 100.
              </p>
            </div>
          </div>
        </section>

        <section className="border-b border-white/10 bg-slate-900/70">
          <div className="mx-auto grid max-w-7xl gap-4 px-5 py-8 md:grid-cols-4">
            {[
              ["60s", "baseline individual"],
              ["10min", "cortes obrigatorios"],
              ["500ms", "indices dinamicos"],
              ["4 camadas", "voz, face, semantica e tempo"],
            ].map(([value, label]) => (
              <div key={value} className="rounded-lg border border-white/10 bg-slate-950 p-4">
                <p className="text-2xl font-black text-cyan-200">{value}</p>
                <p className="mt-1 text-xs font-black uppercase tracking-[0.18em] text-slate-400">{label}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-14">
          <SectionHeading
            eyebrow="DNA FROID"
            title="Uma segunda camada de percepcao para uma clinica mais precisa."
            text="A saude mental nasce na intersecao entre relato, corpo, memoria, linguagem, defesa, historia e expressao. O FROID foi concebido para observar essa intersecao com recursos de IA, bioacustica, visao computacional e bases anonimas, oferecendo ao profissional sinais tecnicos que ampliam sua escuta sem substituir sua responsabilidade clinica."
          />
          <div className="mt-8 grid gap-3">
            {dnaPoints.map((point) => (
              <p key={point} className="rounded-lg border border-cyan-300/15 bg-cyan-300/5 p-4 text-sm leading-7 text-slate-200">
                {point}
              </p>
            ))}
          </div>
        </section>

        <section className="border-y border-white/10 bg-slate-900/70">
          <div className="mx-auto max-w-7xl px-5 py-14">
            <SectionHeading
              eyebrow="Habilidades"
              title="Todas as habilidades centrais em um unico fluxo de sessao."
              text="O modelo anterior era correto no essencial: cada habilidade precisa aparecer como um bloco claro, com briefing objetivo. Esta e a matriz operacional que o profissional deve compreender antes de usar o FROID."
            />
            <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {abilities.map((ability, index) => (
                <AbilityCard key={ability.title} {...ability} index={index} />
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto grid max-w-7xl gap-8 px-5 py-14 lg:grid-cols-[0.88fr_1.12fr]">
          <div>
            <SectionHeading
              eyebrow="FACS / AUs"
              title="A face como matriz de sinais, nao como leitura isolada."
              text="As unidades de acao facial ganham valor clinico quando sao cruzadas com voz, semantica, timing, intensidade e assimetria. O FROID usa esse mapa para detectar combinacoes que podem indicar coerencia expressiva, defesa, contencao, sofrimento ou dissonancia."
            />
            <div className="mt-7 grid gap-3">
              {signalGroups.map((item) => (
                <p key={item} className="rounded-lg border border-white/10 bg-slate-900 p-4 text-sm leading-7 text-slate-300">
                  {item}
                </p>
              ))}
            </div>
          </div>
          <ImagePanel src={auImage} alt="Mapa completo das unidades de acao facial FACS no FROID" />
        </section>

        <section className="border-y border-white/10 bg-slate-900/70">
          <div className="mx-auto max-w-7xl px-5 py-14">
            <SectionHeading
              eyebrow="Dissonancias"
              title="O ponto critico: quando a expressao contradiz a narrativa."
              text="Dissonancia nao e afirmacao do paciente. E um apontamento tecnico ao profissional quando os sinais efetivamente apurados ficam acima da metrica definida. O texto deve explicar quais itens divergiram, quais metricas participaram e qual ponto merece atencao clinica."
            />
            <div className="mt-8 grid gap-4 lg:grid-cols-3">
              {[
                ["Semantica x voz", "O relato pode indicar estabilidade enquanto a voz revela tensao, pausas, aceleracao, retardo, queda de variabilidade ou sub-harmonicos elevados."],
                ["Face x narrativa", "A fala pode sustentar calma enquanto AUs de dor, medo, nojo, raiva contida ou tristeza mascarada aparecem com intensidade relevante."],
                ["Tempo x baseline", "O corte atual pode se afastar do baseline inicial de 60 segundos, revelando mudanca de energia, zona dominante, IPM, IDM ou risco."],
              ].map(([title, text]) => (
                <article key={title} className="rounded-lg border border-rose-300/20 bg-rose-400/5 p-5">
                  <h3 className="text-base font-black text-rose-100">{title}</h3>
                  <p className="mt-3 text-sm leading-7 text-slate-300">{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-14">
          <SectionHeading
            eyebrow="Base anonima"
            title="A inteligencia do FROID cresce pela experiencia anonima agregada."
            text="Com consentimento, anonimato e governanca, os cortes das sessoes podem alimentar uma base capaz de revelar benchmarks, associacoes, padroes raros, respostas a abordagens e caminhos que seriam impossiveis de mapear manualmente em escala humana."
          />
          <div className="mt-8 rounded-lg border border-white/10 bg-slate-900 p-6">
            <p className="text-sm leading-7 text-slate-300 md:text-base">
              Essa inteligencia deve ser tratada com rigor: ela nao decreta diagnosticos,
              nao substitui a avaliacao clinica e nao transforma correlacao em causalidade.
              Ela organiza sinais, levanta hipoteses, aponta relacoes psicossomaticas
              investigaveis e oferece ao profissional um mapa mais amplo para decidir,
              perguntar, acolher e, quando necessario, mudar o curso da sessao.
            </p>
          </div>
        </section>

        <section className="border-y border-cyan-300/20 bg-cyan-300/5">
          <div className="mx-auto grid max-w-7xl gap-6 px-5 py-12 lg:grid-cols-[1fr_0.8fr]">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">Convite aos profissionais</p>
              <h2 className="mt-3 text-3xl font-black text-white">Participe da primeira fase do FROID.</h2>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-300">
                Procuramos profissionais dispostos a testar uma ferramenta sem paralelo
                direto em sua proposta: unir psique, fala, corpo, face, voz, tempo,
                relatorio e inteligencia explicativa em uma mesma pratica clinica.
              </p>
            </div>
            <div className="grid gap-3">
              <div className="rounded-lg border border-cyan-300/30 bg-slate-950 p-5">
                <p className="text-sm font-black text-cyan-200">Primeiros 100 profissionais</p>
                <p className="mt-2 text-2xl font-black text-white">20 sessoes gratuitas</p>
              </div>
              <div className="rounded-lg border border-emerald-300/30 bg-slate-950 p-5">
                <p className="text-sm font-black text-emerald-200">Proximos 100 profissionais</p>
                <p className="mt-2 text-2xl font-black text-white">10 sessoes gratuitas</p>
              </div>
              <Link to="/access/register" className="rounded-lg bg-cyan-400 px-5 py-3 text-center text-sm font-black text-slate-950 hover:bg-cyan-300">
                Solicitar cadastro
              </Link>
            </div>
          </div>
        </section>

        <section className="bg-slate-950">
          <div className="mx-auto max-w-7xl px-5 py-12">
            <div className="mb-5">
              <h2 className="text-2xl font-black text-white">LGPD, consentimento e limites clinicos</h2>
              <p className="mt-3 max-w-4xl text-sm leading-7 text-slate-300">
                O FROID deve operar com consentimento destacado, minimizacao de dados,
                segregacao entre dados identificados e anonimizados, auditoria e exclusao
                formal quando solicitada. Os indicadores sao apoio tecnico ao profissional
                habilitado, nao diagnostico automatico.
              </p>
            </div>
            <LgpdNotice audience="home" />
          </div>
        </section>
      </main>
    </div>
  );
};

