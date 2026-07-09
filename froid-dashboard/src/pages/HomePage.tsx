import React from "react";
import { Link } from "react-router-dom";
import { LgpdNotice } from "../components/legal/LgpdNotice";

const heroImage = "/froid-home/facs-matrizes-emocionais.png";
const auImage = "/froid-home/facs-unidades-acao.png";
const facsMapImage = "/froid-home/facs-mapa-completo.png";

const navItems = [
  { label: "Inicio", to: "/" },
  { label: "Ciencia", to: "/froid/ciencia" },
  { label: "Tecnologia", to: "/froid/tecnologia" },
  { label: "Profissionais", to: "/froid/profissionais" },
];

const abilities = [
  {
    title: "Transcricao clinica em tempo real",
    brief:
      "Registra a fala na cadencia da sessao, separando profissional e paciente, para leitura, revisao e relatorio posterior.",
    detail:
      "A transcricao e a memoria semantica da consulta. Ela organiza a fala real, preserva a alternancia entre profissional e paciente e permite que o especialista acompanhe a narrativa sem perder a observacao corporal e vocal.",
    impact:
      "Permite revisar a sessao com precisao, localizar mudancas de tema, validar cortes e produzir relatorios clinicos mais completos.",
    visual: ["DR", "PAC", "Tema", "Resumo"],
  },
  {
    title: "Bioacustica vocal do paciente",
    brief:
      "Extrai F0, ZCR, Jitter, Shimmer, energia, pausas, cadencia, MFCC7, MFCC9 e sub-harmonicos vocais da trilha do paciente.",
    detail:
      "A voz e uma das expressoes mais diretas da dinamica interna. O FROID utiliza exclusivamente a trilha vocal do paciente para avaliar tensao, intensidade, tremores, pausas, aceleracao, retardo e sinais sub-harmonicos.",
    impact:
      "Ajuda o profissional a perceber mudancas autonomicas e emocionais que podem nao aparecer claramente no conteudo verbal.",
    visual: ["F0", "MFCC7", "MFCC9", "5-20Hz"],
  },
  {
    title: "FACS, AUs e microexpressoes",
    brief:
      "Mapeia unidades de acao facial, intensidade, assimetria, duracao e combinacoes expressivas associadas a matrizes emocionais.",
    detail:
      "O rosto e analisado como matriz dinamica de unidades de acao facial. O FROID cruza AUs isoladas e combinadas, assimetrias, intensidade e tempo de ativacao para apoiar a leitura de sinais expressivos sutis.",
    impact:
      "Amplia a capacidade de observar dor, contencao, surpresa, medo, tristeza mascarada, raiva contida e outras matrizes emocionais.",
    visual: ["AU1", "AU4", "AU15", "AU20"],
  },
  {
    title: "IPM e IDM",
    brief:
      "O IPM mede a intensidade global da mobilizacao emocional; o IDM aponta a direcao dominante do desequilibrio no mapa zonal.",
    detail:
      "O IPM funciona como velocimetro da energia emocional; o IDM aponta a direcao do desequilibrio nas zonas FROID. Ambos ganham valor quando comparados ao baseline inicial e aos cortes temporais.",
    impact:
      "Oferece uma leitura rapida da intensidade e da direcao do processo, permitindo ajustar a conducao clinica em tempo real.",
    visual: ["IPM", "IDM", "Delta", "Zona"],
  },
  {
    title: "Dissonancias e consonancias",
    brief:
      "Cruza voz, face, narrativa, zonas, riscos e baseline para apontar divergencias relevantes e coerencias expressivas.",
    detail:
      "A dissonancia e o aviso central do FROID: ela surge quando sinais efetivamente apurados ultrapassam a metrica definida e indicam divergencia entre narrativa, corpo, voz, face, zona ou intensidade emocional.",
    impact:
      "Ajuda o profissional a identificar pontos onde talvez seja necessario investigar, acolher, mudar o ritmo ou redirecionar a sessao.",
    visual: ["Fala", "Voz", "Face", "Zona"],
  },
  {
    title: "Cortes, temas e resumos",
    brief:
      "Consolida janelas obrigatorias de 10 minutos e cortes profissionais com tema, resumo e metricas correspondentes.",
    detail:
      "Os cortes transformam a sessao em blocos comparaveis. Cada janela preserva tema, resumo, metricas, tom, palavras por minuto, biomarcadores, zonas e dissonancias do periodo.",
    impact:
      "Permite acompanhar a evolucao da consulta, comparar momentos e reconstruir o percurso emocional com objetividade.",
    visual: ["0-10", "10-20", "20-30", "Corte"],
  },
  {
    title: "Relatorio da Consulta",
    brief:
      "Organiza baseline, medias, cortes, dissonancias, observacoes clinicas e selecao do profissional em um documento de revisao.",
    detail:
      "Ao final da sessao, o FROID organiza parametros iniciais, medias, cortes, temas, resumos, observacoes clinicas e dissonancias em um layout de composicao selecionavel pelo profissional.",
    impact:
      "Cria memoria clinica estruturada para revisao, supervisao, estudo de caso e continuidade terapeutica.",
    visual: ["Baseline", "Medias", "Cortes", "Notas"],
  },
  {
    title: "FROID Explica",
    brief:
      "Permite ao profissional perguntar sobre achados, metricas, fontes tecnicas e possiveis relacoes clinicas durante ou apos a sessao.",
    detail:
      "O FROID Explica e a camada de inteligencia que traduz sinais complexos em linguagem clinica. Ele pode responder perguntas, esclarecer metricas, relacionar achados e apoiar a interpretacao do relatorio.",
    impact:
      "Reduz a distancia entre dados tecnicos e decisao clinica, tornando a plataforma mais util durante a pratica real.",
    visual: ["Pergunta", "Fonte", "Metrica", "Resposta"],
  },
  {
    title: "Data Mart anonimo",
    brief:
      "Transforma metricas anonimizadas em base populacional para benchmarks, pesquisa, comparacao longitudinal e descoberta de padroes.",
    detail:
      "Com consentimento e governanca, as metricas anonimizadas das sessoes alimentam uma base populacional capaz de revelar padroes, benchmarks, associacoes e novas hipoteses de estudo.",
    impact:
      "Permite que o FROID evolua com dados agregados, preservando privacidade e fortalecendo pesquisa em saude mental.",
    visual: ["Anonimo", "k>=50", "Benchmark", "Padroes"],
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

function AbilityVisual({
  title,
  visual,
  index,
}: {
  title: string;
  visual: string[];
  index: number;
}) {
  return (
    <div className="rounded-lg border border-cyan-300/20 bg-slate-950 p-4 shadow-2xl shadow-cyan-950/20">
      <div className="rounded-md border border-white/10 bg-slate-900 p-4">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs font-black uppercase tracking-[0.22em] text-cyan-300">
            Imagem conceitual
          </span>
          <span className="rounded bg-cyan-400/15 px-2 py-1 text-xs font-black text-cyan-200">
            {String(index + 1).padStart(2, "0")}
          </span>
        </div>
        <div className="mt-5 grid min-h-[220px] place-items-center rounded-md border border-white/10 bg-slate-950 p-5">
          <div className="relative flex h-44 w-44 items-center justify-center rounded-full border border-cyan-300/40 bg-cyan-300/5">
            <div className="absolute h-28 w-28 rounded-full border border-emerald-300/35" />
            <div className="absolute h-16 w-16 rounded-full border border-rose-300/35" />
            <p className="max-w-[120px] text-center text-sm font-black leading-5 text-white">
              {title}
            </p>
            {visual.map((item, itemIndex) => {
              const positions = [
                "left-1/2 top-0 -translate-x-1/2 -translate-y-1/2",
                "right-0 top-1/2 translate-x-1/2 -translate-y-1/2",
                "bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2",
                "left-0 top-1/2 -translate-x-1/2 -translate-y-1/2",
              ];
              return (
                <span
                  key={item}
                  className={`absolute ${positions[itemIndex] || positions[0]} rounded border border-white/10 bg-slate-800 px-2 py-1 text-xs font-black text-cyan-100`}
                >
                  {item}
                </span>
              );
            })}
          </div>
        </div>
        <div className="mt-3 rounded border border-dashed border-white/15 bg-white/[0.03] p-3">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">
            Espaco preparado para video ou imagem especifica
          </p>
        </div>
      </div>
    </div>
  );
}

function AbilitySection({
  title,
  brief,
  detail,
  impact,
  visual,
  index,
}: {
  title: string;
  brief: string;
  detail: string;
  impact: string;
  visual: string[];
  index: number;
}) {
  const reversed = index % 2 === 1;
  return (
    <section className="border-t border-white/10">
      <div
        className={`mx-auto grid max-w-7xl gap-8 px-5 py-12 lg:grid-cols-[0.95fr_1.05fr] ${
          reversed ? "lg:[&>*:first-child]:order-2" : ""
        }`}
      >
        <div>
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-cyan-400/15 text-sm font-black text-cyan-200">
              {String(index + 1).padStart(2, "0")}
            </span>
            <p className="text-xs font-black uppercase tracking-[0.28em] text-cyan-300">
              Habilidade FROID
            </p>
          </div>
          <h3 className="mt-4 text-3xl font-black leading-tight text-white">{title}</h3>
          <p className="mt-4 text-base font-semibold leading-8 text-cyan-100">{brief}</p>
          <div className="mt-6 grid gap-3">
            <div className="rounded-lg border border-white/10 bg-slate-900 p-5">
              <p className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">Como funciona</p>
              <p className="mt-3 text-sm leading-7 text-slate-300">{detail}</p>
            </div>
            <div className="rounded-lg border border-emerald-300/20 bg-emerald-300/5 p-5">
              <p className="text-xs font-black uppercase tracking-[0.2em] text-emerald-200">Valor para o profissional</p>
              <p className="mt-3 text-sm leading-7 text-slate-300">{impact}</p>
            </div>
          </div>
        </div>
        <AbilityVisual title={title} visual={visual} index={index} />
      </div>
    </section>
  );
}

function ImagePanel({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white p-3 shadow-2xl shadow-cyan-950/30">
      <img src={src} alt={alt} className="h-auto max-h-[620px] w-full object-contain" />
    </div>
  );
}

function SignalConsole() {
  const rows = [
    ["Voz", "MFCC7, MFCC9, F0, ZCR, Jitter, Shimmer"],
    ["Face", "AUs, assimetria, onset, apex, offset"],
    ["Semantica", "tema, valencia, resumo, contradicao"],
    ["Tempo", "baseline, cortes, medias, delta"],
  ];
  return (
    <div className="rounded-lg border border-cyan-300/25 bg-slate-950 p-4 shadow-2xl shadow-cyan-950/30">
      <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-3">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.28em] text-cyan-300">FROID OS</p>
          <p className="mt-1 text-sm font-bold text-white">Fusao multimodal ativa</p>
        </div>
        <span className="rounded bg-emerald-300/10 px-2 py-1 text-xs font-black text-emerald-200">
          500ms
        </span>
      </div>
      <div className="mt-4 grid gap-3">
        {rows.map(([label, value], index) => (
          <div key={label} className="grid grid-cols-[96px_1fr] items-center gap-3">
            <p className="text-xs font-black uppercase tracking-[0.14em] text-cyan-200">{label}</p>
            <div className="rounded border border-white/10 bg-white/[0.03] p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-slate-300">{value}</span>
                <span className="text-xs font-black text-white">{92 - index * 7}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                <div
                  className="h-full rounded-full bg-cyan-300"
                  style={{ width: `${92 - index * 7}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 grid grid-cols-3 gap-3">
        {["IPM", "IDM", "Dissonancia"].map((item) => (
          <div key={item} className="rounded border border-cyan-300/15 bg-cyan-300/5 p-3 text-center">
            <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-400">{item}</p>
            <p className="mt-1 text-lg font-black text-cyan-100">ativo</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export const HomePage: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <Header />

      <main>
        <section
          className="relative overflow-hidden border-b border-white/10 bg-slate-950"
          style={{
            backgroundImage:
              "radial-gradient(circle at 1px 1px, rgba(103,232,249,.12) 1px, transparent 0)",
            backgroundSize: "28px 28px",
          }}
        >
          <div className="mx-auto grid min-h-[82vh] max-w-7xl items-center gap-10 px-5 py-16 lg:grid-cols-[0.96fr_1.04fr]">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.38em] text-cyan-300">
                Frequency Recognition of Internal Dynamics
              </p>
              <h1 className="mt-5 text-4xl font-black leading-[1.03] text-white md:text-6xl">
                FROID decifra a coerencia entre psique, voz, face e narrativa.
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-8 text-slate-200 md:text-lg">
                Uma plataforma de percepcao clinica aumentada para profissionais de
                saude mental: bioacustica vocal, FACS, AUs, transcricao, IPM, IDM,
                dissonancias, Data Mart anonimo e FROID Explica trabalhando como um
                unico organismo de apoio clinico.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link to="/access/register" className="rounded-lg bg-cyan-400 px-5 py-3 text-sm font-black text-slate-950 hover:bg-cyan-300">
                  Cadastrar profissional
                </Link>
                <Link to="/login" className="rounded-lg border border-white/20 px-5 py-3 text-sm font-black text-white hover:bg-white/10">
                  Entrar no FROID
                </Link>
                <Link to="/froid/tecnologia" className="rounded-lg border border-cyan-300/50 px-5 py-3 text-sm font-black text-cyan-100 hover:bg-cyan-300/10">
                  Ver tecnologia
                </Link>
              </div>
              <div className="mt-7 grid gap-3 text-sm leading-6 text-slate-300 md:grid-cols-2">
                <p className="rounded-lg border border-cyan-300/15 bg-cyan-300/5 p-4">
                  20 sessoes gratuitas para os primeiros 100 profissionais cadastrados.
                </p>
                <p className="rounded-lg border border-emerald-300/20 bg-emerald-300/5 p-4">
                  10 sessoes gratuitas para os proximos 100 profissionais.
                </p>
              </div>
            </div>

            <div className="grid gap-4">
              <SignalConsole />
              <div className="rounded-lg border border-white/10 bg-white p-3 shadow-2xl shadow-cyan-950/30">
                <img
                  src={heroImage}
                  alt="Mapa das expressoes faciais e matrizes emocionais do FROID"
                  className="h-auto max-h-[430px] w-full object-contain"
                />
              </div>
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
              title="Nove habilidades centrais, descritas uma a uma."
              text="Cada habilidade do FROID representa uma camada de observacao clinica. A magnitude da plataforma aparece quando essas camadas deixam de ser telas isoladas e passam a trabalhar como um unico sistema de leitura da sessao."
            />
          </div>
          <div className="border-t border-white/10">
            {abilities.map((ability, index) => (
              <AbilitySection key={ability.title} {...ability} index={index} />
            ))}
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
          <div className="grid gap-4">
            <ImagePanel src={auImage} alt="Mapa completo das unidades de acao facial FACS no FROID" />
            <ImagePanel src={facsMapImage} alt="Mapa FACS com descritores de acao e regioes anatomicas" />
          </div>
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
              <Link to="/login" className="rounded-lg border border-white/20 px-5 py-3 text-center text-sm font-black text-white hover:bg-white/10">
                Entrar no FROID
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
