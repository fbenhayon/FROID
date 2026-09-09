import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * As saídas da tela de campanha — o que acontece quando o operador se perde.
 *
 * Em 09/09/2026 um cliente criou QUATRO campanhas onde deviam existir duas, em
 * dois pares de títulos idênticos, e emitiu oito convites numa campanha que
 * declarava quinze trabalhadores. Cada passo dele foi consequência da tela:
 *
 *   1. criar não mudava NADA na tela — o aviso de sucesso nasce no topo da
 *      página e o botão fica no fim de um formulário longo. Clicou de novo.
 *   2. a lista mostrava título e estado, e duas campanhas homônimas ficavam
 *      indistinguíveis. Selecionou a errada.
 *   3. o passo 3 escrevia "(draft)" cru, enquanto o passo 2 já escrevia
 *      "Rascunho" — nada dizia que ali o link não abre.
 *   4. nada avisava que com quinze trabalhadores a campanha exige censo, e
 *      que oito convites nunca publicariam.
 *   5. não havia como desfazer nada.
 *
 * Estes testes afirmam as garantias, não a redação: eles procuram o mecanismo
 * que impede cada passo, porque texto se reescreve e a garantia não pode cair
 * junto.
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

describe("criar duas vezes por engano", () => {
  it("o título é esvaziado depois de criar", () => {
    // O único campo que a campanha seguinte precisa ter diferente. Enquanto
    // ele continuar preenchido, o segundo clique produz uma homônima.
    expect(corpoDe("criar")).toContain('setTitulo("")');
  });

  it("os campos que são da EMPRESA continuam preenchidos", () => {
    // Limpar tudo faria a segunda campanha legítima custar o formulário
    // inteiro de novo — e o remédio não pode ser pior que a doença.
    const corpo = corpoDe("criar");
    for (const setter of [
      "setPeriodo(",
      "setEfetivo(",
      "setFinalidade(",
      "setCanalRotulo(",
      "setCanalDetalhe(",
      "setUnidadeId(",
    ]) {
      expect(corpo, `${setter} não devia ser limpo`).not.toContain(setter);
    }
  });

  it("a confirmação nasce ao lado do botão, não só no topo da página", () => {
    expect(corpoDe("criar")).toContain("setUltimaCriada(");
    expect(CORRIDA).toContain("{ultimaCriada && (");
    // E diz o que o clique seguinte faria.
    expect(CORRIDA).toMatch(/cria uma <strong>segunda<\/strong> campanha/);
  });

  it("avisa antes, quando o título digitado já existe", () => {
    expect(PAGINA).toContain("const tituloJaExiste = useMemo(");
    expect(CORRIDA).toContain("{tituloJaExiste && (");
  });
});

describe("duas campanhas com o mesmo título", () => {
  it("cada linha da lista traz o que a distingue", () => {
    expect(PAGINA).toContain("function identificacaoDaCampanha(");
    expect(CORRIDA).toContain("{identificacaoDaCampanha(campanha)}");
  });

  it("a identificação usa período, abrangência, efetivo, janela e criação", () => {
    const fonte = PAGINA.slice(
      PAGINA.indexOf("function identificacaoDaCampanha("),
      PAGINA.indexOf("export const Nr1Campaign"),
    );
    expect(fonte).toContain("reference_period");
    expect(fonte).toContain("unit_name");
    expect(fonte).toContain("target_headcount");
    expect(fonte).toContain("opens_at");
    expect(fonte).toContain("created_at");
  });

  it("nenhuma parte da identificação é inventada quando falta o dado", () => {
    // Campo ausente escrito como "período —" ou "0 trabalhadores" seria
    // indistinguível do declarado, num painel de conformidade.
    const fonte = PAGINA.slice(
      PAGINA.indexOf("function identificacaoDaCampanha("),
      PAGINA.indexOf("export const Nr1Campaign"),
    );
    expect(fonte).toContain("if (campanha.reference_period)");
    expect(fonte).toContain("if (campanha.target_headcount)");
    expect(fonte).toContain("if (abre && fecha)");
  });

  it("a tela avisa quando há homônimas na lista", () => {
    expect(PAGINA).toContain("const haHomonimas = useMemo(");
    expect(CORRIDA).toContain("{haHomonimas && (");
  });

  it("avisa quando duas campanhas coletam ao mesmo tempo", () => {
    // Dividir os convidados divide as respostas, e duas metades não vencem o
    // portão que a coorte inteira venceria: nenhuma das duas publica.
    expect(CORRIDA).toContain("{emColeta.length > 1 && (");
    expect(CORRIDA).toMatch(/<strong>nenhuma das duas publica<\/strong>/i);
  });
});

describe("convite emitido no estado errado", () => {
  it("o passo 3 nunca escreve o estado cru do banco", () => {
    // Era "(draft)" três centímetros abaixo de "Rascunho".
    expect(PAGINA).not.toContain("({selecionada.status})");
    expect(CORRIDA).toContain(
      "{ESTADO_DA_CAMPANHA[selecionada.status] || selecionada.status}",
    );
  });

  it("encerrada e cancelada não emitem convite, e o botão fica travado", () => {
    // Não há rota que reabra: `nr1_open_campaign` só aceita rascunho. O link
    // nasceria morto e é mostrado uma única vez.
    expect(PAGINA).toContain("const emissaoImpossivel =");
    expect(PAGINA).toContain('selecionada?.status === "closed"');
    expect(PAGINA).toContain('selecionada?.status === "cancelled"');
    expect(corpoDe("gerarConvites")).toContain("if (emissaoImpossivel)");
    expect(CORRIDA).toContain("emissaoImpossivel ||");
  });

  it("rascunho avisa e pede ciência, em vez de proibir", () => {
    // Preparar os convites antes e abrir no dia é fluxo legítimo. O que não
    // pode é acontecer por distração.
    expect(PAGINA).toContain("const [cienteRascunho, setCienteRascunho]");
    expect(corpoDe("gerarConvites")).toContain(
      'selecionada.status === "draft" && !cienteRascunho',
    );
    expect(CORRIDA).toMatch(/convite indispon[ií]vel/i);
  });

  it("trocar de campanha zera a ciência", () => {
    // Sem isso, marcar "emitir mesmo assim" numa campanha valeria para a
    // próxima selecionada — o engano que a caixa existe para impedir.
    expect(CORRIDA).toContain(
      "useEffect(() => { setCienteRascunho(false); }, [selecionada?.campaign_id]);",
    );
  });
});

describe("emitir convites que nunca vão publicar", () => {
  it("compara o teto alcançável com o portão da campanha", () => {
    expect(PAGINA).toContain("const exigidoNaSelecionada = useMemo(");
    expect(PAGINA).toContain("exigidoNaCampanha(Number(selecionada?.target_headcount)");
    expect(PAGINA).toContain("const alcanceInsuficiente =");
    expect(CORRIDA).toContain("{alcanceInsuficiente && (");
  });

  it("convite já emitido ausente não é contado como zero na prosa", () => {
    // O servidor devolve null quando o papel não pode contar convites. Dizer
    // "contando os 0 já emitidos" seria afirmar uma apuração que não houve.
    expect(PAGINA).toContain(
      'typeof selecionada?.invitations === "number" ? selecionada.invitations : null',
    );
    expect(CORRIDA).toContain("{convitesJaEmitidos === null ?");
    expect(CORRIDA).toMatch(/Contando s[óo] os convites desta emiss[ãa]o/);
  });

  it("diz que o teto supõe adesão de 100%", () => {
    // O número é um teto generoso: se nem ele vence o portão, nenhuma adesão
    // vence. Apresentá-lo como previsão seria outra coisa.
    expect(CORRIDA).toMatch(/supondo ades[ãa]o de 100%/);
  });

  it("a contagem de convites da lista não escreve zero sem apuração", () => {
    expect(CORRIDA).toContain('{typeof campanha.invitations === "number" && (');
  });
});

describe("setor que não bate com o cadastro", () => {
  it("diz quais setores existem, não só que não encontrou", () => {
    expect(CORRIDA).toContain("Os setores cadastrados são:");
    expect(CORRIDA).toContain("{setores.map((s) => s.name).join(\", \")}");
    // E o caso em que não há nenhum, que é diferente de não ter achado.
    expect(CORRIDA).toMatch(/Nenhum setor est[áa] cadastrado nesta empresa/);
  });
});

