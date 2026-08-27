import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { interpretarLinha, linkDoConvite, montarCsv } from "./Nr1Campaign";

/**
 * Travas da camada de coleta — campanha e convites.
 *
 * O defeito que motivou esta tela nao foi um bug: foi uma ausencia. Criar
 * campanha, abrir a coleta e emitir convites existiam no servidor desde a
 * migration 010, e nenhuma tela os chamava. E o terceiro caso do mesmo padrao
 * neste modulo — desenho completo, camada ausente — e o teste estrutural
 * abaixo existe para que a proxima remocao de link seja reprovada em vez de
 * passar despercebida.
 */

const PAGINA = readFileSync(join(__dirname, "Nr1Campaign.tsx"), "utf-8");
const PAGINA_CORRIDA = PAGINA.replace(/\s+/g, " ");
const APP = readFileSync(join(__dirname, "..", "App.tsx"), "utf-8");
const PAINEL = readFileSync(join(__dirname, "Nr1Dashboard.tsx"), "utf-8");
const DASHBOARD = readFileSync(join(__dirname, "Dashboard.tsx"), "utf-8");

const UNIDADES = [
  {
    unit_id: "u-1",
    parent_unit_id: null,
    unit_type: "site" as const,
    name: "Matriz",
    external_code: "SP01",
    headcount: 120,
    status: "active",
    child_count: 2,
  },
  {
    unit_id: "u-2",
    parent_unit_id: "u-1",
    unit_type: "sector" as const,
    name: "Operações",
    external_code: "OPS",
    headcount: 60,
    status: "active",
    child_count: 0,
  },
];

describe("a lista que o RH cola", () => {
  it("aceita matrícula sozinha", () => {
    expect(interpretarLinha("10432", UNIDADES)).toEqual({
      payroll_number: "10432",
      unit_id: null,
      setorNaoEncontrado: "",
    });
  });

  it("casa o setor pelo nome, sem diferenciar maiúscula", () => {
    // O RH conhece a unidade pelo nome que usa, nunca pelo UUID. Exigir o id
    // tornaria a lista impossível de montar a partir da folha de pagamento.
    expect(interpretarLinha("10433;operações", UNIDADES)?.unit_id).toBe("u-2");
  });

  it("casa o setor pelo código interno", () => {
    expect(interpretarLinha("10434;OPS", UNIDADES)?.unit_id).toBe("u-2");
  });

  it("aceita vírgula e tabulação, porque a lista vem de planilha", () => {
    expect(interpretarLinha("10435,Operações", UNIDADES)?.unit_id).toBe("u-2");
    expect(interpretarLinha("10436\tOperações", UNIDADES)?.unit_id).toBe("u-2");
  });

  it("nomeia o setor que não existe em vez de descartá-lo em silêncio", () => {
    // Descartar calado mandaria a pessoa para a campanha sem recorte e
    // ninguém saberia por quê — o número só apareceria errado no fim.
    const linha = interpretarLinha("10437;Jurídico", UNIDADES);
    expect(linha?.unit_id).toBeNull();
    expect(linha?.setorNaoEncontrado).toBe("Jurídico");
  });

  it("ignora linha vazia", () => {
    expect(interpretarLinha("   ", UNIDADES)).toBeNull();
    expect(interpretarLinha("", UNIDADES)).toBeNull();
  });
});

describe("o arquivo que o RH usa para distribuir", () => {
  it("separa por ponto e vírgula e começa com BOM", () => {
    // Excel em pt-BR abre CSV virgulado numa coluna só, e come o acento sem o
    // BOM. A planilha chegaria ilegível justamente a quem precisa usá-la sob
    // pressa, com centenas de linhas.
    const csv = montarCsv([{ payroll_number: "10432", token: "abc" }]);
    expect(csv.startsWith("﻿")).toBe(true);
    expect(csv).toContain("matricula;link");
    expect(csv).toContain("10432;");
  });

  it("monta o link sem hash, para sobreviver a filtro de e-mail corporativo", () => {
    // /avaliacao é rota direta e normalizeDirectPublicPath a reescreve
    // preservando a query. O link com # funcionaria e passaria muito pior.
    const link = linkDoConvite("abc");
    expect(link).toContain("/avaliacao?token=abc");
    expect(link).not.toContain("#");
  });

  it("escapa o token na URL", () => {
    expect(linkDoConvite("a b+c")).toContain("token=a%20b%2Bc");
  });
});

describe("a camada não pode voltar a ficar sem porta", () => {
  it("a rota da campanha existe no App", () => {
    expect(APP).toContain('path="/nr1/campanha"');
    expect(APP).toContain("<Nr1Campaign user={user} />");
  });

  it("o painel NR-1 aponta para campanha e para a estrutura", () => {
    // O defeito original: /access/empresa continuou alcançável de propósito
    // depois do cadastro, e nenhuma tela apontava para ela. Quem terminava o
    // cadastro não tinha mais como criar unidade nenhuma.
    expect(PAINEL).toContain('nav("/nr1/campanha")');
    expect(PAINEL).toContain('nav("/access/empresa")');
  });

  it("o painel clínico aponta a empresa para a própria estrutura", () => {
    expect(DASHBOARD).toContain('nav("/access/empresa")');
  });
});

describe("o que a tela precisa dizer antes da coleta", () => {
  it("avisa que os links aparecem uma vez só", () => {
    // O servidor guarda o digest, nunca o token. Sair da tela sem baixar o
    // arquivo significa reemitir, o que invalida os já distribuídos.
    expect(PAGINA_CORRIDA).toMatch(/uma [uú]nica vez|uma vez/i);
    expect(PAGINA).toContain("beforeunload");
  });

  it("exige canal de apoio antes de deixar criar a campanha", () => {
    // O banco recusa abrir coleta sem canal. Repetir a exigência aqui é o que
    // evita descobrir isso depois de preencher a tela inteira.
    expect(PAGINA_CORRIDA).toMatch(/canal de apoio.{0,80}obrigat[oó]rio/i);
  });

  it("recusa lista com matrícula repetida", () => {
    // Duas linhas para a mesma pessoa inflam o denominador da adesão, e a
    // adesão é o que decide se o resultado publica.
    expect(PAGINA_CORRIDA).toMatch(/Matr[ií]cula repetida/i);
  });

  it("mostra a exigência de respostas na hora em que o efetivo é digitado", () => {
    expect(PAGINA).toContain("exigidoNaCampanha");
    expect(PAGINA).toContain("exigeCenso");
  });

  it("diz, por estabelecimento, o que cada um publica sozinho", () => {
    // Numa empresa com muitos endereços pequenos quase nenhum recorte vence o
    // portão. Descobrir isso com o painel aberto na frente do cliente é a pior
    // hora possível.
    expect(PAGINA).toContain("exigidoNoRecorte");
    expect(PAGINA_CORRIDA).toMatch(/publica sozinho/i);
  });

  it("explica que recorte reprovado vira linha declarada, e não sumiço", () => {
    // Painel vazio é lido como "não há risco aqui", que é a única conclusão
    // que a ausência de dado nunca autoriza.
    expect(PAGINA_CORRIDA).toMatch(/declarada insuficiente/i);
  });
});

describe("a fronteira continua de pé nesta tela", () => {
  it("não pede nome, CPF nem e-mail do trabalhador", () => {
    // A matrícula vira pseudônimo por HMAC no servidor. Coletar nome aqui
    // reintroduziria o par identidade↔resposta que o módulo inteiro existe
    // para não ter.
    expect(PAGINA).not.toMatch(/\bcpf\b/i);
    expect(PAGINA).toContain("payroll_number");
  });

  it("declara que o par matrícula–link não é guardado", () => {
    expect(PAGINA_CORRIDA).toMatch(/nunca o par|n[aã]o guarda o par/i);
  });
});

describe("o ciclo da campanha se fecha pela tela", () => {
  /**
   * Encerrar era o quarto caso do mesmo padrão deste módulo: a rota existia no
   * servidor desde a migration 010 e nenhuma tela a chamava.
   *
   * E aqui a ausência era pior do que um botão faltando. O painel só serve
   * agregado de campanha ENCERRADA — durante a coleta, de propósito, só a
   * adesão é legível. Sem botão de encerrar, o resultado inteiro do módulo
   * ficava inalcançável pela interface: nem painel, nem inventário, nem plano
   * de ação. Quem operasse o produto teria de fechar a campanha por chamada
   * direta à API, que é exatamente o que a existência desta tela nega.
   */

  it("chama a rota de encerramento", () => {
    expect(PAGINA).toContain("/close");
    expect(PAGINA).toContain("const fechar");
  });

  it("oferece o botão para campanha em coleta, e não só para rascunho", () => {
    // O `status === "draft"` sozinho era a condição de todo o bloco de ações:
    // campanha aberta não tinha ação nenhuma disponível.
    expect(PAGINA).toContain('campanha.status === "open"');
    expect(PAGINA_CORRIDA).toMatch(/Encerrar coleta/);
  });

  it("exige confirmação em dois passos", () => {
    // Encerrar é definitivo: não existe rota que devolva uma campanha
    // encerrada ao estado aberto, e os links pendentes morrem junto.
    expect(PAGINA).toContain("confirmandoFecho");
    expect(PAGINA_CORRIDA).toMatch(/Confirmar encerramento/);
    expect(PAGINA_CORRIDA).toMatch(/n[aã]o tem volta/i);
  });

  it("diz o que se ganha e o que se perde ao encerrar", () => {
    expect(PAGINA_CORRIDA).toMatch(/perde a chance/i);
    expect(PAGINA_CORRIDA).toMatch(/invent[aá]rio/i);
  });

  it("não mostra o enum do banco para o cliente", () => {
    // "DRAFT" ao lado de uma campanha que já custou dinheiro, numa tela que a
    // empresa abre na frente da diretoria dela.
    expect(PAGINA).toContain("ESTADO_DA_CAMPANHA");
    expect(PAGINA_CORRIDA).toMatch(/draft: "Rascunho"/);
    expect(PAGINA_CORRIDA).toMatch(/closed: "Encerrada"/);
  });
});
