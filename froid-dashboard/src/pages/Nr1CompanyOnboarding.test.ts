import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * Travas do cadastro guiado da empresa NR-1.
 *
 * A primeira é de segurança e não de interface. A empresa precisa entrar como
 * `nr1_company`, porque é esse valor que produz uma organização `enterprise` —
 * e só nesse tipo o servidor retira dos papéis do empregador as permissões
 * clínicas identificadas. Trocado por "organization", o cadastro criaria uma
 * CLÍNICA, e o dono da empresa passaria a carregar patients.read_all e
 * reports.read_all.
 */

const PAGINA = readFileSync(join(__dirname, "Nr1CompanyOnboarding.tsx"), "utf-8");
/** Texto de JSX quebra em varias linhas. Procurar frase sem normalizar reprova
 *  codigo correto — foi assim que a primeira versao deste arquivo falhou em
 *  "nao recebe prontuario", com as duas palavras em linhas diferentes. */
const PAGINA_CORRIDA = PAGINA.replace(/\s+/g, " ");
const APP = readFileSync(join(__dirname, "..", "App.tsx"), "utf-8");
const ESCOLHA = readFileSync(join(__dirname, "ProductChoice.tsx"), "utf-8");
const ROTAS = readFileSync(
  join(__dirname, "..", "lib", "product-choice.ts"),
  "utf-8",
);

describe("a empresa não pode virar clínica", () => {
  it("envia account_type nr1_company", () => {
    expect(PAGINA).toContain('account_type: "nr1_company"');
  });

  it("nunca envia account_type organization", () => {
    expect(PAGINA).not.toContain('account_type: "organization"');
  });

  it("declara na tela o que o empregador não recebe", () => {
    // O texto não é decorativo: é a promessa que o tipo de organização
    // sustenta tecnicamente, e precisa estar visível antes do cadastro.
    expect(PAGINA_CORRIDA).toMatch(/n[aã]o recebe resposta individual/i);
    expect(PAGINA_CORRIDA).toMatch(/n[aã]o recebe prontu[aá]rio/i);
    expect(PAGINA_CORRIDA).toMatch(/estrutural/i);
  });
});

describe("o caminho até a tela", () => {
  it("a escolha NR-1 leva ao cadastro da empresa", () => {
    // O destino saiu da tela e virou pathForProduct, para que a rota do NR-1
    // seja a MESMA em todo lugar que decide para onde mandar quem ainda está
    // se cadastrando. Antes o App mandava todo mundo para /access/register, e
    // a empresa reaparecia no formulário clínico.
    expect(ESCOLHA).toContain("pathForProduct(produto)");
    expect(ROTAS).toContain('return product === "nr1" ? "/access/empresa"');
  });

  it("a empresa NR-1 vira account_type nr1_company na origem da escolha", () => {
    // É este mapa que decide o organization_type no servidor. Trocar "nr1"
    // para "organization" aqui criaria uma clínica com os dados da empresa.
    expect(ROTAS).toContain('nr1: "nr1_company"');
    expect(ROTAS).toContain('clinic: "organization"');
    expect(ROTAS).toContain('individual: "individual"');
  });

  it("quem não escolheu produto não entra direto", () => {
    const rota = APP.slice(
      APP.indexOf('path="/access/empresa"'),
      APP.indexOf('path="/access/empresa"') + 700,
    );
    expect(rota).toContain("needsProductChoice(user, productChoice)");
    expect(rota).toContain('<Navigate to="/access/produto" replace />');
  });

  it("continua alcançável depois de concluído o cadastro", () => {
    // A empresa volta aqui para acrescentar filial ou corrigir efetivo. Se a
    // rota checasse onboarding_required como as outras, ficaria trancada
    // justamente para quem já é cliente.
    const rota = APP.slice(
      APP.indexOf('path="/access/empresa"'),
      APP.indexOf('path="/access/empresa"') + 700,
    );
    expect(rota).not.toContain("!onboardingRequired(user)");
  });
});

describe("a estrutura é ensinada enquanto é preenchida", () => {
  it("separa estabelecimento de departamento", () => {
    // Foi o mal-entendido comercial que precos.html precisou desfazer: cinco
    // setores no mesmo endereço são uma base, não cinco.
    expect(PAGINA_CORRIDA).toMatch(/n[aã]o é estabelecimento/i);
  });

  it("avisa dos dois portões no momento em que o efetivo é digitado", () => {
    // Havia um PISO_UNIDADE = 75 fixo aqui, herdado de quando o único portão
    // era o de anonimato. Desde a migration 025 a exigência depende do efetivo,
    // então o aviso tem de ser derivado do mesmo espelho que o resto do painel
    // usa — número fixo voltaria a prometer o que o banco vai suprimir.
    // A checagem e pela DECLARACAO, nao pela palavra: o comentario que
    // explica por que a constante saiu precisa poder cita-la pelo nome.
    expect(PAGINA).not.toMatch(/const PISO_UNIDADE\s*=/);
    expect(PAGINA).toContain("nr1-representatividade");
    expect(PAGINA).toContain("exigidoNoRecorte");
    expect(PAGINA_CORRIDA).toMatch(/recorte pr[oó]prio/i);
    expect(PAGINA_CORRIDA).toMatch(/censo/i);
  });

  it("nomeia a AEP quando a unidade não alcança nem o piso absoluto", () => {
    // Abaixo de 50 nenhuma campanha publica, por mais adesão que haja. Dizer só
    // "não dá" deixa a empresa sem caminho de conformidade — e ela tem um.
    expect(PAGINA).toContain("PISO_CAMPANHA");
    expect(PAGINA_CORRIDA).toMatch(/AEP/);
  });

  it("explica que setor suprimido não é falha", () => {
    expect(PAGINA_CORRIDA).toMatch(/suprimido/i);
  });

  it("avisa quando a soma dos setores passa do efetivo da unidade", () => {
    expect(PAGINA).toContain("somaSetores > site.headcount");
  });
});

describe("o que falta antes da campanha aparece na conferência", () => {
  it("nomeia o canal de apoio como bloqueante", () => {
    expect(PAGINA_CORRIDA).toMatch(/canal de apoio/i);
    expect(PAGINA_CORRIDA).toMatch(/recusa abrir campanha/i);
  });

  it("nomeia os critérios de gradação e a coerência com o PGR", () => {
    expect(PAGINA_CORRIDA).toMatch(/crit[eé]rios de grada[çc][aã]o/i);
    expect(PAGINA_CORRIDA).toMatch(/PGR/);
  });

  it("traz o canal de contato combinado", () => {
    expect(PAGINA).toContain('const CONTATO = "froid@froid.com.br"');
  });
});

describe("arquivar, nunca excluir", () => {
  it("a tela só oferece arquivamento", () => {
    // O inventário aponta para a unidade e precisa sobreviver vinte anos
    // (1.5.7.3.3.1). A tela não pode oferecer um botão que o servidor recusa.
    expect(PAGINA).toContain('status: "archived"');
    expect(PAGINA).not.toContain('method: "DELETE"');
  });
});
