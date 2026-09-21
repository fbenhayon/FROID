"""Autoria antes de recorte — a regra, e nao a ocorrencia que eu tinha visto.

DECISAO DO DONO DO PRODUTO, 20/09/2026.

O caso: num atendimento real, o profissional foi barrado da propria consulta
porque a organizacao ATIVA do login dele nao batia com a organizacao carimbada
na sessao. A conta dele tem mais de uma organizacao no PostgreSQL, e a ativa e
escolhida pelo servidor quando a anterior nao esta na lista — ou seja, muda
entre logins sem ninguem pedir. E o painel clinico nao tem seletor de
organizacao (retirado de proposito), entao nao havia acao possivel na tela.

A REGRA

Onde a AUTORIA da sessao ja esta provada, o recorte por organizacao so alcanca
o proprio autor: ele nao protege ninguem de ninguem, e o que produz e um
profissional trancado para fora do que e dele. Nesses pontos ele nao recusa.

Onde a autoria NAO esta provada, o recorte continua sendo a guarda — e a
correcao e acrescentar a pergunta que falta, nunca remover a que existe.

POR QUE ESTE ARQUIVO EXISTE SEPARADO

Porque a primeira correcao mexeu nas duas rotas de WebSocket e parou ali. O
defeito 2.8 desta casa e exatamente esse: corrigir o lugar, e nao a regra. Esta
varredura pergunta a mesma coisa a TODOS os pontos onde `_session_matches_context`
decide, e obriga cada um a se declarar — ou passa a autoria na frente, ou esta
listado aqui com o motivo de nao precisar.

Do lado da leitura a regra ja existia antes de tudo isto, em
`_report_within_context`: "a autoria vence a organizacao corrente [...], o
prontuario e de quem o escreveu, e trocar de organizacao nao transfere a
autoria de nada". O que faltava era aplica-la ao resto.
"""

import re
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")


def _corpo_da_funcao(nome: str) -> str:
    """Recorta pelo nome da definicao, nunca por contagem de caracteres."""
    padrao = rf"\n(?:async )?def {re.escape(nome)}\(.*?(?=\n(?:async )?def |\n@app\.|\Z)"
    achado = re.search(padrao, MAIN, re.DOTALL)
    assert achado, f"funcao {nome} nao encontrada"
    return achado.group(0)


class AutoriaVenceORecorteTests(unittest.TestCase):
    def test_arquivar_o_relatorio_aceita_o_autor_da_sessao(self):
        # O pior momento possivel: a consulta acabou, o relatorio esta pronto, e
        # o 409 nao grava. Tentar de novo dava o mesmo 409 — nada mudava.
        corpo = _corpo_da_funcao("save_session_report")
        self.assertIn("SESSION_OWNERS.get(session_id)", corpo)
        self.assertIn("e_o_autor_da_sessao", corpo)
        self.assertIn(
            "if not e_o_autor_da_sessao and not _session_matches_context(session_id, context):",
            corpo,
        )

    def test_arquivar_continua_recusando_quem_nao_criou(self):
        # A correcao ACRESCENTA uma pergunta; nao remove a que ja existia. Quem
        # nao e o autor continua exatamente sob a regra de antes.
        corpo = _corpo_da_funcao("save_session_report")
        self.assertIn("sessão pertence a outra organização", corpo)
        self.assertIn("status_code=409", corpo)

    def test_sessao_sem_dono_registrado_nao_vira_passe_livre(self):
        # `SESSION_OWNERS.get` devolve "" para sessao anterior a este controle, e
        # "" nao pode casar com e-mail nenhum — senao qualquer conta gravaria
        # relatorio em qualquer sessao antiga.
        corpo = _corpo_da_funcao("save_session_report")
        self.assertIn("and bool(owner_email)", corpo)

    def test_a_configuracao_da_sessao_nao_recorta_o_proprio_autor(self):
        # Aqui a autoria ja era exigida no MESMO `if`, entao o recorte so
        # alcancava o autor — e devolvia 404 "configuracao da sessao nao
        # encontrada" sobre uma sessao que existe e e dele.
        corpo = _corpo_da_funcao("get_professional_session_configuration")
        self.assertIn('_normalize_email(item.get("professional_email") or "")', corpo)
        self.assertNotIn("_session_matches_context", corpo)

    def test_o_portao_de_acesso_continua_de_pe_na_configuracao(self):
        # So o valor de retorno perdeu leitor. A chamada e o portao e levanta
        # sozinha quando recusa — remove-la abriria a rota.
        corpo = _corpo_da_funcao("get_professional_session_configuration")
        self.assertIn("_require_professional_feature_access(request)", corpo)
        self.assertIn("_require_current_user(request)", corpo)

    def test_todo_ponto_de_recorte_esta_declarado(self):
        """A varredura que impede "corrigi o lugar, e nao a regra".

        Todo uso de `_session_matches_context` precisa estar nesta tabela, com o
        motivo. Um uso novo quebra o teste, e quem o escrever tem de responder a
        pergunta: isto pode trancar alguem para fora do que e dele?
        """
        declarados = {
            "websocket_fusion": "so registra a divergencia; a autoria ja foi provada acima",
            "websocket_rtc_signaling": "idem, e o ramo do paciente recorta por convite",
            "create_session_invite": "a sessao NASCE aqui; nao ha autoria anterior a provar",
            "save_session_report": "a autoria passa na frente desde 20/09/2026",
        }
        # `(?<!def )` deixa a propria definicao de fora: sem isso ela conta como
        # uso e e atribuida a funcao que a precede no arquivo, acusando um ponto
        # de recorte que nao existe.
        usos = set()
        for achado in re.finditer(r"(?<!def )_session_matches_context\(", MAIN):
            trecho = MAIN[:achado.start()]
            definicoes = re.findall(r"\n(?:async )?def (\w+)\(", trecho)
            if definicoes:
                usos.add(definicoes[-1])
        self.assertTrue(usos, "a varredura nao encontrou uso nenhum")

        nao_declarados = sorted(usos - set(declarados))
        self.assertEqual(
            nao_declarados,
            [],
            "recorte por organizacao em funcao nao declarada: "
            f"{nao_declarados}. Responda se ela pode trancar alguem para fora "
            "do que e dele, e declare-a aqui com o motivo.",
        )


if __name__ == "__main__":
    unittest.main()
