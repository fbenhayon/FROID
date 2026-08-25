import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * Travas da escolha de produto.
 *
 * A mais importante é a primeira, e ela não é estética.
 *
 * Os `element` das rotas são calculados no render do App, que está ACIMA do
 * HashRouter — então uma navegação interna NÃO faz o App renderizar de novo.
 * Se a decisão de rota ler o localStorage durante esse cálculo, o elemento
 * congela com o valor do primeiro render. Foi o que aconteceu: /access/register
 * ficou preso devolvendo para /access/produto, e o cadastro clínico virou
 * inalcançável. Passava no typecheck e só apareceu clicando.
 *
 * Por isso a escolha precisa ser estado do React. Quem "simplificar" isso de
 * volta para uma leitura direta derruba estes testes.
 */

const APP = readFileSync(join(__dirname, "..", "App.tsx"), "utf-8");
const PAGINA = readFileSync(join(__dirname, "ProductChoice.tsx"), "utf-8");
const LIB = readFileSync(
  join(__dirname, "..", "lib", "product-choice.ts"),
  "utf-8",
);

/** Junta o texto quebrado em varias linhas de comentario.
 *
 * A primeira versao deste arquivo procurava "nao concede acesso" e reprovava
 * codigo correto: as duas palavras caiam em linhas diferentes, separadas por
 * "// ". Procurar frase em fonte exige normalizar antes. */
const LIB_CORRIDO = LIB.replace(/\n\s*\/\/ ?/g, " ").replace(/\s+/g, " ");

describe("a escolha decide rota, então precisa ser estado", () => {
  it("o App guarda a escolha em useState", () => {
    expect(APP).toMatch(/useState<FroidProduct \| null>\(/);
  });

  it("as funções de rota recebem a escolha por parâmetro", () => {
    // Elas mudaram de casa em 25/08/2026: viviam no App e havia mais DUAS
    // cópias abreviadas da mesma decisão, em LoginPage e AccountAccessPages.
    // Quando a regra ganhou a exceção do administrador, ela entrou só na cópia
    // do App — e o admin continuou caindo na escolha de produto a cada login,
    // fazendo a correção parecer que não tinha funcionado.
    //
    // O que este teste guarda continua sendo o mesmo: a escolha entra por
    // PARÂMETRO. Ler o armazenamento dentro da função foi o defeito que
    // congelava as rotas no valor do primeiro render.
    const LIB = readFileSync(
      join(__dirname, "..", "lib", "product-choice.ts"),
      "utf-8",
    );
    expect(LIB).toMatch(
      /function needsProductChoice\(\s*user: UsuarioRoteavel,\s*choice: FroidProduct \| null,?\s*\)/,
    );
    expect(LIB).toMatch(
      /function defaultAuthenticatedPath\(\s*user: UsuarioRoteavel,\s*choice: FroidProduct \| null,?\s*\)/,
    );
    // E nenhuma delas lê o armazenamento por dentro.
    const corpo = LIB.slice(LIB.indexOf("export function defaultAuthenticatedPath"));
    expect(corpo).not.toContain("readProductChoice()");
  });

  it("existe uma única decisão de destino após autenticar", () => {
    // Três cópias foi o que produziu o defeito. Quem precisa do destino importa
    // a função; ninguém reescreve a condição.
    for (const arquivo of ["LoginPage.tsx", "AccountAccessPages.tsx"]) {
      const fonte = readFileSync(join(__dirname, arquivo), "utf-8");
      expect(fonte).toContain("defaultAuthenticatedPath(");
      expect(fonte).not.toMatch(
        /onboarding_required\s*\?\s*"\/access\/produto"/,
      );
    }
  });

  it("nenhuma decisão de rota lê o armazenamento durante o render", () => {
    // readProductChoice pode aparecer UMA vez: na inicializacao do useState.
    const leituras = APP.match(/readProductChoice\(\)/g) || [];
    expect(leituras.length).toBe(1);
    const inicializacao = APP.slice(
      APP.indexOf("useState<FroidProduct | null>"),
      APP.indexOf("useState<FroidProduct | null>") + 120,
    );
    expect(inicializacao).toContain("readProductChoice()");
  });

  it("a tela não guarda a escolha em estado próprio", () => {
    // Estado local aqui nao propagaria para as rotas — foi exatamente o
    // desenho que falhou.
    expect(PAGINA).not.toContain("useState");
    expect(PAGINA).toContain("choice: FroidProduct | null");
  });
});

describe("o portão do cadastro", () => {
  it("quem não escolheu não chega na ficha clínica por link direto", () => {
    const rota = APP.slice(
      APP.indexOf('path="/access/register"'),
      APP.indexOf('path="/access/register"') + 700,
    );
    expect(rota).toContain("needsProductChoice(user, productChoice)");
    expect(rota).toContain('<Navigate to="/access/produto" replace />');
  });

  it("quem já concluiu o cadastro não volta a escolher produto", () => {
    const rota = APP.slice(
      APP.indexOf('path="/access/produto"'),
      APP.indexOf('path="/access/produto"') + 500,
    );
    expect(rota).toContain("!onboardingRequired(user)");
    expect(rota).toContain('<Navigate to="/dashboard" replace />');
  });

  it("o logout limpa a escolha", () => {
    // localStorage e do navegador, nao da conta: sem limpar, o proximo usuario
    // desta maquina herdaria a escolha de quem saiu.
    const logout = APP.slice(APP.indexOf("const logout ="), APP.indexOf("const logout =") + 800);
    expect(logout).toContain("resetProductChoice()");
  });
});

describe("a escolha não é fronteira de segurança", () => {
  it("está documentado que ela só decide qual formulário aparece", () => {
    expect(LIB_CORRIDO).toMatch(/n[aã]o concede acesso/i);
    expect(LIB_CORRIDO).toMatch(/access_status/);
  });

  it("armazenamento bloqueado não derruba a aplicação", () => {
    // Navegador com localStorage negado precisa cair na tela de escolha, e
    // nunca lancar.
    for (const trecho of ["readProductChoice", "saveProductChoice", "clearProductChoice"]) {
      const inicio = LIB.indexOf(`export function ${trecho}`);
      expect(inicio, trecho).toBeGreaterThan(-1);
      const corpo = LIB.slice(inicio, LIB.indexOf("\n}", inicio));
      expect(corpo, trecho).toContain("catch");
    }
  });
});

describe("a tela separa os dois produtos sem confundir a fronteira", () => {
  it("diz que o empregador nunca recebe resposta individual", () => {
    expect(PAGINA).toMatch(/nunca recebe resposta individual/i);
  });

  it("não promete diagnóstico no produto corporativo", () => {
    expect(PAGINA).toMatch(/n[aã]o produz diagn[oó]stico/i);
  });

  it("avisa dos dois pisos antes de agendar", () => {
    expect(PAGINA).toMatch(/anonimato/i);
    expect(PAGINA).toMatch(/representatividade/i);
  });

  it("oferece o cadastro guiado em vez de terminar em e-mail", () => {
    // O painel do NR-1 só oferecia "escreva para froid@froid.com.br". Era resto
    // de quando /access/empresa ainda não existia: entregue depois, nunca foi
    // ligado aqui, e quem escolhia empresa ficava sem próximo passo.
    expect(PAGINA).toContain('to="/access/empresa"');
    expect(PAGINA).toMatch(/Continuar o cadastro da empresa/);
  });
});
