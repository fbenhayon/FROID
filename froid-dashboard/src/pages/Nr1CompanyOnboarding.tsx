import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";
import {
  acceptanceFor,
  documentosDaAudiencia,
  loadLegalCatalog,
  type LegalCatalog,
} from "../lib/legal";
import {
  caminhoDoPorte,
  exigeCenso,
  exigidoNaCampanha,
  exigidoNoRecorte,
  PISO_CAMPANHA,
  PISO_RECORTE,
} from "../lib/nr1-representatividade";
import { GlossarioDeSiglas, Sigla } from "../lib/siglas";
import { Nr1ExplicaPainel } from "../components/nr1/Nr1ExplicaPainel";

/**
 * Cadastro guiado da empresa contratante do NR-1.
 *
 * Não é uma variação do cadastro de clínica. A empresa entra como
 * `account_type: "nr1_company"`, que produz uma organização do tipo
 * `enterprise` — e é só nesse tipo que o servidor retira dos papéis do
 * empregador as permissões clínicas identificadas. Cadastrada como clínica, a
 * empresa manteria acesso a prontuário, que é exatamente a fronteira que o
 * produto existe para sustentar.
 *
 * A ordem dos passos segue a dependência real, não a estética: sem organização
 * não há unidade; sem estabelecimento não há setor; sem setor não há recorte
 * publicável. O piso de anonimato é avisado no passo em que o efetivo é
 * digitado, e não no fim — descobrir que a unidade é pequena depois de montar
 * tudo é a conversa ruim que a página de diagnóstico existe para evitar.
 */

// O aviso de porte deixou de ser uma constante. Havia um `PISO_UNIDADE = 75`
// aqui, herdado de quando o unico portao era o de anonimato (50 respostas com
// adesao de ~65%). Desde a migration 025 vale tambem o portao de
// representatividade, e ele depende do efetivo: abaixo de 98 pessoas a amostra
// necessaria alcanca o quadro inteiro e a unidade so publica em censo. Manter
// os 75 fazia a tela prometer resultado que o banco ia suprimir.
function avisoDeRecorte(efetivo: number): string | null {
  const exigido = exigidoNoRecorte(efetivo);
  if (exigido === null || efetivo <= 0) return null;
  if (exigeCenso(efetivo)) {
    return (
      `Uma unidade de ${efetivo} trabalhadores só publica recorte próprio em ` +
      `censo: as ${efetivo} precisam responder. Abaixo de 98 pessoas a amostra ` +
      "necessária para falar pelo efetivo alcança o quadro inteiro — é onde o " +
      "Guia MTE indica diálogo e observação da atividade no lugar do questionário."
    );
  }
  return (
    `Uma unidade de ${efetivo} trabalhadores precisa de ${exigido} respostas ` +
    "substantivas para publicar recorte próprio."
  );
}

const CONTATO = "froid@froid.com.br";

type Unidade = {
  unit_id: string;
  parent_unit_id: string | null;
  unit_type: "site" | "sector" | "exposure_group";
  name: string;
  external_code: string;
  headcount: number;
  status: string;
  child_count: number;
};

type Props = {
  user: FroidUser | null;
  onUserChange?: (user: FroidUser) => void;
  onLogout?: () => void;
};

function token() {
  return localStorage.getItem("froid_token") || "";
}

async function chamar(caminho: string, init?: RequestInit) {
  const resposta = await fetch(apiUrl(caminho), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token()}`,
      ...(init?.headers || {}),
    },
  });
  const texto = await resposta.text();
  const corpo = texto ? JSON.parse(texto) : {};
  if (!resposta.ok) {
    const erro = new Error(corpo?.detail || `falha ${resposta.status}`);
    // A liberacao pendente nao e uma falha do preenchimento: e um passo
    // comercial que falta. Tratar as duas do mesmo jeito faz a pessoa reler o
    // formulario atras de um erro que nao esta la.
    (erro as Error & { aguardandoLiberacao?: boolean }).aguardandoLiberacao =
      resposta.status === 403 && Boolean(corpo?.approval_pending);
    throw erro;
  }
  return corpo;
}

const Passo: React.FC<{ numero: number; atual: number; titulo: string }> = ({
  numero,
  atual,
  titulo,
}) => (
  <div className="flex items-center gap-2">
    <span
      className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-black ${
        atual > numero
          ? "bg-emerald-600 text-white"
          : atual === numero
            ? "bg-amber-500 text-amber-950"
            : "bg-slate-700 text-slate-400"
      }`}
    >
      {atual > numero ? "✓" : numero}
    </span>
    <span
      className={`text-xs font-bold ${
        atual === numero ? "text-amber-300" : "text-slate-400"
      }`}
    >
      {titulo}
    </span>
  </div>
);

const Campo: React.FC<{
  rotulo: string;
  valor: string;
  onChange: (v: string) => void;
  obrigatorio?: boolean;
  placeholder?: string;
  tipo?: string;
}> = ({ rotulo, valor, onChange, obrigatorio, placeholder, tipo = "text" }) => (
  <label className="block">
    <span className="text-xs font-black text-slate-300">
      {rotulo}
      {obrigatorio && <span className="ml-1 text-red-300">*</span>}
    </span>
    <input
      type={tipo}
      value={valor}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-amber-500"
    />
  </label>
);

export const Nr1CompanyOnboarding: React.FC<Props> = ({ user, onUserChange, onLogout }) => {
  const [passo, setPasso] = useState(1);
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  const [razaoSocial, setRazaoSocial] = useState("");
  const [nomeFantasia, setNomeFantasia] = useState("");
  const [cnpj, setCnpj] = useState("");
  const [responsavel, setResponsavel] = useState(user?.name || "");
  const [cargo, setCargo] = useState("");
  // O empregador e controlador do dado agregado, e a base legal do
  // tratamento e obrigacao legal (LGPD art. 7o II e art. 11 II "a"), nao
  // consentimento do trabalhador — que a relacao de hierarquia
  // comprometeria. Reconhecer isso e ato dele, e por isso e uma caixa que
  // ele marca, e nao um campo que o formulario preenche sozinho.
  const [reconhece, setReconhece] = useState(false);
  const [aguardandoLiberacao, setAguardandoLiberacao] = useState(false);
  // O contrato do NR-1 e um documento proprio, com objeto proprio. Ate
  // 22/08/2026 a empresa nao assinava nada — required_document_keys devolvia
  // o contrato de PROFISSIONAL para ela, o que teria produzido registro
  // juridico falso se o aceite estivesse ligado.
  const [catalogo, setCatalogo] = useState<LegalCatalog | null>(null);
  // Qual documento está aberto para leitura, por chave. Era um booleano
  // quando havia um documento só; agora são dois — contrato e termos —
  // e abrir um fecha o outro, que é o que se espera de uma sanfona.
  const [documentoAberto, setDocumentoAberto] = useState("");
  const [contratoAceito, setContratoAceito] = useState(false);
  const [telefone, setTelefone] = useState("");

  const [unidades, setUnidades] = useState<Unidade[]>([]);
  const [novoSite, setNovoSite] = useState({ name: "", headcount: "", code: "" });
  const [novoSetor, setNovoSetor] = useState({ name: "", headcount: "", parent: "" });

  // A organização nasce no passo 1, e o usuário recém-criado não tem
  // active_organization_id em lugar nenhum. O id chega na resposta do próprio
  // salvamento; sem guardá-lo aqui, a chamada do passo 2 sairia com a URL
  // truncada em /api/organizations//nr1/units.
  const [organizationId, setOrganizationId] = useState(
    user?.active_organization_id || "",
  );

  // A empresa JA cadastrada precisava redigitar tudo para chegar aos
  // estabelecimentos, e isso e um beco.
  //
  // `setPasso(2)` so acontecia dentro de `salvarEmpresa`, e os campos do passo
  // 1 nasciam vazios. Quem voltasse para acrescentar uma filial — que e
  // exatamente o motivo pelo qual esta rota continua alcancavel — caia num
  // formulario em branco cuja unica saida para a frente era reescrever razao
  // social, CNPJ e responsavel. Na frente de um cliente, redigitar o CNPJ dele
  // para conseguir cadastrar a filial e o momento em que o produto parece
  // frageil.
  const [jaCadastrada, setJaCadastrada] = useState(false);

  useEffect(() => {
    let ativo = true;
    chamar("/api/professional/profile")
      .then((dados) => {
        if (!ativo) return;
        const perfil = dados?.profile;
        if (!perfil || String(perfil.account_type || "") !== "nr1_company") return;
        setJaCadastrada(true);
        setRazaoSocial((v) => v || String(perfil.organization_legal_name || ""));
        setNomeFantasia((v) => v || String(perfil.organization_name || ""));
        setCnpj((v) => v || String(perfil.organization_document || ""));
        setResponsavel((v) => v || String(perfil.owner_name || ""));
        setCargo((v) => v || String(perfil.profession || ""));
        setTelefone((v) => v || String(perfil.phone || ""));
        // O reconhecimento de tratamento de dados e fato ja registrado, e
        // remarca-lo a cada visita seria pedir duas vezes a mesma declaracao.
        if (perfil.lgpd_acknowledged) setReconhece(true);
        // `contratoAceito` NUNCA e pre-marcado. Ele nao descreve um fato
        // gravado: e o ato que a pessoa esta praticando agora, e marca-lo por
        // ela e assinar no lugar dela.
        if (!organizationId) {
          const primeira = Array.isArray(dados?.organizations)
            ? dados.organizations[0]
            : null;
          if (primeira?.organization_id) setOrganizationId(String(primeira.organization_id));
        }
      })
      // Perfil indisponivel nao trava o cadastro novo, que e o caminho em que
      // ele legitimamente nao existe.
      .catch(() => undefined);
    return () => {
      ativo = false;
    };
  }, [organizationId]);

  const carregarUnidades = useCallback(async () => {
    if (!organizationId) return;
    try {
      const dados = await chamar(`/api/organizations/${organizationId}/nr1/units`);
      setUnidades(dados.units || []);
    } catch (e) {
      const falha = e as Error & { aguardandoLiberacao?: boolean };
      if (falha.aguardandoLiberacao) setAguardandoLiberacao(true);
      setErro(String(falha.message));
    }
  }, [organizationId]);

  useEffect(() => {
    if (passo >= 2) void carregarUnidades();
  }, [passo, carregarUnidades]);

  const estabelecimentos = useMemo(
    () => unidades.filter((u) => u.unit_type === "site"),
    [unidades],
  );
  const setores = useMemo(
    () => unidades.filter((u) => u.unit_type === "sector"),
    [unidades],
  );
  const efetivoTotal = useMemo(
    () => estabelecimentos.reduce((total, site) => total + site.headcount, 0),
    [estabelecimentos],
  );
  // Qual caminho de conformidade este porte sustenta. O passo final deixou de
  // assumir campanha: uma empresa de 30 pessoas montava a estrutura inteira e
  // recebia uma lista do que faltava "antes da primeira campanha" que nunca
  // ia publicar nada. A AEP, que atende essa empresa e e obrigatoria para ela,
  // nao era sequer mencionada.
  const caminho = caminhoDoPorte(efetivoTotal);

  useEffect(() => {
    loadLegalCatalog("BR")
      .then(setCatalogo)
      // Catalogo indisponivel nao derruba o cadastro: o servidor decide se o
      // aceite e obrigatorio, e recusa sozinho se for.
      .catch(() => setCatalogo(null));
  }, []);

  // Os documentos que esta audiência aceita, menos a privacidade, que tem
  // caixa própria mais acima — reconhecer tratamento de dados e contratar
  // um serviço são dois atos, e juntá-los num só clique enfraquece os dois.
  const paraAceitar = documentosDaAudiencia(catalogo, "nr1_company").filter(
    ([chave]) => chave !== "privacy",
  );

  const salvarEmpresa = async () => {
    setErro("");
    if (!razaoSocial.trim() || !cnpj.trim() || !responsavel.trim()) {
      setErro("Razão social, CNPJ e responsável são obrigatórios.");
      return;
    }
    if (cnpj.replace(/\D/g, "").length !== 14) {
      setErro("O CNPJ precisa ter 14 dígitos.");
      return;
    }
    if (!reconhece) {
      setErro(
        "É preciso reconhecer o tratamento de dados antes de concluir o cadastro.",
      );
      return;
    }
    // O aceite e exigido SEMPRE nesta tela, e nao so quando
    // FROID_LEGAL_ACCEPTANCE_REQUIRED esta ligado no servidor.
    //
    // Aquela variavel e global e vale `false` por padrao — ela governa tambem
    // o cadastro clinico e o TCLE do paciente, onde o aceite pode ser
    // dispensavel conforme a jurisdicao. Aqui nao pode: este formulario
    // CONTRATA um servico pago de conformidade. Concluir a contratacao sem
    // prova de aceite produz exatamente o cenario que o comprovante existe
    // para evitar — e foi o que aconteceu no primeiro cadastro real, que
    // respondeu sucesso e deixou o livro de aceites vazio.
    //
    // O servidor grava o aceite valido mesmo com a exigencia desligada
    // (_validated_legal_acceptances registra o que e valido em qualquer caso),
    // entao basta a tela nao deixar passar sem ele.
    if (!paraAceitar.length) {
      setErro(
        "Os documentos desta contratação não puderam ser carregados, e sem " +
          "eles não há o que aceitar. Recarregue a página; se persistir, " +
          `escreva para ${CONTATO} — o cadastro não foi concluído de propósito, ` +
          "para não registrar contratação sem aceite.",
      );
      return;
    }
    if (!contratoAceito) {
      setErro("É preciso aceitar o contrato de prestação de serviço para continuar.");
      return;
    }
    setSalvando(true);
    try {
      const dados = await chamar("/api/professional/profile", {
        method: "POST",
        body: JSON.stringify({
          account_type: "nr1_company",
          owner_name: responsavel.trim(),
          organization_name: nomeFantasia.trim() || razaoSocial.trim(),
          organization_legal_name: razaoSocial.trim(),
          organization_document: cnpj.replace(/\D/g, ""),
          profession: cargo.trim(),
          phone: telefone.trim(),
          lgpd_acknowledged: true,
          lgpd_acknowledged_at: new Date().toISOString(),
          legal_jurisdiction: "BR",
          // Os documentos vêm do catálogo pela AUDIÊNCIA, e não fixados aqui.
          //
          // Fixá-los quebrou uma vez: em 25/08/2026 os termos se separaram em
          // "terms" (Psique) e "terms_nr1", e esta tela continuaria registrando
          // aceite dos termos do produto clínico. O servidor exige `terms_nr1`,
          // não receberia, e o cadastro responderia "sucesso" sem liberar o
          // acesso — que é o defeito mais caro de diagnosticar, porque parece
          // problema de permissão e está a três camadas de distância.
          //
          // A privacidade tem aceite próprio (`reconhece`); os demais seguem o
          // aceite do contrato, que é o que a pessoa marca na tela.
          legal_acceptances: Object.fromEntries(
            documentosDaAudiencia(catalogo, "nr1_company").map(([chave, doc]) => [
              chave,
              acceptanceFor(doc, chave === "privacy" ? reconhece : contratoAceito),
            ]),
          ),
        }),
      });
      const orgId = String(dados?.organization_id || "");
      if (!orgId) {
        // Falhar aqui com uma frase e melhor do que seguir para o passo 2 e
        // receber 404 numa URL truncada, que nao diz nada a quem esta
        // cadastrando.
        setErro(
          "A empresa foi salva, mas o servidor não devolveu o identificador da " +
            "organização. Recarregue a página; se persistir, escreva para " +
            `${CONTATO}.`,
        );
        return;
      }
      setOrganizationId(orgId);
      if (user && onUserChange) {
        onUserChange({
          ...user,
          active_organization_id: orgId,
          access_status: dados?.access_status ?? user.access_status,
        });
      }
      setPasso(2);
    } catch (e) {
      const falha = e as Error & { aguardandoLiberacao?: boolean };
      if (falha.aguardandoLiberacao) setAguardandoLiberacao(true);
      setErro(String(falha.message));
    } finally {
      setSalvando(false);
    }
  };

  const criarUnidade = async (
    tipo: "site" | "sector",
    nome: string,
    efetivo: string,
    pai?: string,
    codigo?: string,
  ) => {
    setErro("");
    if (!nome.trim()) {
      setErro("Informe o nome.");
      return;
    }
    setSalvando(true);
    try {
      await chamar(`/api/organizations/${organizationId}/nr1/units`, {
        method: "POST",
        body: JSON.stringify({
          unit_type: tipo,
          name: nome.trim(),
          headcount: Number(efetivo) || 0,
          parent_unit_id: pai || null,
          external_code: codigo || "",
        }),
      });
      await carregarUnidades();
      if (tipo === "site") setNovoSite({ name: "", headcount: "", code: "" });
      else setNovoSetor({ name: "", headcount: "", parent: pai || "" });
    } catch (e) {
      const falha = e as Error & { aguardandoLiberacao?: boolean };
      if (falha.aguardandoLiberacao) setAguardandoLiberacao(true);
      setErro(String(falha.message));
    } finally {
      setSalvando(false);
    }
  };

  const arquivar = async (unitId: string) => {
    setErro("");
    try {
      await chamar(`/api/organizations/${organizationId}/nr1/units/${unitId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "archived" }),
      });
      await carregarUnidades();
    } catch (e) {
      const falha = e as Error & { aguardandoLiberacao?: boolean };
      if (falha.aguardandoLiberacao) setAguardandoLiberacao(true);
      setErro(String(falha.message));
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <header className="border-b border-slate-700 bg-slate-900">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-5 py-4">
          <Link to="/" className="text-sm font-black tracking-[0.35em] text-amber-500">
            FROID NR-1
          </Link>
          <div className="flex items-center gap-3">
            {/* Estrutura da empresa e onde nasce a duvida sobre setor pequeno
                demais para publicar recorte proprio. O verbete responde antes
                de a pessoa cadastrar errado e descobrir no fim do ciclo. */}
            <div className="flex items-center border-l border-slate-800 pl-3">
              <Link
                to="/nr1/explica?verbete=setor-pequeno"
                title="Perguntas sobre a norma, sobre a metodologia e sobre como ler o resultado — com a fonte normativa."
                className="rounded border border-cyan-700 bg-cyan-950 px-4 py-2 text-xs font-black text-cyan-100 hover:bg-cyan-900"
              >
                FROID Explica NR-1
              </Link>
            </div>
            {onLogout && (
              <button
                type="button"
                onClick={onLogout}
                className="rounded-md bg-slate-950 px-3 py-2 text-xs font-black text-white"
              >
                Sair
              </button>
            )}
          </div>
        </div>
      </header>

      <div className="mx-auto grid w-full max-w-[104rem] items-start gap-4 px-3 xl:grid-cols-[minmax(0,1fr)_400px]">
      <main className="w-full min-w-0 px-5 py-8">
        <div className="flex flex-wrap gap-4">
          <Passo numero={1} atual={passo} titulo="A empresa" />
          <Passo numero={2} atual={passo} titulo="Estabelecimentos" />
          <Passo numero={3} atual={passo} titulo="Setores" />
          <Passo numero={4} atual={passo} titulo="Conferência" />
        </div>

        {aguardandoLiberacao ? (
          <section className="mt-5 rounded-lg border border-amber-700 bg-amber-950/40 p-5">
            <p className="text-sm font-black text-amber-200">
              Cadastro recebido. Falta a liberação da equipe FROID.
            </p>
            <p className="mt-2 text-sm leading-6 text-amber-100">
              O que você preencheu até aqui está salvo. A avaliação de riscos
              psicossociais é um serviço contratado, e a liberação para operar o
              módulo — abrir campanha, gerar inventário e plano de ação — é o
              passo em que a contratação se confirma. Não é uma checagem do que
              você digitou.
            </p>
            <p className="mt-3 text-sm leading-6 text-amber-100">
              Escreva para{" "}
              <a className="font-black text-amber-300 underline" href={`mailto:${CONTATO}`}>
                {CONTATO}
              </a>{" "}
              informando o CNPJ cadastrado. Assim que a liberação sair, volte a
              esta página e o cadastro continua de onde parou.
            </p>
          </section>
        ) : (
          erro && (
            <p className="mt-5 rounded-lg border border-red-800 bg-red-950/60 px-3 py-2 text-sm font-bold text-red-200">
              {erro}
            </p>
          )
        )}

        {passo === 1 && (
          <section className="mt-6">
            <h1 className="text-2xl font-black">Quem é a empresa contratante</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              A avaliação é contratada pelo empregador e responde por um{" "}
              <Sigla nome="CNPJ" />. Pessoas diferentes da mesma empresa que se
              cadastrarem com este CNPJ passam a enxergar a mesma estrutura e as
              mesmas campanhas.
            </p>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <Campo rotulo="Razão social" valor={razaoSocial} onChange={setRazaoSocial} obrigatorio />
              <Campo rotulo="Nome fantasia" valor={nomeFantasia} onChange={setNomeFantasia} />
              <Campo rotulo="CNPJ" valor={cnpj} onChange={setCnpj} obrigatorio placeholder="00.000.000/0001-00" />
              <Campo rotulo="Telefone" valor={telefone} onChange={setTelefone} />
              <Campo rotulo="Responsável pelo programa" valor={responsavel} onChange={setResponsavel} obrigatorio />
              <Campo rotulo="Cargo" valor={cargo} onChange={setCargo} placeholder="SESMT, RH, segurança do trabalho..." />
            </div>

            <div className="mt-5 rounded-lg border border-amber-800 bg-amber-950/40 p-4 text-xs leading-5 text-amber-100">
              <strong className="text-amber-200">O que este cadastro não dá acesso.</strong>{" "}
              A empresa contratante recebe resultados agregados por unidade e por
              dimensão. Não recebe resposta individual de trabalhador, não recebe
              prontuário e não recebe dado clínico — a separação é estrutural, e
              não uma configuração que se possa desligar depois.
            </div>

            <label className="mt-4 flex items-start gap-3 rounded-lg border border-slate-700 bg-slate-950 p-4">
              <input
                type="checkbox"
                checked={reconhece}
                onChange={(e) => setReconhece(e.target.checked)}
                className="mt-1 h-4 w-4"
              />
              <span className="text-xs leading-5 text-slate-300">
                Reconheço que a avaliação trata dados de trabalhadores de forma
                anônima e agregada, com base no{" "}
                <strong>cumprimento de obrigação legal</strong> (<Sigla
                  nome="LGPD"
                />
                , art. 7º, II, e art. 11, II, “a”) — e não no consentimento do
                trabalhador,
                que a relação de hierarquia comprometeria. Declaro estar de
                acordo com a{" "}
                {/* Só a privacidade: esta caixa é sobre tratamento de dados, e
                    os Termos de Uso aparecem logo abaixo, no bloco de
                    documentos, com versão e impressão digital. Citá-los aqui
                    duplicava o aceite e mandava para a página estática do site,
                    que não é o documento que o cadastro registra. */}
                <a
                  className="underline"
                  href="#/privacidade"
                  target="_blank"
                  rel="noreferrer"
                >
                  Política de Privacidade
                </a>
                .
              </span>
            </label>

            {/* Os documentos que a pessoa está de fato aceitando, cada um com
                versão e impressão digital, e cada um legível aqui mesmo.

                Até 25/08/2026 esta tela mostrava só o contrato e, ao lado do
                aceite, um link para froid.com.br/termos.html — a página
                ESTÁTICA do site. Depois que os termos se separaram, a pessoa
                passava a aceitar `terms_nr1` no envio e a ler outro documento
                na tela. Numa tela que produz efeito jurídico, mostrar documento
                diferente do que se aceita é o defeito que anula o aceite. */}
            {paraAceitar.length > 0 && (
              <div className="mt-4 rounded-lg border border-slate-700 bg-slate-950 p-4">
                <p className="text-xs font-black uppercase tracking-wide text-slate-400">
                  Documentos desta contratação
                </p>
                {paraAceitar.map(([chave, doc]) => (
                  <div key={chave} className="mt-3 border-t border-slate-800 pt-3 first:mt-2 first:border-0 first:pt-0">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs font-black text-slate-200">{doc.title}</p>
                      <button
                        type="button"
                        onClick={() =>
                          setDocumentoAberto((atual) => (atual === chave ? "" : chave))
                        }
                        className="text-xs font-black text-cyan-300 underline"
                      >
                        {documentoAberto === chave ? "Fechar" : "Ler"}
                      </button>
                    </div>
                    <p className="mt-1 text-[11px] text-slate-500">
                      {doc.sections.length} cláusulas · versão {doc.version} ·
                      impressão digital {doc.sha256.slice(0, 12)}
                    </p>
                    {documentoAberto === chave && (
                      <div className="mt-3 max-h-80 overflow-y-auto rounded border border-slate-800 bg-slate-900 p-3">
                        {doc.sections.map((secao) => (
                          <div key={secao.heading} className="mb-3 last:mb-0">
                            <p className="text-[11px] font-black uppercase tracking-wide text-slate-400">
                              {secao.heading}
                            </p>
                            <p className="mt-1 text-xs leading-5 text-slate-300">{secao.body}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                <label className="mt-4 flex items-start gap-3 border-t border-slate-800 pt-3">
                  <input
                    type="checkbox"
                    checked={contratoAceito}
                    onChange={(e) => setContratoAceito(e.target.checked)}
                    className="mt-1 h-4 w-4"
                  />
                  <span className="text-xs leading-5 text-slate-300">
                    Li e aceito os documentos acima, em nome da pessoa jurídica
                    identificada, declarando possuir poderes para contratar.
                  </span>
                </label>
              </div>
            )}

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button
                type="button"
                disabled={salvando}
                onClick={salvarEmpresa}
                className="rounded-lg bg-amber-500 px-5 py-3 text-sm font-black text-amber-950 hover:bg-amber-400 disabled:opacity-60"
              >
                {salvando
                  ? "Salvando..."
                  : jaCadastrada
                    ? "Registrar aceite e continuar"
                    : "Continuar"}
              </button>
              {jaCadastrada && organizationId && (
                <button
                  type="button"
                  onClick={() => setPasso(2)}
                  className="rounded-lg border border-slate-600 px-4 py-3 text-sm font-black text-slate-200 hover:bg-slate-800"
                >
                  Ir direto aos estabelecimentos →
                </button>
              )}
            </div>
            {jaCadastrada && (
              <p className="mt-3 max-w-2xl text-xs leading-5 text-slate-400">
                Esta empresa já está cadastrada, e os campos acima vieram do que
                está gravado. Use <strong>“Ir direto aos estabelecimentos”</strong>{" "}
                para acrescentar uma filial ou corrigir um efetivo sem tocar no
                cadastro. O botão da esquerda salva de novo — e é ele que{" "}
                <strong>registra o aceite dos documentos</strong>, com a data e a
                impressão digital de hoje.
              </p>
            )}
          </section>
        )}

        {passo === 2 && (
          <section className="mt-6">
            <h1 className="text-2xl font-black">Estabelecimentos</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              Estabelecimento é o endereço — a unidade que a{" "}
              <Sigla nome="NR-1" /> usa como recorte de resultado, e sobre a
              qual incide a base do contrato.{" "}
              <strong>Departamento no mesmo endereço não é estabelecimento</strong>;
              ele entra como setor no passo seguinte.
            </p>

            <div className="mt-5 grid gap-3 md:grid-cols-[1fr_140px_160px_auto]">
              <Campo rotulo="Nome" valor={novoSite.name} onChange={(v) => setNovoSite({ ...novoSite, name: v })} placeholder="Matriz, Filial Campinas..." />
              <Campo rotulo="Efetivo" valor={novoSite.headcount} onChange={(v) => setNovoSite({ ...novoSite, headcount: v })} tipo="number" />
              <Campo rotulo="Código interno" valor={novoSite.code} onChange={(v) => setNovoSite({ ...novoSite, code: v })} />
              <button
                type="button"
                disabled={salvando}
                onClick={() => criarUnidade("site", novoSite.name, novoSite.headcount, undefined, novoSite.code)}
                className="mt-5 h-10 rounded-lg bg-amber-500 px-4 text-sm font-black text-amber-950 hover:bg-amber-400 disabled:opacity-60"
              >
                Adicionar
              </button>
            </div>

            <ul className="mt-5 space-y-2">
              {estabelecimentos.map((site) => (
                <li key={site.unit_id} className="rounded-lg border border-slate-700 bg-slate-950 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-black">{site.name}</span>
                    <span className="text-xs text-slate-400">
                      {site.headcount} trabalhadores · {site.child_count} setor(es)
                    </span>
                    <button
                      type="button"
                      onClick={() => arquivar(site.unit_id)}
                      className="rounded-md border border-slate-600 px-2 py-1 text-[11px] font-bold text-slate-300"
                    >
                      Arquivar
                    </button>
                  </div>
                  {avisoDeRecorte(site.headcount) && (
                    <p className="mt-2 text-xs leading-5 text-amber-200">
                      {avisoDeRecorte(site.headcount)}
                      {site.headcount < PISO_CAMPANHA && (
                        <>
                          {" "}Com menos de {PISO_CAMPANHA} trabalhadores nenhuma
                          campanha desta unidade produz resultado liberável — o
                          piso de anonimato é absoluto. O caminho é a{" "}
                          <strong>
                            <Sigla nome="AEP" />
                          </strong>
                          , obrigatória para toda organização com empregados e
                          que não depende de piso.
                        </>
                      )}{" "}
                      <Link className="font-black underline" to="/nr1/aep">
                        Abrir a AEP desta unidade
                      </Link>
                      .
                    </p>
                  )}
                </li>
              ))}
              {!estabelecimentos.length && (
                <li className="text-sm text-slate-400">Nenhum estabelecimento cadastrado.</li>
              )}
            </ul>

            <div className="mt-6 flex gap-3">
              <button type="button" onClick={() => setPasso(1)} className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-black">
                Voltar
              </button>
              <button
                type="button"
                disabled={!estabelecimentos.length}
                onClick={() => setPasso(3)}
                className="rounded-lg bg-amber-500 px-5 py-2 text-sm font-black text-amber-950 disabled:opacity-50"
              >
                Continuar
              </button>
            </div>
          </section>
        )}

        {passo === 3 && (
          <section className="mt-6">
            <h1 className="text-2xl font-black">Setores</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              O setor define o recorte que pode aparecer no relatório. Abaixo de{" "}
              <strong>{PISO_RECORTE} pessoas</strong> o setor não ganha recorte
              próprio — não por falha, mas porque é assim que o anonimato de quem
              respondeu se sustenta. As pessoas continuam respondendo e contando
              para o resultado da empresa; o que não sai é o retrato daquele
              setor isolado.
            </p>

            <div className="mt-5 grid gap-3 md:grid-cols-[180px_1fr_120px_auto]">
              <label className="block">
                <span className="text-xs font-black text-slate-300">Estabelecimento<span className="ml-1 text-red-300">*</span></span>
                <select
                  value={novoSetor.parent}
                  onChange={(e) => setNovoSetor({ ...novoSetor, parent: e.target.value })}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                >
                  <option value="">Selecione</option>
                  {estabelecimentos.map((s) => (
                    <option key={s.unit_id} value={s.unit_id}>{s.name}</option>
                  ))}
                </select>
              </label>
              <Campo rotulo="Nome do setor" valor={novoSetor.name} onChange={(v) => setNovoSetor({ ...novoSetor, name: v })} placeholder="Operações, Comercial..." />
              <Campo rotulo="Efetivo" valor={novoSetor.headcount} onChange={(v) => setNovoSetor({ ...novoSetor, headcount: v })} tipo="number" />
              <button
                type="button"
                disabled={salvando || !novoSetor.parent}
                onClick={() => criarUnidade("sector", novoSetor.name, novoSetor.headcount, novoSetor.parent)}
                className="mt-5 h-10 rounded-lg bg-amber-500 px-4 text-sm font-black text-amber-950 disabled:opacity-50"
              >
                Adicionar
              </button>
            </div>

            <div className="mt-5 space-y-4">
              {estabelecimentos.map((site) => {
                const meus = setores.filter((s) => s.parent_unit_id === site.unit_id);
                const somaSetores = meus.reduce((t, s) => t + s.headcount, 0);
                // Os setores que não alcançam o piso de anonimato, e quanto
                // somariam juntos. É a informação que decide o que fazer: se a
                // soma passa do piso, agrupar resolve; se não passa, agrupar
                // entre eles não resolve e insistir só adia a descoberta.
                const pequenos = meus.filter(
                  (s) => s.headcount > 0 && s.headcount < PISO_RECORTE,
                );
                const somaPequenos = pequenos.reduce((t, s) => t + s.headcount, 0);
                const maiorDoSite = meus.reduce(
                  (maior, s) => (s.headcount > (maior?.headcount ?? 0) ? s : maior),
                  null as (typeof meus)[number] | null,
                );
                return (
                  <div key={site.unit_id} className="rounded-lg border border-slate-700 bg-slate-950 p-3">
                    <p className="text-sm font-black">{site.name}</p>
                    <ul className="mt-2 space-y-1">
                      {meus.map((setor) => (
                        <li key={setor.unit_id} className="flex items-center justify-between gap-2 text-sm">
                          <span className="text-slate-200">
                            {setor.name}
                            {setor.headcount > 0 && setor.headcount < PISO_RECORTE && (
                              <span className="ml-2 rounded bg-amber-950 px-1.5 py-0.5 text-[10px] font-black uppercase tracking-wide text-amber-300">
                                sem recorte próprio
                              </span>
                            )}
                          </span>
                          <span className="text-xs text-slate-400">{setor.headcount}</span>
                          <button
                            type="button"
                            onClick={() => arquivar(setor.unit_id)}
                            className="rounded-md border border-slate-600 px-2 py-0.5 text-[11px] font-bold text-slate-300"
                          >
                            Arquivar
                          </button>
                        </li>
                      ))}
                      {!meus.length && <li className="text-xs text-slate-500">Sem setores.</li>}
                    </ul>

                    {/* Dito no cadastro, e não no fim da coleta.
                        Um setor de 4 pessoas nunca vai publicar recorte, e
                        descobrir isso com o painel aberto na frente do cliente
                        é a pior hora possível. Aqui ainda dá para redesenhar a
                        estrutura, que é a única coisa que resolve. */}
                    {pequenos.length > 0 && (
                      <div className="mt-3 rounded border border-amber-900 bg-amber-950/40 p-3 text-xs leading-5 text-amber-100">
                        <p className="font-black text-amber-200">
                          {pequenos.length === 1
                            ? "1 setor abaixo do piso de anonimato"
                            : `${pequenos.length} setores abaixo do piso de anonimato`}
                        </p>
                        <p className="mt-1">
                          {pequenos
                            .map((s) => `${s.name} (${s.headcount})`)
                            .join(", ")}{" "}
                          — abaixo de {PISO_RECORTE} pessoas nenhum deles publica
                          retrato próprio, por mais que respondam.
                        </p>
                        {pequenos.length > 1 && somaPequenos >= PISO_RECORTE ? (
                          <p className="mt-2">
                            Somados, chegam a <strong>{somaPequenos}</strong> — o
                            bastante para um recorte. Se essas pessoas fizerem
                            trabalho semelhante, cadastre-as como{" "}
                            <strong>um único setor</strong> (arquive os pequenos e
                            crie o agrupado) e o relatório passa a falar delas.
                          </p>
                        ) : pequenos.length > 1 ? (
                          <p className="mt-2">
                            Mesmo somados chegam a apenas{" "}
                            <strong>{somaPequenos}</strong>, ainda abaixo de{" "}
                            {PISO_RECORTE}. Agrupá-los entre si não resolve
                            {maiorDoSite && maiorDoSite.headcount >= PISO_RECORTE
                              ? `; o caminho é incorporá-los a “${maiorDoSite.name}”, se o trabalho for compatível.`
                              : "; neste tamanho o recorte por setor não existe, e o retrato sai no nível do estabelecimento."}
                          </p>
                        ) : (
                          <p className="mt-2">
                            Para ganhar recorte próprio ele precisaria de{" "}
                            {PISO_RECORTE - pequenos[0].headcount} pessoa(s) a
                            mais. A alternativa é agrupá-lo a um setor vizinho de
                            trabalho semelhante
                            {maiorDoSite && maiorDoSite.unit_id !== pequenos[0].unit_id
                              ? ` — “${maiorDoSite.name}”, por exemplo.`
                              : "."}
                          </p>
                        )}
                        {/* A ressalva que impede o conselho de virar defeito.
                            A NR-1 avalia condição de trabalho, e a coorte só
                            significa alguma coisa se as pessoas dentro dela
                            estiverem expostas ao mesmo. Juntar a limpeza com o
                            call center para "chegar a dez" produz uma média que
                            não descreve nenhum dos dois — e o risco do grupo
                            menor desaparece dentro do maior, que é exatamente o
                            oposto do que o agrupamento deveria conseguir. */}
                        <p className="mt-2 text-amber-100/75">
                          Agrupe apenas quem faz trabalho semelhante, sob as
                          mesmas condições e a mesma chefia. Juntar setores
                          diferentes só para alcançar o piso produz uma média que
                          não descreve nenhum dos dois, e some com o risco do
                          grupo menor dentro do maior.
                        </p>
                      </div>
                    )}
                    {/* A soma dos setores não precisa bater com o efetivo do
                        estabelecimento — há quem não pertença a nenhum setor
                        mapeado. Mas divergência grande costuma ser digitação, e
                        é melhor descobrir aqui do que na campanha. */}
                    {site.headcount > 0 && somaSetores > site.headcount && (
                      <p className="mt-2 text-xs text-amber-200">
                        A soma dos setores ({somaSetores}) passou do efetivo do
                        estabelecimento ({site.headcount}). Confira os números.
                      </p>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="mt-6 flex gap-3">
              <button type="button" onClick={() => setPasso(2)} className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-black">
                Voltar
              </button>
              <button type="button" onClick={() => setPasso(4)} className="rounded-lg bg-amber-500 px-5 py-2 text-sm font-black text-amber-950">
                Continuar
              </button>
            </div>
          </section>
        )}

        {passo === 4 && (
          <section className="mt-6">
            <h1 className="text-2xl font-black">Estrutura registrada</h1>
            <div className="mt-4 rounded-lg border border-slate-700 bg-slate-950 p-4">
              <p className="text-sm font-black text-slate-200">
                {razaoSocial || "Empresa"} — {estabelecimentos.length} estabelecimento(s),{" "}
                {setores.length} setor(es)
              </p>
              <p className="mt-1 text-xs text-slate-400">
                Efetivo somado: {efetivoTotal} trabalhadores
              </p>
            </div>

            {caminho === "aep" && (
              <div className="mt-5 rounded-lg border border-cyan-800 bg-cyan-950/40 p-4">
                <p className="text-sm font-black text-cyan-200">
                  O caminho desta empresa é a <Sigla nome="AEP" />, e não a
                  campanha
                </p>
                <p className="mt-2 text-xs leading-5 text-cyan-100">
                  Com {efetivoTotal} trabalhadores nenhuma campanha produz
                  resultado liberável — e isso não depende de adesão. O piso de{" "}
                  {PISO_CAMPANHA} respostas protege o anonimato e é absoluto:
                  numa coorte menor que isso, saber a média já é quase saber quem
                  respondeu o quê. Um trabalhador que suspeita disso responde o
                  que é seguro, não o que é verdade, e a empresa paga por um
                  retrato que não corresponde à realidade.
                </p>
                <p className="mt-2 text-xs leading-5 text-cyan-100">
                  Isso não reduz a sua conformidade em nada. A{" "}
                  <strong>Avaliação Ergonômica Preliminar</strong> é obrigatória
                  para toda organização com empregados — inclusive as
                  microempresas e empresas de pequeno porte dispensadas do{" "}
                  <Sigla nome="PGR" /> — e não depende de piso de respondentes.
                  Para um grupo deste tamanho o Guia do <Sigla nome="MTE" />{" "}
                  indica justamente diálogo com os
                  trabalhadores e observação da atividade em vez de formulário, e
                  é isso que a AEP registra, com o método nomeado em cada
                  evidência.
                </p>
                <Link
                  to="/nr1/aep"
                  className="mt-4 inline-block rounded-lg bg-cyan-500 px-5 py-2.5 text-sm font-black text-cyan-950 hover:bg-cyan-400"
                >
                  Abrir a AEP desta empresa
                </Link>
              </div>
            )}

            {caminho === "censo" && (
              <div className="mt-5 rounded-lg border border-amber-800 bg-amber-950/40 p-4">
                <p className="text-sm font-black text-amber-200">
                  Com {efetivoTotal} trabalhadores, a campanha exige censo
                </p>
                <p className="mt-2 text-xs leading-5 text-amber-100">
                  São dois pisos. O de anonimato pede {PISO_CAMPANHA} respostas.
                  O de representatividade pede a amostra que fala pelo efetivo — e
                  abaixo de 98 pessoas essa amostra alcança o quadro inteiro:{" "}
                  {exigidoNaCampanha(efetivoTotal)} de {efetivoTotal}. Como
                  responder é voluntário, uma única recusa suspende o inventário.
                </p>
                <p className="mt-2 text-xs leading-5 text-amber-100">
                  A campanha continua disponível, e vale se a adesão for
                  garantida. Mas a{" "}
                  <strong>
                    <Sigla nome="AEP" />
                  </strong>{" "}
                  não depende de piso, é
                  obrigatória de todo modo e pode correr em paralelo — comece por
                  ela para não ficar sem documento se a coleta não fechar.
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                  <Link
                    to="/nr1/aep"
                    className="rounded-lg bg-cyan-500 px-5 py-2.5 text-sm font-black text-cyan-950 hover:bg-cyan-400"
                  >
                    Abrir a AEP desta empresa
                  </Link>
                  <Link
                    className="rounded-lg border border-amber-700 px-4 py-2.5 text-sm font-black text-amber-200 hover:bg-amber-900/40"
                    to="/nr1/campanha"
                  >
                    Criar a campanha mesmo assim
                  </Link>
                </div>
              </div>
            )}

            {/* Esta caixa dizia "o que FALTA antes da primeira campanha" e
                terminava num endereço de e-mail. Duas coisas erradas ao mesmo
                tempo: nada faltava — a estrutura estava completa e o cadastro,
                concluído —, e os quatro itens listados não são pendências, são
                os campos da tela seguinte. Quem lia entendia que havia sido
                barrado, e a única saída oferecida era escrever para o
                fornecedor e esperar. Um cadastro que termina pedindo para o
                cliente mandar um e-mail não terminou. */}
            {caminho === "campanha" && (
              <div className="mt-5 rounded-lg border border-emerald-800 bg-emerald-950/40 p-4">
                <p className="text-sm font-black text-emerald-200">
                  Estrutura completa. A próxima tela cria a campanha.
                </p>
                <p className="mt-2 text-xs leading-5 text-emerald-100">
                  Com {efetivoTotal} trabalhadores, a campanha da organização
                  inteira publica com{" "}
                  <strong>
                    {exigidoNaCampanha(efetivoTotal)} respostas substantivas
                  </strong>
                  . É lá que se informa, tudo na mesma página:
                </p>
                <ul className="mt-2 space-y-1 text-xs leading-5 text-emerald-100">
                  <li>
                    • <strong>Canal de apoio ao trabalhador</strong> — nome e
                    como acessar. É o único campo que o banco de dados exige
                    para deixar a coleta abrir: perguntar a alguém como ele está
                    sem ter para onde encaminhá-lo é pior do que não perguntar.
                  </li>
                  <li>
                    • <strong>Janela de coleta</strong> — quando abre e quando
                    fecha — e o <strong>aviso de finalidade</strong> que os
                    trabalhadores leem antes da primeira pergunta.
                  </li>
                  <li>
                    • <strong>Efetivo do período de referência</strong> — vem
                    preenchido com os {efetivoTotal} desta estrutura e pode ser
                    corrigido.
                  </li>
                </ul>
                <p className="mt-3 text-xs leading-5 text-emerald-100/80">
                  A gradação sai pelos critérios padrão FROID, ancorados na{" "}
                  <Sigla nome="NR-1" curta /> e no Guia do{" "}
                  <Sigla nome="MTE" curta />, e o inventário já é válido assim.
                  Alinhá-los à matriz que a empresa usa no resto do{" "}
                  <Sigla nome="PGR" /> é opcional e se faz depois, sem refazer
                  nada.
                </p>
                {/* "Criar a primeira campanha" era mentira a partir da
                    segunda: esta tela nao consulta campanhas — ela e o cadastro
                    da estrutura — e a empresa volta aqui para acrescentar filial
                    ou corrigir efetivo muito depois de ter campanha rodando.
                    Buscar o estado so para escolher o rotulo acrescentaria uma
                    requisicao e um modo de falha a uma tela que nao precisa de
                    nenhum dos dois. O rotulo neutro e verdadeiro nos dois casos. */}
                <Link
                  to="/nr1/campanha"
                  className="mt-4 inline-block rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-black text-emerald-950 hover:bg-emerald-400"
                >
                  Ir para Campanha e convites
                </Link>
              </div>
            )}

            {/* A AEP nao e alternativa da campanha: e o documento que a recebe.
                O MTE e explicito que questionario nao comprova gestao de risco
                isoladamente — ele caracteriza a exposicao e entra como insumo. */}
            {caminho !== "aep" && (
              <p className="mt-3 text-xs leading-5 text-slate-400">
                Em qualquer porte a{" "}
                <Link className="underline" to="/nr1/aep">
                  <Sigla nome="AEP" />
                </Link>{" "}
                continua obrigatória: o questionário caracteriza a exposição, não
                comprova sozinho a gestão do risco.
              </p>
            )}

            <div className="mt-6 flex flex-wrap gap-3">
              <button type="button" onClick={() => setPasso(3)} className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-black">
                Ajustar estrutura
              </button>
              <Link
                to={caminho === "aep" ? "/nr1/aep" : "/nr1"}
                className="rounded-lg bg-amber-500 px-5 py-2 text-sm font-black text-amber-950"
              >
                {caminho === "aep" ? "Ir para a AEP" : "Ir para o painel NR-1"}
              </Link>
            </div>

            <GlossarioDeSiglas
              termos={["NR-1", "PGR", "AEP", "MTE", "LGPD", "CNPJ"]}
            />
          </section>
        )}
      </main>
      <Nr1ExplicaPainel
        organizationId={organizationId}
        verbeteSugerido="setor-pequeno"
        contexto="Estrutura da empresa"
      />
      </div>
    </div>
  );
};

export default Nr1CompanyOnboarding;
