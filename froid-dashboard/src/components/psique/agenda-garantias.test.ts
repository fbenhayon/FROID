import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * As garantias da agenda interna e da tela de papéis, afirmadas no arquivo
 * (revisão de 20/10/2026, itens 3, 12, 13 e 27). Cada uma custou um defeito
 * real: o reagendamento recusado que criava um segundo atendimento, o clique
 * duplo que invertia a concessão, o cancelamento sem motivo, a lista vazia
 * indistinguível de falha de leitura.
 */
const AGENDA = readFileSync(join(__dirname, "AgendaInterna.tsx"), "utf-8");
const PAPEIS = readFileSync(join(__dirname, "PapeisV2.tsx"), "utf-8");

describe("AgendaInterna", () => {
  it("só sai do modo edição quando o reagendamento foi aplicado", () => {
    const aplicado = AGENDA.indexOf('r.estado === "ok" && r.dados.applied) {');
    expect(aplicado).toBeGreaterThan(-1);
    const bloco = AGENDA.slice(aplicado, AGENDA.indexOf("} else {", aplicado));
    expect(bloco).toContain("setEditando(null)");
    // No ramo recusado o item continua em edição e o motivo é traduzido.
    const recusado = AGENDA.slice(AGENDA.indexOf("} else {", aplicado), AGENDA.indexOf("} else {", aplicado) + 500);
    expect(recusado).not.toContain("setEditando(null)");
    expect(recusado).toContain("traduzirMotivo(");
    expect(recusado).toContain("O atendimento original continua marcado");
  });

  it("o item em edição acompanha a versão nova depois da releitura", () => {
    expect(AGENDA).toContain("atual.version !== editando.version) setEditando(atual)");
  });

  it("cancela com motivo informado, sem janela bloqueante e sem clique duplo", () => {
    expect(AGENDA).not.toContain("window.confirm(");
    expect(AGENDA).toContain("Informe o motivo do cancelamento.");
    expect(AGENDA).toContain("if (!cancelando || salvando) return;");
    expect(AGENDA).toContain("reason: motivoInformado");
    expect(AGENDA).not.toContain('reason: "painel"');
  });

  it("os botões só aparecem em marcado e confirmado, e o status sai traduzido", () => {
    expect(AGENDA).toContain("podeOperarOAtendimento(item.appointment_status)");
    expect(AGENDA).toContain("rotuloDoStatus(item.appointment_status)");
    expect(AGENDA).not.toContain(">{item.appointment_status}<");
  });

  it("falha ao ler clínicos ou pacientes aparece como falha, não como lista vazia", () => {
    expect(AGENDA).toContain('clinicos.estado === "falhou"');
    expect(AGENDA).toContain("Os clínicos não puderam ser lidos");
    expect(AGENDA).toContain('pacientes.estado === "falhou"');
    expect(AGENDA).toContain("Os pacientes não puderam ser lidos");
    // "Nenhum clínico" só depois de a lista ter sido lida.
    expect(AGENDA.indexOf('clinicos.estado === "falhou"')).toBeLessThan(AGENDA.indexOf("Nenhum clínico com papel V2"));
  });

  it("reconhece o clínico pelo vínculo, nunca por e-mail", () => {
    expect(AGENDA).toContain("c.membership_id === papel.membershipId");
    expect(AGENDA).not.toContain("usuarioArmazenado");
    expect(AGENDA).not.toContain("email.toLowerCase() === ");
  });

  it("datas e limites da semana ficam no fuso da agenda", () => {
    expect(AGENDA).toContain("limitesDaSemana(dias, FUSO_PADRAO)");
    expect(AGENDA).toContain("diaNoFuso(item.start_at, FUSO_PADRAO)");
    expect(AGENDA).not.toContain("diaIso(new Date(item.start_at))");
    expect(AGENDA).not.toContain("function minutosDe(");
  });
});

describe("PapeisV2", () => {
  it("o botão fica travado até a releitura terminar", () => {
    const alternar = PAPEIS.slice(PAPEIS.indexOf("const alternar = async"), PAPEIS.indexOf("const v2 ="));
    expect(alternar).toContain("if (ocupado) return;");
    expect(alternar).toContain("await carregar();");
    expect(alternar).toContain("} finally {\n      setOcupado(false);");
    // carregar() acontece ANTES de liberar o botão.
    expect(alternar.indexOf("await carregar();")).toBeLessThan(alternar.indexOf("setOcupado(false)"));
  });

  it("limpa o aviso a cada ação e mostra o motivo das falhas", () => {
    expect(PAPEIS).toContain("traduzirMotivo(");
    expect(PAPEIS).toContain('data-campo="estado-dos-papeis"');
    expect(PAPEIS).toContain("não lido: ${traduzirMotivo(capacidades.motivo)}");
    // Só a rota ausente (404) esconde a seção.
    expect(PAPEIS).toContain("capacidades.motivo === MOTIVO_DE_ROTA_AUSENTE");
    expect(PAPEIS).not.toContain('capacidades.motivo !== "CARREGANDO") {\n    // Flag desligado');
  });
});
