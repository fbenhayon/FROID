import { describe, expect, it } from "vitest";
import { TOOLTIP_TEXT } from "./RiskChart";
import { tooltipText } from "../../lib/tooltip-i18n";

/**
 * As chaves do i18n sao o proprio texto em pt-BR. Mudar o texto-fonte sem
 * mudar a chave nao quebra nada visivel: o profissional em EN/FR/ES
 * simplesmente volta a ler portugues, e ninguem percebe ate um cliente
 * reclamar. Este teste torna a divergencia uma falha de build.
 */
describe("tooltips do grafico de padroes", () => {
  const chaves = Object.entries(TOOLTIP_TEXT);

  it("tem traducao para os tres idiomas em todos os padroes", () => {
    const semTraducao: string[] = [];
    for (const [id, pt] of chaves) {
      for (const locale of ["en-US", "fr-FR", "es-ES"]) {
        if (tooltipText(locale, pt) === pt) semTraducao.push(`${id}/${locale}`);
      }
    }
    expect(semTraducao).toEqual([]);
  });

  /**
   * O grafico exibia percentuais para "Depressao", "Ansiedade somatica" e
   * "Ativacao de mania", crachados com PHQ-9, HAMD e YMRS — instrumentos que o
   * FROID nao aplica e contra os quais nunca foi validado.
   */
  it("nao nomeia condicao clinica nem instrumento que o FROID nao aplica", () => {
    const proibidos = [
      "phq-9", "phq9", "hamd", "ymrs", "beck", "gad-7",
      "depress", "mania", "dissocia", "trauma", "ansiedade som",
      "risco de", "retraumat",
    ];
    for (const [id, texto] of chaves) {
      const baixo = texto.toLowerCase();
      // "quadros depressivos" e citacao de literatura com ressalva explicita,
      // e nao rotulo atribuido ao paciente — permitido so nessa forma.
      const limpo = baixo.replace("descrita em quadros depressivos", "");
      const achados = proibidos.filter((termo) => limpo.includes(termo));
      expect(achados, `${id}: ${achados.join(", ")}`).toEqual([]);
    }
  });

  it("mantem a ressalva de nivel de grupo onde cita literatura", () => {
    for (const [id, texto] of chaves) {
      if (texto.toLowerCase().includes("literatura")) {
        expect(texto, id).toContain("nível de grupo");
      }
    }
  });
});
