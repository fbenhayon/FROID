import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { caminhoDoConviteDeSessao } from "./convite-de-sessao";

/**
 * O convite de sessão, e o defeito que ele evita.
 *
 * Convidar um paciente é cair no formulário de `/patients/new` com os dados
 * dele já preenchidos. O preenchimento viaja por nome de parâmetro na URL, e
 * nome casado por nome erra em silêncio (seção 2.9): um `telefone` onde o
 * leitor espera `phone` não dá erro, não pinta nada de vermelho — abre o
 * formulário em branco, e quem convidou só descobre relendo o campo.
 *
 * Por isso os dois lados são confrontados aqui pelo texto-fonte, e não pelo
 * olhar: o que o produtor emite tem de ser exatamente o que `NewPatient` lê.
 */

const FONTE = (...caminho: string[]) =>
  readFileSync(join(__dirname, "..", ...caminho), "utf-8");

const NEW_PATIENT = FONTE("pages", "NewPatient.tsx");
const PRODUTOR = readFileSync(join(__dirname, "convite-de-sessao.ts"), "utf-8");

function nomesEmitidos(fonte: string): string[] {
  return [...fonte.matchAll(/params\.set\("([^"]+)"/g)].map((m) => m[1]);
}

function nomesLidos(fonte: string): string[] {
  return [...fonte.matchAll(/searchParams\.get\("([^"]+)"\)/g)].map((m) => m[1]);
}

describe("caminho do convite de sessão", () => {
  it("sem paciente, abre o formulário em branco e sem query vazia", () => {
    expect(caminhoDoConviteDeSessao()).toBe("/patients/new");
    expect(caminhoDoConviteDeSessao(null)).toBe("/patients/new");
    expect(caminhoDoConviteDeSessao({})).toBe("/patients/new");
  });

  it("leva nome, e-mail e telefone quando existem", () => {
    const caminho = caminhoDoConviteDeSessao({
      name: "Bruno Nalon",
      email: "bruno@exemplo.com",
      phone: "16466769860",
    });
    const query = new URLSearchParams(caminho.split("?")[1]);
    expect(query.get("name")).toBe("Bruno Nalon");
    expect(query.get("email")).toBe("bruno@exemplo.com");
    expect(query.get("phone")).toBe("16466769860");
  });

  it("campo ausente não vira parâmetro vazio", () => {
    // Parâmetro vazio não é o mesmo que parâmetro ausente: `name=` chegaria ao
    // formulário como um nome em branco escrito de propósito.
    const caminho = caminhoDoConviteDeSessao({ name: "Bruno", email: "" });
    expect(caminho).toContain("name=Bruno");
    expect(caminho).not.toContain("email=");
  });

  it("o modo de captura só viaja quando é pedido", () => {
    expect(caminhoDoConviteDeSessao({ name: "A" })).not.toContain("capture=");
    expect(caminhoDoConviteDeSessao({ name: "A" }, "patient_mobile")).toContain(
      "capture=patient_mobile",
    );
  });

  it("todo nome que o produtor emite é um nome que NewPatient lê", () => {
    const emitidos = nomesEmitidos(PRODUTOR);
    const lidos = nomesLidos(NEW_PATIENT);
    expect(emitidos.length).toBeGreaterThan(0);
    expect(lidos.length).toBeGreaterThan(0);
    for (const nome of emitidos) {
      expect(lidos, `NewPatient não lê o parâmetro "${nome}"`).toContain(nome);
    }
  });

  it("nenhuma tela monta a rota do convite por conta própria", () => {
    // A regra varre o repositório, não o arquivo que eu estava olhando
    // (seção 2.8). Só duas citações de `/patients/new` são legítimas: a
    // declaração da rota em App.tsx e o produtor aqui do lado.
    for (const arquivo of [
      "Dashboard.tsx",
      "ProfessionalDashboardSummary.tsx",
      "PatientDetail.tsx",
    ]) {
      expect(
        FONTE("pages", arquivo),
        `${arquivo} deve chamar caminhoDoConviteDeSessao`,
      ).not.toContain("/patients/new");
    }
    expect(FONTE("App.tsx")).toContain('path="/patients/new"');
  });

  it("as três telas convidam pelo mesmo produtor", () => {
    for (const arquivo of [
      "Dashboard.tsx",
      "ProfessionalDashboardSummary.tsx",
      "PatientDetail.tsx",
    ]) {
      expect(FONTE("pages", arquivo)).toContain("caminhoDoConviteDeSessao");
    }
  });

  it("a ficha do paciente convida, não abre sessão", () => {
    // O botão antigo dizia "Abrir sessão" e levava à sala da ÚLTIMA sessão
    // deste paciente. Pelo painel não se abre a sessão de um paciente: o
    // paciente recebe um link e a sala nasce quando ele entra.
    const ficha = FONTE("pages", "PatientDetail.tsx");
    const botoes = [...ficha.matchAll(/>\s*\{?tr\("([^"]+)"\)\}?\s*</g)].map(
      (m) => m[1],
    );
    expect(botoes).toContain("Convidar para sessão");
    expect(ficha).not.toMatch(/>\s*Abrir sessão\s*</);
  });

  it("o dashboard resumido oferece cadastro e convite", () => {
    const resumido = FONTE("pages", "ProfessionalDashboardSummary.tsx");
    expect(resumido).toContain("Cadastrar paciente");
    expect(resumido).toContain("Convidar");
    // A coluna nova e o colSpan da lista vazia saem da mesma lista, para não
    // divergirem na próxima coluna que alguém acrescentar (seção 2.7).
    expect(resumido).toContain("colSpan={COLUNAS_DA_TABELA.length}");
  });
});

describe("acesso do paciente aos resultados", () => {
  it("a caixa do convite chega marcada", () => {
    // Determinação do dono, 20/09/2026. Marcar não publica relatório nenhum:
    // cada sessão ainda passa pela composição e pelo botão de liberar, na tela
    // do Relatório da Sessão. O que a caixa decide é se o paciente chega a ver
    // o que já foi liberado.
    expect(NEW_PATIENT).toContain(
      "const [patientResultsEnabled, setPatientResultsEnabled] = useState(true);",
    );
    expect(NEW_PATIENT).toContain("patient_results_enabled: patientResultsEnabled");
  });
});
