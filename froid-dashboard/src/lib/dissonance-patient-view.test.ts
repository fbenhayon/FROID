import { describe, expect, it } from "vitest";
import {
  PATIENT_DESCRIPTION_WORD_LIMIT,
  allPatientViews,
  countWords,
  patientViewFor,
} from "./dissonance-patient-view";

/**
 * O texto que o paciente lê sobre si mesmo.
 *
 * Um relatório de produção trazia "Sorriso falso / falsa calma" e "Mitigar
 * validando a fala sem confrontar bruscamente". Serve ao profissional, que tem
 * formação para contextualizar. Dito a alguém sobre si, sozinho, num PDF que
 * circula, o mesmo texto vira veredito sem juiz.
 */

const VIEWS = allPatientViews();

describe("cobertura", () => {
  it("traduz os oito sinais que o motor produz", () => {
    expect(VIEWS.length).toBe(8);
  });

  it("cada título técnico aparece uma única vez", () => {
    const chaves = VIEWS.map((v) => v.professionalTitle);
    expect(new Set(chaves).size).toBe(chaves.length);
  });

  it("o que não tem tradução é OMITIDO, nunca substituído pelo texto técnico", () => {
    // Cair no texto do profissional seria exatamente o acidente que este módulo
    // impede — e aconteceria no caso novo que ninguém lembrou de traduzir.
    expect(patientViewFor("Sinal que ainda não existe")).toBeNull();
    expect(patientViewFor("")).toBeNull();
  });

  it("encontra pela chave exata", () => {
    const achado = patientViewFor("Sorriso falso / falsa calma");
    expect(achado).not.toBeNull();
    expect(achado?.title).toBe("Sorriso na boca sem o movimento ao redor dos olhos");
  });
});

describe("limite de 100 palavras", () => {
  it("nenhuma descrição passa do limite", () => {
    for (const view of VIEWS) {
      const palavras = countWords(view.description);
      expect(palavras, `${view.professionalTitle}: ${palavras} palavras`)
        .toBeLessThanOrEqual(PATIENT_DESCRIPTION_WORD_LIMIT);
    }
  });

  it("nenhuma é curta demais para dizer o que foi medido", () => {
    for (const view of VIEWS) {
      expect(countWords(view.description), view.professionalTitle).toBeGreaterThan(25);
    }
  });
});

describe("o título descreve o sinal, não a pessoa", () => {
  const ROTULOS = [
    "falso", "falsa", "mascarada", "contida", "desprezo",
    "shutdown", "retraumatiza", "psíquico", "psiquico",
  ];

  it("nenhum título do paciente carrega rótulo de pessoa", () => {
    for (const view of VIEWS) {
      const baixo = view.title.toLowerCase();
      for (const rotulo of ROTULOS) {
        expect(baixo.includes(rotulo), `${view.title} contém "${rotulo}"`).toBe(false);
      }
    }
  });

  it("nenhuma descrição carrega rótulo de pessoa", () => {
    for (const view of VIEWS) {
      const baixo = view.description.toLowerCase();
      for (const rotulo of ROTULOS) {
        expect(baixo.includes(rotulo), `${view.professionalTitle}: "${rotulo}"`).toBe(false);
      }
    }
  });
});

describe("nenhuma descrição prescreve conduta", () => {
  const CONDUTA = /\b(mitigar|facilitar|estimular|acolher|conter|desacelerar|pausar|reduzir|diminuir|restaurar)\s/i;

  it("não diz ao paciente o que fazer", () => {
    for (const view of VIEWS) {
      expect(CONDUTA.test(view.description), view.professionalTitle).toBe(false);
    }
  });

  it("não afirma causa nem estado interno como fato", () => {
    // "indica ansiedade" seria inferência de construto. O texto pode dizer o
    // que foi medido e que a interpretação depende do contexto.
    for (const view of VIEWS) {
      expect(/\bindica (que )?(voc[êe]|ansiedade|depress|tristeza|raiva)/i
        .test(view.description), view.professionalTitle).toBe(false);
    }
  });
});

describe("o documento devolve a interpretação ao profissional", () => {
  it("a maioria das descrições aponta para a conversa clínica", () => {
    // Não exijo em todas: forçar a mesma frase em oito textos produziria
    // repetição que o leitor deixa de ler. Mas a maioria precisa apontar.
    const apontam = VIEWS.filter((v) =>
      /profissional|pr[óo]xima sess[ãa]o|acompanha voc[êe]|com o seu/i.test(v.description),
    );
    expect(apontam.length).toBeGreaterThanOrEqual(Math.ceil(VIEWS.length / 2));
  });
});
