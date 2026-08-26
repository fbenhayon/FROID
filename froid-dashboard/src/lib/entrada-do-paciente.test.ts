import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * O que acontece quando o link do convite é clicado várias vezes.
 *
 * Apurado em 26/08/2026, depois de uma sessão em que o paciente abriu no
 * telefone e depois no computador, e nada sincronizou.
 *
 * O QUE O SERVIDOR FAZ, e é correto:
 *
 * - o convite NÃO é de uso único: `join` pode ser chamado quantas vezes for,
 *   e não cria sessão nova — é sempre o mesmo session_id
 * - o servidor já contava as aberturas e devolvia `join_count`
 * - `RtcSignalManager` guarda UM socket por papel: quem entra por último
 *   desconecta o anterior com o código 4000
 *
 * O QUE FALTAVA, e é o defeito:
 *
 * - o paciente não era avisado de nada — nem de que o navegador ia pedir
 *   permissão, nem de que sem ela a sessão não começa, nem de que um segundo
 *   aparelho desconecta o primeiro
 * - `join_count` nunca foi lido por ninguém
 * - o profissional via a chamada cair sem ter como saber que a causa estava
 *   do outro lado, num segundo aparelho
 *
 * Quem não sabe o que esperar interpreta a espera como defeito, fecha a página
 * e reabre — e reabrir é justamente o que desconecta. A instrução ausente
 * fabricava o problema que ela deveria evitar.
 */

const PACIENTE = readFileSync(
  join(__dirname, "..", "pages", "PatientSessionPage.tsx"),
  "utf-8",
);
const PROFISSIONAL = readFileSync(
  join(__dirname, "..", "pages", "LiveSession.tsx"),
  "utf-8",
);
const IDIOMAS = readFileSync(join(__dirname, "localization.ts"), "utf-8");

const CHAVES = [
  "howItWorksTitle",
  "howItWorksStep1",
  "howItWorksStep2",
  "howItWorksStep3",
  "howItWorksOneDevice",
  "alreadyOpenElsewhere",
];

describe("o paciente sabe o que vai acontecer antes de acontecer", () => {
  it("a tela mostra os três passos", () => {
    for (const chave of ["howItWorksStep1", "howItWorksStep2", "howItWorksStep3"]) {
      expect(PACIENTE).toContain(`copy.${chave}`);
    }
  });

  /** O texto de uma chave, e não a declaração do tipo.
   *
   *  `indexOf(chave)` cai na linha `howItWorksStep2: string;` do tipo, que vem
   *  antes de todas as traduções — e aí a asserção lê declaração em vez de
   *  frase.
   *
   *  Escrito com varredura de string, e não com expressão regular: a primeira
   *  versão usava RegExp e a quebra de linha do template literal a corrompeu
   *  em silêncio, devolvendo zero resultados. Regex montada por template é
   *  exatamente o que se corrompe quando este arquivo é editado por script.
   */
  const textoDe = (chave: string, ordem = 0) => {
    const achados: string[] = [];
    let de = 0;
    for (;;) {
      const i = IDIOMAS.indexOf(chave + ":", de);
      if (i < 0) break;
      de = i + chave.length + 1;
      const aspa = IDIOMAS.indexOf('"', de);
      const pontoEVirgula = IDIOMAS.indexOf(";", de);
      // `chave: string;` do tipo não tem aspas antes do ponto e vírgula.
      if (aspa < 0 || (pontoEVirgula >= 0 && pontoEVirgula < aspa)) continue;
      const fecha = IDIOMAS.indexOf('"', aspa + 1);
      if (fecha < 0) break;
      achados.push(IDIOMAS.slice(aspa + 1, fecha));
    }
    expect(achados.length).toBe(4);
    return achados[ordem];
  };

  it("avisa que o navegador vai pedir permissão, e que sem ela não começa", () => {
    const texto = textoDe("howItWorksStep2");
    expect(texto).toMatch(/permiss[ãa]o/i);
    expect(texto).toMatch(/n[ãa]o come[çc]a|Permitir/i);
  });

  it("diz que depois disso não há mais nada a fazer", () => {
    // É a frase que impede o paciente de mexer na página achando que travou.
    expect(textoDe("howItWorksStep3")).toMatch(
      /sozinho|n[ãa]o precisa fazer mais nada/i,
    );
  });

  it("avisa para usar um aparelho só, com o motivo", () => {
    const texto = textoDe("howItWorksOneDevice");
    expect(texto).toMatch(/um aparelho s[óo]/i);
    expect(texto).toMatch(/desconectado/i);
  });

  it("some quando a mídia já está ativa", () => {
    // Instrução que não sai da tela depois de cumprida vira ruído.
    expect(PACIENTE).toContain('mediaState !== "active" && (');
  });
});

describe("reabrir o link deixa de ser silencioso", () => {
  it("o paciente lê join_count e avisa se já abriu antes", () => {
    expect(PACIENTE).toContain("join_count");
    expect(PACIENTE).toContain("aberturasAnteriores");
    expect(PACIENTE).toContain("copy.alreadyOpenElsewhere");
  });

  it("o aviso não bloqueia a entrada", () => {
    // O paciente pode ter fechado o outro aparelho legitimamente. Travar quem
    // tem direito de entrar seria pior que o problema.
    const i = PACIENTE.indexOf("aberturasAnteriores > 0");
    expect(PACIENTE.slice(i, i + 300)).not.toContain("disabled");
  });

  it("o profissional é avisado de aberturas repetidas", () => {
    expect(PROFISSIONAL).toContain("aberturasRef");
    const corrido = PROFISSIONAL.replace(/\s+/g, " ");
    expect(corrido).toMatch(/abriu o link .* vezes/i);
    expect(corrido).toMatch(/pe[çc]a para fechar l[áa]/i);
  });
});

describe("nenhum idioma fica sem a instrução", () => {
  // Idioma sem as chaves mostraria a tela muda que motivou tudo isto. O tipo
  // já obriga; o teste confere que as quatro traduções existem de fato.
  for (const chave of CHAVES) {
    it(`${chave} existe nos quatro idiomas`, () => {
      const ocorrencias = IDIOMAS.split(`${chave}:`).length - 1;
      // 4 traduções + 1 declaração no tipo.
      expect(ocorrencias).toBe(5);
    });
  }
});
