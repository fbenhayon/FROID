import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { VERBETES } from "../../lib/nr1-explica-conteudo";

const PAINEL = readFileSync(join(__dirname, "Nr1ExplicaPainel.tsx"), "utf-8");
const PAGINAS = join(__dirname, "..", "..", "pages");

/** As oito telas do modulo. O Fabio pediu a coluna em todas, e "todas" e uma
 *  afirmacao que so um teste sustenta -- integrar sete e esquecer uma e
 *  exatamente o tipo de falha que passa despercebida em revisao. */
const LAYOUTS = [
  "Nr1Dashboard.tsx",
  "Nr1Inventario.tsx",
  "Nr1ActionPlan.tsx",
  "Nr1Campaign.tsx",
  "Nr1Effectiveness.tsx",
  "Nr1Aep.tsx",
  "Nr1Acceptance.tsx",
  "Nr1CompanyOnboarding.tsx",
];

const fonteDaTela = (arquivo: string) =>
  readFileSync(join(PAGINAS, arquivo), "utf-8");

describe("os oito layouts tem a segunda coluna", () => {
  it.each(LAYOUTS)("%s hospeda o painel", (arquivo) => {
    const fonte = fonteDaTela(arquivo);
    expect(fonte).toContain("Nr1ExplicaPainel");
    expect(fonte).toContain("components/nr1/Nr1ExplicaPainel");
  });

  it.each(LAYOUTS)("%s passa a organizacao ao painel", (arquivo) => {
    // Sem organizationId a consulta aberta nao sai, e o painel fica decorativo.
    expect(fonteDaTela(arquivo)).toContain("organizationId={organizationId}");
  });

  it.each(LAYOUTS)("%s monta a coluna num grid", (arquivo) => {
    expect(fonteDaTela(arquivo)).toContain("xl:grid-cols-[minmax(0,1fr)_400px]");
  });

  it("todo verbete sugerido por uma tela existe", () => {
    // Um id errado degradaria em silencio: o seletor abriria vazio em vez de
    // abrir na pergunta que aquela tela torna provavel.
    for (const arquivo of LAYOUTS) {
      const sugeridos = [...fonteDaTela(arquivo).matchAll(/verbeteSugerido="([^"]+)"/g)];
      for (const [, id] of sugeridos) {
        expect(VERBETES.some((v) => v.id === id)).toBe(true);
      }
    }
  });
});

describe("o painel responde o que foi pedido", () => {
  it("cita os documentos da contratacao pelo nome", () => {
    expect(PAINEL).toContain("Termos de Uso — FROID NR-1");
    expect(PAINEL).toContain(
      "Contrato de Prestação de Serviço — FROID NR-1, Riscos Psicossociais",
    );
    expect(PAINEL).toContain("Política de Privacidade");
  });

  it("os documentos apontam para rotas, e nao para texto colado", () => {
    for (const rota of ["/termos-nr1", "/contrato-nr1", "/privacidade"]) {
      expect(PAINEL).toContain(`para: "${rota}"`);
    }
  });

  it("cobre contrato, operacao e privacidade pelos temas curados", () => {
    for (const tema of ["contrato", "operacao", "privacidade", "lei"]) {
      expect(VERBETES.some((v) => v.tema === tema)).toBe(true);
    }
  });

  it("a camada revisada nao depende de rede", () => {
    /**
     * `responderComVerbete` monta a resposta a partir do proprio verbete. Se
     * algum dia ela passar a buscar no servidor, o painel deixa de funcionar
     * na frente de um auditor com a rede ruim -- que e o cenario para o qual
     * a camada revisada existe.
     */
    const corpo = PAINEL.slice(
      PAINEL.indexOf("const responderComVerbete"),
      PAINEL.indexOf("const perguntar"),
    );
    expect(corpo).not.toContain("fetch(");
    expect(corpo).toContain('motor: "revisada"');
  });

  it("so a resposta gerada leva a ressalva de conferir a fonte", () => {
    // A revisada foi conferida uma vez; repetir a ressalva nela treinaria o
    // leitor a ignorar o aviso onde ele importa.
    expect(PAINEL).toContain('item.resposta.motor !== "revisada"');
  });

  it("a pergunta que falha entra no historico", () => {
    const captura = PAINEL.slice(PAINEL.indexOf("} catch (e) {"));
    expect(captura).toContain("registrar({");
    expect(captura).toContain("erro: motivo");
  });

  it("nao parafraseia clausula: aponta para o documento", () => {
    expect(PAINEL).toContain("verbete?.destino");
    expect(PAINEL).toContain("nunca a parafraseia");
  });
});
