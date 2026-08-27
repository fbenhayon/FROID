# -*- coding: utf-8 -*-
"""Travas da reemissão de convite.

Apurado em 26/08/2026, no teste ponta a ponta com a TATICCA. Numa campanha de
centenas de pessoas alguém apaga a mensagem antes de responder, e até aqui não
havia saída: o servidor guarda só o digest do link, e uma segunda emissão para
a mesma matrícula esbarra no UNIQUE (campaign_id, subject_pseudonym). A única
alternativa era recriar a campanha inteira.

Três invariantes, e as três protegem coisas diferentes:

1. **Quem já respondeu não recebe link novo.** O WHERE do UPDATE exige
   `status = 'pending'`. Sem isso a mesma pessoa responderia duas vezes e a
   coorte a contaria duas — corrompendo justamente o agregado que o módulo
   existe para produzir.

2. **A linha é atualizada, nunca duplicada.** `invited` conta linhas de
   convite; duas linhas por pessoa inflariam o denominador da adesão e a taxa
   cairia sozinha a cada correção de distribuição.

3. **A resposta não diz POR QUE alguém não foi reemitido.** Quem opera o RH já
   tem o pareamento matrícula-link no CSV e já podia descobrir quem respondeu
   abrindo cada link. A rota não pode transformar isso numa consulta em lote
   com resposta pronta.
"""

from __future__ import annotations

import ast
import io
import unittest
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
MAIN = io.open(SERVER / "main.py", encoding="utf-8").read()
STORE = io.open(SERVER / "tenant_store.py", encoding="utf-8").read()


def _corpo_da_funcao(fonte: str, nome: str) -> str:
    """O texto de uma função, localizada pela AST e não por regex.

    Procurar `def nome` com regex acha também a menção em comentário, e um
    teste que passa por causa de um comentário é pior do que teste nenhum.
    """
    arvore = ast.parse(fonte)
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            return ast.get_source_segment(fonte, no) or ""
    raise AssertionError(f"funcao {nome!r} nao encontrada")


def _codigo_da_funcao(fonte: str, nome: str) -> str:
    """O corpo da função SEM a docstring.

    Necessário para as asserções negativas. A docstring de
    `nr1_create_invitations` explica o defeito antigo citando `created += 1`
    pelo nome — e é assim que ela deve continuar. Um teste que procurasse a
    string no texto inteiro estaria proibindo a explicação em vez do código.
    """
    arvore = ast.parse(fonte)
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            corpo = list(no.body)
            if (
                corpo
                and isinstance(corpo[0], ast.Expr)
                and isinstance(corpo[0].value, ast.Constant)
                and isinstance(corpo[0].value.value, str)
            ):
                corpo = corpo[1:]
            return "\n".join(
                ast.get_source_segment(fonte, comando) or "" for comando in corpo
            )
    raise AssertionError(f"funcao {nome!r} nao encontrada")


class ReemissaoRespeitaQuemJaRespondeu(unittest.TestCase):
    def test_o_update_exige_convite_pendente(self):
        corpo = _corpo_da_funcao(STORE, "nr1_reissue_invitations")
        self.assertIn("UPDATE assessment_invitations", corpo)
        self.assertIn("status = 'pending'", corpo)

    def test_nao_insere_linha_nova(self):
        # Duas linhas para a mesma pessoa inflariam `invited`, e a UNIQUE
        # (campaign_id, subject_pseudonym) recusaria a segunda de qualquer modo.
        codigo = _codigo_da_funcao(STORE, "nr1_reissue_invitations")
        self.assertNotIn("INSERT INTO assessment_invitations", codigo)

    def test_devolve_quem_foi_trocado_e_nao_uma_contagem(self):
        # A contagem cega foi o defeito da emissao: `created += 1` a cada
        # iteracao devolvia o tamanho da lista enviada, e a tela exibia link
        # para quem nunca teve um gravado.
        corpo = _corpo_da_funcao(STORE, "nr1_reissue_invitations")
        self.assertIn("RETURNING subject_pseudonym", corpo)


class ReemissaoNaoVirouConsultaDeQuemRespondeu(unittest.TestCase):
    def test_a_rota_limita_o_lote(self):
        corpo = _corpo_da_funcao(MAIN, "reissue_nr1_invitations")
        self.assertIn("> 50", corpo)

    def test_a_resposta_nao_explica_o_motivo(self):
        # "sem_convite_pendente" cobre quem ja respondeu E quem nunca foi
        # convidado. Nomear a causa entregaria a relacao de quem respondeu.
        codigo = _codigo_da_funcao(MAIN, "reissue_nr1_invitations")
        self.assertIn("sem_convite_pendente", codigo)
        for vazamento in ("ja_respondeu", "already_responded", "responded"):
            self.assertNotIn(f'"{vazamento}"', codigo)

    def test_toda_reemissao_vira_evento_de_auditoria(self):
        corpo = _corpo_da_funcao(MAIN, "reissue_nr1_invitations")
        self.assertIn("nr1.invitation.reissue", corpo)

    def test_e_rota_propria_e_nao_opcao_da_emissao(self):
        # Como o efeito e destrutivo — o link anterior morre —, precisa de um
        # ato deliberado com nome proprio, e nao de uma caixa marcada por
        # engano no meio do fluxo normal de distribuicao.
        self.assertIn("/invitations/reissue", MAIN)
        emissao = _codigo_da_funcao(MAIN, "create_nr1_invitations")
        self.assertNotIn("reissue", emissao)


class ConviteRevogadoNaoEConvidado(unittest.TestCase):
    def test_o_denominador_da_adesao_ignora_revogado(self):
        # Sem isto, cada correcao de distribuicao derrubaria a taxa de adesao
        # sem que ninguem tivesse deixado de responder.
        corpo = _corpo_da_funcao(STORE, "nr1_campaign_progress")
        self.assertIn("invitation.status <> 'revoked'", corpo)


class EmissaoSoDevolveLinkQueExiste(unittest.TestCase):
    def test_os_links_sao_filtrados_pelos_gravados(self):
        corpo = _corpo_da_funcao(MAIN, "create_nr1_invitations")
        self.assertIn("already_invited", corpo)
        self.assertIn("gravados", corpo)

    def test_a_store_devolve_os_pseudonimos_gravados(self):
        codigo = _codigo_da_funcao(STORE, "nr1_create_invitations")
        self.assertIn("RETURNING subject_pseudonym", codigo)
        self.assertNotIn("created += 1", codigo)


if __name__ == "__main__":
    unittest.main()
