import React from "react";
import { Link } from "react-router-dom";
import { LgpdNotice } from "../components/legal/LgpdNotice";

const scienceBlocks = [
  {
    title: "A Ciencia da Transparencia",
    text:
      "O FROID opera com uma formulacao fisico-matematica auditavel. A linha de base dinamica usa os primeiros 60 segundos para calibrar F0, Jitter, Shimmer e energia vocal media, permitindo comparar desvios posteriores com a referencia individual do paciente.",
  },
  {
    title: "Biopsia Espectral e Bioacustica",
    text:
      "O motor FROID-Voice analisa bandas espectrais, MFCC7, MFCC9, ZCR, infrassons vocais e sub-harmonicos para apoiar a leitura clinica da fala, da tensao autonomica e de padroes de risco ao longo da sessao.",
  },
  {
    title: "Morfodinamica Facial FACS",
    text:
      "O FROID-Face cruza microexpressoes, unidades de acao facial, assimetrias e marcadores temporais para ampliar a percepcao do profissional sem substituir seu julgamento clinico.",
  },
  {
    title: "Bussola IPM x IDM",
    text:
      "O IPM mede a intensidade global da energia emocional, enquanto o IDM aponta a direcao do desequilibrio. A dissonancia nasce do cruzamento entre semantica, voz, face e zonas FROID.",
  },
  {
    title: "Data-FROID e Evidencias",
    text:
      "As features anonimizadas podem alimentar benchmarks e analises populacionais com governanca, k-anonimato e trilhas de auditoria para apoiar pesquisa, comparacao longitudinal e medicina de precisao psicologica.",
  },
];

const plans = [
  { name: "Acesso livre", price: "US$ 0.00", detail: "Entrada livre ao sistema" },
  { name: "Pacote profissional", price: "US$ 1.50", detail: "25 sessoes" },
  { name: "Desenvolvedores", price: "US$ 2.50", detail: "25 sessoes de teste" },
];

export const HomePage: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
          <Link to="/" className="text-sm font-black tracking-[0.42em] text-cyan-300">
            FROID
          </Link>
          <nav className="flex items-center gap-2 text-xs font-bold">
            <a href="#ciencia" className="rounded-md px-3 py-2 text-slate-300 hover:bg-white/10">
              Ciencia
            </a>
            <a href="#planos" className="rounded-md px-3 py-2 text-slate-300 hover:bg-white/10">
              Planos
            </a>
            <Link to="/access/register" className="rounded-md px-3 py-2 text-slate-300 hover:bg-white/10">
              Cadastro
            </Link>
            <Link to="/login" className="rounded-md bg-cyan-500 px-4 py-2 text-slate-950 hover:bg-cyan-300">
              Login
            </Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="mx-auto grid min-h-[72vh] max-w-7xl items-center gap-10 px-5 py-14 lg:grid-cols-[1.08fr_0.92fr]">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.38em] text-cyan-300">
              Frequency Recognition of Internal Dynamics
            </p>
            <h1 className="mt-5 max-w-4xl text-4xl font-black leading-tight text-white md:text-6xl">
              Plataforma de Percepcao Clinica Aumentada
            </h1>
            <p className="mt-6 max-w-3xl text-base leading-8 text-slate-300">
              O FROID integra bioacustica vocal, decodificacao morfodinamica facial
              e processamento semantico para apoiar psiquiatras, psicologos e
              pesquisadores na leitura em tempo real da dinamica interna da sessao.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to="/login"
                className="rounded-lg bg-cyan-400 px-5 py-3 text-sm font-black text-slate-950 hover:bg-cyan-300"
              >
                Entrar no FROID
              </Link>
              <Link
                to="/access/register"
                className="rounded-lg border border-cyan-300/40 px-5 py-3 text-sm font-black text-cyan-100 hover:bg-cyan-300/10"
              >
                Criar cadastro profissional
              </Link>
            </div>
          </div>

          <div className="rounded-lg border border-cyan-300/20 bg-slate-900 p-5 shadow-2xl shadow-cyan-950/40">
            <div className="grid gap-3">
              {["Voz", "Face", "Semantica", "IPM", "IDM", "Dissonancias"].map((item, index) => (
                <div key={item} className="flex items-center gap-3 rounded-md border border-white/10 bg-white/[0.03] p-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded bg-cyan-400/15 text-xs font-black text-cyan-200">
                    {index + 1}
                  </span>
                  <div>
                    <p className="font-black text-white">{item}</p>
                    <p className="text-xs text-slate-400">
                      leitura integrada para apoio clinico e analise longitudinal
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="ciencia" className="border-y border-white/10 bg-slate-900/70">
          <div className="mx-auto max-w-7xl px-5 py-12">
            <h2 className="text-2xl font-black text-white">Arquitetura FROID</h2>
            <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {scienceBlocks.map((block) => (
                <article key={block.title} className="rounded-lg border border-slate-700 bg-slate-950 p-5">
                  <h3 className="text-base font-black text-cyan-200">{block.title}</h3>
                  <p className="mt-3 text-sm leading-7 text-slate-300">{block.text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="planos" className="mx-auto max-w-7xl px-5 py-12">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-2xl font-black text-white">Planos de acesso</h2>
              <p className="mt-2 text-sm text-slate-400">
                Escolha o pacote no cadastro profissional e conclua o pagamento via Stripe.
              </p>
            </div>
            <Link to="/access/register" className="rounded-lg bg-white px-4 py-2 text-sm font-black text-slate-950">
              Selecionar plano
            </Link>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {plans.map((plan) => (
              <div key={plan.name} className="rounded-lg border border-white/10 bg-white/[0.03] p-5">
                <p className="text-sm font-black text-slate-200">{plan.name}</p>
                <p className="mt-3 text-3xl font-black text-cyan-200">{plan.price}</p>
                <p className="mt-2 text-sm text-slate-400">{plan.detail}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="lgpd" className="border-t border-white/10 bg-slate-900/70">
          <div className="mx-auto max-w-7xl px-5 py-12">
            <div className="mb-5">
              <h2 className="text-2xl font-black text-white">
                Governanca LGPD e dados sensiveis
              </h2>
              <p className="mt-2 max-w-4xl text-sm leading-7 text-slate-300">
                O FROID foi concebido para operar com minimizacao de dados,
                consentimento destacado, auditoria, seguranca e anonimização de
                bases populacionais. A conformidade real depende da configuracao
                tecnica, dos contratos e da governanca de cada profissional ou
                instituicao usuaria.
              </p>
            </div>
            <LgpdNotice audience="home" />
          </div>
        </section>
      </main>
    </div>
  );
};
