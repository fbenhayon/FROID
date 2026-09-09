import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Desfazer o rascunho criado por engano.
 *
 * Em 09/09/2026 um cliente criou quatro campanhas onde deviam existir duas, e
 * descobriu que não havia como remover as três sobrando: campanha não tem
 * exclusão, e o FROID Explica respondia "não se exclui" — doutrina correta,
 * ancorada na guarda de vinte anos do inventário, e que simplesmente não
 * alcança o rascunho vazio que nenhum inventário referencia.
 *
 * Cancelar não é apagar: a linha continua no banco. O que estes testes guardam
 * é o contorno do que pode ser cancelado (rascunho, e só com zero convites
 * confirmados pelo servidor), o fato de a ação avisar que não tem volta, e a
 * coerência entre a tela e o verbete que a explica — um respondendo "não há
 * saída" enquanto o outro oferece o botão manda o operador desistir de uma
 * saída que existe.
 */

const PAGINA = readFileSync(join(__dirname, "Nr1Campaign.tsx"), "utf-8");
const CORRIDA = PAGINA.replace(/\s+/g, " ");

/** O corpo de uma função `const nome = ... => { ... }`, pelo balanço de chaves.
 *
 *  Recorte por número de linha e por janela de caracteres já quebrou duas vezes
 *  nesta casa por crescimento de comentário. */
function corpoDe(nome: string): string {
  const inicio = PAGINA.indexOf(`const ${nome} =`);
  expect(inicio, `função ${nome} não existe`).toBeGreaterThan(-1);
  const abre = PAGINA.indexOf("{", inicio);
  let profundidade = 0;
  for (let i = abre; i < PAGINA.length; i += 1) {
    if (PAGINA[i] === "{") profundidade += 1;
    if (PAGINA[i] === "}") {
      profundidade -= 1;
      if (profundidade === 0) return PAGINA.slice(inicio, i + 1);
    }
  }
  throw new Error(`corpo de ${nome} não fecha`);
}

describe("desfazer o rascunho criado por engano", () => {
  it("existe a ação, e ela chama a rota de cancelamento", () => {
    expect(corpoDe("cancelar")).toContain("/cancel`");
  });

  it("o botão só aparece no rascunho que o servidor confirmou vazio", () => {
    // Com a contagem ausente o botão não aparece: oferecer uma ação que o
    // servidor vai recusar é pior do que não oferecer.
    expect(CORRIDA).toContain(
      '{campanha.status === "draft" && campanha.invitations === 0 &&',
    );
  });

  it("pede um segundo clique e diz que não tem volta", () => {
    expect(PAGINA).toContain("const [confirmandoCancelamento, setConfirmandoCancelamento]");
    expect(CORRIDA).toMatch(/Cancelar n[ãa]o apaga\.<\/strong>/);
    expect(CORRIDA).toMatch(/N[ãa]o h[áa] como desfazer/);
  });

  it("a cancelada some da lista de trabalho e não do sistema", () => {
    expect(PAGINA).toContain("const campanhasVivas = useMemo(");
    expect(CORRIDA).toContain("{campanhasVivas.map((campanha) => (");
    expect(CORRIDA).toContain("{canceladas.length} campanha(s) cancelada(s)");
  });

  it("a campanha cancelada não conta como homônima nem como em coleta", () => {
    // Ela não disputa mais nada: manter o alarme de homônimas aceso por causa
    // de uma campanha cancelada treinaria o operador a ignorá-lo.
    const fonte = PAGINA.slice(
      PAGINA.indexOf("const tituloJaExiste = useMemo("),
      PAGINA.indexOf("const linhasInterpretadas = useMemo("),
    );
    expect(fonte).toContain("campanhasVivas");
    expect(fonte).not.toContain("campanhas.find(");
    expect(fonte).not.toContain("of campanhas)");
  });
});

describe("o FROID Explica conta a mesma história que a tela", () => {
  const VERBETES = readFileSync(
    join(__dirname, "..", "lib", "nr1-explica-conteudo.ts"),
    "utf-8",
  );
  const EXCLUIR = VERBETES.slice(
    VERBETES.indexOf('id: "excluir"'),
    VERBETES.indexOf('id: "gradacao"'),
  );

  it("o verbete deixou de dizer que NUNCA há saída", () => {
    // Enquanto a tela oferece "Cancelar rascunho", um verbete que responde
    // "não se exclui" e para por aí manda o operador desistir de uma saída
    // que existe — e é a esse verbete que ele chega procurando por "apagar".
    expect(EXCLUIR).toContain("Cancelar rascunho");
    expect(EXCLUIR).toMatch(/sem nenhum convite emitido/);
  });

  it("continua dizendo que cancelar não é apagar", () => {
    expect(EXCLUIR).toMatch(/cancelar n[ãa]o é apagar/i);
    expect(EXCLUIR).toContain("vinte anos");
  });

  it("quem procura pelo engano encontra o verbete", () => {
    for (const chave of ["cancelar", "rascunho", "duplicada", "criei sem querer"]) {
      expect(EXCLUIR, `chave ${chave}`).toContain(`"${chave}"`);
    }
  });
});
