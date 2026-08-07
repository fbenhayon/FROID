import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * Travas do cadastro, escritas depois de um cliente ver a tela reduzida.
 *
 * O cadastro completo existia inteiro no arquivo — tipo de conta, CPF, CNPJ,
 * endereco, contrato por tipo — e estava desligado por uma constante de fase de
 * testes. Quem apresentou o produto concluiu que a diferenciacao nao existia.
 *
 * Os testes leem a fonte em vez de montar o componente de proposito: o defeito
 * nao era de renderizacao, era uma constante no topo do arquivo, e e exatamente
 * isso que precisa ficar preso.
 */

const FONTE = readFileSync(
  join(__dirname, "ProfessionalOnboarding.tsx"),
  "utf-8",
);

/** Recorta ate a proxima declaracao de topo, e nao por N caracteres: cortar por
 * tamanho ja reprovou codigo correto aqui antes. */
function trechoDe(inicio: string, fim: string): string {
  const i = FONTE.indexOf(inicio);
  expect(i, `ancora ausente: ${inicio}`).toBeGreaterThan(-1);
  const f = FONTE.indexOf(fim, i + inicio.length);
  expect(f, `fim ausente apos ${inicio}`).toBeGreaterThan(i);
  return FONTE.slice(i, f);
}

describe("cadastro reduzido de testes", () => {
  it("permanece desligado", () => {
    expect(FONTE).toContain("const TESTING_MINIMAL_ONBOARDING = false;");
  });

  it("mantem o aviso de que religar e uma regressao, e nao um atalho", () => {
    const cabecalho = FONTE.slice(0, FONTE.indexOf("TESTING_MINIMAL_ONBOARDING"));
    expect(cabecalho).toMatch(/regress[aã]o/i);
  });
});

describe("diferenciacao entre pessoa fisica e juridica", () => {
  const validacao = trechoDe("const requiredFields =", "const addressFields");

  it("exige CPF na pessoa fisica", () => {
    expect(validacao).toContain('"cpf", fields.cpf');
  });

  it("exige registro profissional na pessoa fisica", () => {
    // Quem interpreta o sinal responde por um conselho. O cadastro completo
    // trazia o campo apenas como dado fiscal opcional.
    expect(validacao).toContain('"professionalRegistry", fields.professionalRegistry');
  });

  it("exige CNPJ e representante legal na pessoa juridica", () => {
    for (const campo of [
      '"cnpj", fields.cnpj',
      '"legalRepresentativeCpf", fields.legalRepresentativeCpf',
      '"legalRepresentativeEmail", fields.legalRepresentativeEmail',
    ]) {
      expect(validacao).toContain(campo);
    }
  });

  it("vincula o contrato correspondente ao tipo de conta", () => {
    expect(FONTE).toContain("#/contrato-clinica");
    expect(FONTE).toContain("#/contrato-profissional");
  });
});

describe("blocos de compliance", () => {
  it("aparecem por titulo, com o descritivo em expansao", () => {
    // O pedido era nao empilhar o texto integral na frente de quem preenche o
    // cadastro. O conteudo continua na pagina — recolhido, nao removido.
    const bloco = trechoDe("<SecurityAssurance", "</div>");
    expect(bloco).toContain("CollapsibleDisclosure");

    const lgpd = trechoDe("<LgpdNotice audience=\"professional\"", "</div>");
    expect(lgpd).toContain("CollapsibleDisclosure");
  });

  it("mantem cada aceite como titulo mais link para a versao integral", () => {
    const aceites = trechoDe('id="legal-contract-consent"', "</div>");
    expect(aceites).toContain("Termos Gerais de Uso");
    expect(aceites).toContain("abrir versão integral");
  });
});
