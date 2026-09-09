import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import {
  nomeDoClienteAtivo,
  organizacaoAtiva,
} from "../../lib/contexto-organizacao";

const PAGINAS = join(__dirname, "..", "..", "pages");
const ler = (nome: string) => readFileSync(join(PAGINAS, nome), "utf-8");

/** As telas que a EMPRESA opera. Todas precisam dizer de quem é o dado.
 *
 *  Nr1QuestionnairePage fica fora: é a tela do TRABALHADOR, aberta por token,
 *  sem sessão de empregador — ela não tem o nome e não deve inventá-lo.
 *  Nr1Acceptance também: é o comprovante impresso, e o nome da empresa já é
 *  parte do corpo do documento, não do cabeçalho de navegação.
 */
const TELAS_DO_EMPREGADOR = [
  "Nr1Dashboard.tsx",
  "Nr1Campaign.tsx",
  "Nr1Inventario.tsx",
  "Nr1ActionPlan.tsx",
  "Nr1Aep.tsx",
  "Nr1Effectiveness.tsx",
  "Nr1Explica.tsx",
];

const org = (id: string, nome?: string) => ({
  organization_id: id,
  organization_name: nome,
  organization_type: "enterprise",
});

describe("quem é o cliente da sessão", () => {
  it("é a organização ativa, e não a primeira da lista", () => {
    const user = {
      organizations: [org("a", "Alfa"), org("b", "Beta")],
      active_organization_id: "b",
    };
    expect(organizacaoAtiva(user)?.organization_id).toBe("b");
    expect(nomeDoClienteAtivo(user)).toBe("Beta");
  });

  it("cai na primeira quando a ativa não corresponde a vínculo nenhum", () => {
    // Não é chute: é a mesma regra que `_attach_tenant_contexts` aplica no
    // servidor antes de responder. Divergir dela faria a tela nomear um
    // cliente e o servidor operar noutro.
    const user = {
      organizations: [org("a", "Alfa"), org("b", "Beta")],
      active_organization_id: "sumiu",
    };
    expect(nomeDoClienteAtivo(user)).toBe("Alfa");
  });

  it("NUNCA escreve o organization_id no lugar do nome", () => {
    // `nomeDaOrganizacao` cai no id quando o nome falta. No cabeçalho isso
    // poria um UUID onde se lê o nome do cliente — pior que o vazio, porque
    // quem lê conclui que a tela está com defeito sem saber qual.
    const user = {
      organizations: [org("3ee303c5-581c-4f59-9ee9-ed1bd3e82b04")],
      active_organization_id: "3ee303c5-581c-4f59-9ee9-ed1bd3e82b04",
    };
    expect(nomeDoClienteAtivo(user)).toBe("");
  });

  it("conta sem organização nenhuma não quebra", () => {
    expect(nomeDoClienteAtivo(null)).toBe("");
    expect(nomeDoClienteAtivo({})).toBe("");
    expect(nomeDoClienteAtivo({ organizations: [] })).toBe("");
    expect(organizacaoAtiva(undefined)).toBeNull();
  });
});

describe("o nome do cliente aparece em TODA tela do empregador", () => {
  it.each(TELAS_DO_EMPREGADOR)("%s", (tela) => {
    const fonte = ler(tela);
    expect(fonte).toContain("<EtapaNr1");
    expect(fonte).toContain("user={user}");
  });

  it("nenhuma tela voltou a escrever a etapa à mão", () => {
    // O ponto do componente é não haver oitava cópia da linha. Uma tela nova
    // que a escrevesse direto herdaria o defeito original — a etapa sem o
    // cliente — e ninguém perceberia, porque a tela ficaria idêntica às
    // outras para quem olha.
    const orfas = readdirSync(PAGINAS)
      .filter((nome) => nome.startsWith("Nr1") && nome.endsWith(".tsx"))
      .filter((nome) => nome !== "Nr1QuestionnairePage.tsx")
      .filter((nome) =>
        ler(nome).includes(
          'className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300"',
        ),
      );
    expect(orfas).toEqual([]);
  });

  it("o cadastro da empresa também se identifica, ao lado dos passos", () => {
    // Ali o nome vem do formulário: no passo 1 a organização ainda não existe.
    const fonte = ler("Nr1CompanyOnboarding.tsx");
    const inicio = fonte.indexOf("<Passo numero={1}");
    expect(inicio).toBeGreaterThan(-1);
    const antes = fonte.slice(Math.max(0, inicio - 600), inicio);
    expect(antes).toContain("nomeFantasia.trim() || razaoSocial.trim()");
  });
});
