import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Esperar não é o mesmo que não existir.
 *
 * Ao clicar num paciente, a tela abria o cartão "Paciente não encontrado —
 * ainda não há relatórios locais ou sincronizados para este paciente"
 * ENQUANTO o servidor ainda estava respondendo. O estado inicial de `reports`
 * é o cache do navegador; se o paciente não estivesse nele, `group` ficava
 * indefinido e a tela afirmava a ausência antes de ter o que afirmar.
 *
 * Para quem clicou, o efeito é pior que uma espera: é uma resposta definitiva
 * e errada, seguida de um conteúdo que aparece sozinho alguns segundos depois.
 *
 * A regra que este teste fixa: enquanto a busca estiver no ar, a tela diz que
 * está executando; a ausência só pode ser afirmada depois que a resposta
 * chegou.
 */
const PATIENT_DETAIL = readFileSync(join(__dirname, "PatientDetail.tsx"), "utf-8");

describe("a tela do paciente distingue esperar de não encontrar", () => {
  it("tem um estado próprio para a busca em andamento", () => {
    expect(PATIENT_DETAIL).toContain("carregandoAcervo");
    // O desligamento vive num finally: a busca que falha também termina, e sem
    // isso a tela ficaria presa em "aguarde" para sempre.
    expect(PATIENT_DETAIL).toContain(".finally(");
  });

  it("mostra o aviso de execução antes de afirmar ausência", () => {
    const espera = PATIENT_DETAIL.indexOf(
      "Estamos executando sua Solicitação, aguarde por favor",
    );
    const ausencia = PATIENT_DETAIL.indexOf("Paciente não encontrado");
    expect(espera).toBeGreaterThan(-1);
    expect(ausencia).toBeGreaterThan(-1);
    expect(espera).toBeLessThan(ausencia);
  });

  it("a ausência só é afirmada quando a busca terminou", () => {
    expect(PATIENT_DETAIL).toContain("if (!group && carregandoAcervo)");
  });

  it("o aviso é anunciado a leitor de tela", () => {
    expect(PATIENT_DETAIL).toContain('role="status"');
    expect(PATIENT_DETAIL).toContain('aria-live="polite"');
  });

  it("o botão de voltar respeita de onde a pessoa veio", () => {
    // Voltava sempre para /dashboard, o detalhado, mesmo para quem tinha saído
    // do resumido — que é a casa do profissional.
    expect(PATIENT_DETAIL).toContain("navigate(returnTo)");
  });
});

/**
 * O destino do login e o retorno do link profundo são o MESMO valor.
 *
 * LoginPage cede a vez para a página que a pessoa tentou abrir apenas quando o
 * destino calculado é a casa genérica do clínico. Com o caminho escrito à mão
 * dos dois lados, mudar a casa quebrava esse retorno em silêncio: o destino
 * deixava de bater com a string literal e o link profundo era descartado.
 */
const LOGIN = readFileSync(join(__dirname, "LoginPage.tsx"), "utf-8");

const APP = readFileSync(join(__dirname, "..", "App.tsx"), "utf-8");

/**
 * "Nao pedi nada" e "pedi o painel detalhado" chegavam identicos.
 *
 * `protectedElement` montava o afterLoginPath com
 * `window.location.hash.replace(/^#/, "") || "/dashboard"`. O fallback e o
 * hash deixado por uma sessao anterior produziam a MESMA string, e como o
 * LoginPage cede a vez para o afterLoginPath quando o destino e a casa
 * generica, o profissional voltava ao painel detalhado depois de entrar —
 * mesmo com a casa dele ja apontando para o resumido.
 */
describe("as portas de entrada caem na casa, nao no detalhado", () => {
  it("nao usa mais /dashboard como destino de quem nao pediu nada", () => {
    expect(APP).not.toContain('window.location.hash.replace(/^#/, "") || "/dashboard"');
    expect(APP).toContain("semDestinoProprio");
    expect(APP).toContain("afterLoginPath={semDestinoProprio ? HOME_CLINICO : hash}");
  });

  it("trata as portas de entrada como ausencia de destino", () => {
    for (const porta of ['hash === "/"', 'hash === "/dashboard"',
                         'hash.startsWith("/login")', 'hash.startsWith("/registrar")']) {
      expect(APP).toContain(porta);
    }
  });

  it("link profundo de verdade continua respeitado", () => {
    // A lista de excecoes e fechada: qualquer outra rota cai no `hash`.
    expect(APP).toContain("? HOME_CLINICO : hash");
  });
});

describe("o login não perde o link profundo ao mudar a casa do clínico", () => {
  it("compara com a constante, não com um caminho escrito à mão", () => {
    expect(LOGIN).toContain("destino === HOME_CLINICO ? afterLoginPath : destino");
    expect(LOGIN).not.toContain('destino === "/dashboard"');
  });

  it("o padrão de afterLoginPath é a mesma constante", () => {
    expect(LOGIN).toContain("afterLoginPath = HOME_CLINICO");
    expect(LOGIN).not.toContain('afterLoginPath = "/dashboard"');
  });
});
