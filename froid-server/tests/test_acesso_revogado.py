"""O login recusa quem teve acesso e perdeu — e só esse.

Por que este teste existe:

O banco já trazia o vocabulário de suspensão desde a primeira migração —
`users.status` aceita `disabled`, `organizations.status` aceita `suspended`, e
`organization_memberships.status` aceita `revoked`. Nenhuma linha de código lia
qualquer um dos três. Quem tinha o vínculo revogado autenticava normalmente e
caía numa tela sem organização alguma, que lê como defeito do sistema e não
como decisão de quem opera.

É a sexta vez que este módulo produz uma peça correta que ninguém consome. O
teste existe para que não haja sétima.

O risco na direção oposta é maior e menos óbvio: bloquear "quem não tem
organização" trancaria para fora todo profissional autônomo, que autentica pelo
cadastro próprio e nunca teve vínculo nenhum. Por isso a regra é estreita — tem
de haver vínculo registrado e nenhum ativo — e por isso metade dos casos abaixo
verifica quem NÃO deve ser recusado.
"""

from __future__ import annotations

import ast
import io
import os
import sys

import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = io.open(os.path.join(RAIZ, "main.py"), encoding="utf-8").read()
STORE = io.open(os.path.join(RAIZ, "tenant_store.py"), encoding="utf-8").read()


def _sem_comentarios(fonte: str) -> str:
    """Comentários e docstrings citam o defeito; asserção negativa os veria."""
    arvore = ast.parse(fonte)
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            corpo = getattr(no, "body", [])
            if (
                corpo
                and isinstance(corpo[0], ast.Expr)
                and isinstance(corpo[0].value, ast.Constant)
                and isinstance(corpo[0].value.value, str)
            ):
                corpo.pop(0)
    return ast.unparse(arvore)


class TestAMensagem(unittest.TestCase):
    def test_e_exatamente_a_que_o_fabio_pediu(self):
        assert "Acesso restrito, entre em contato com froid@froid.com.br" in MAIN
        assert "para maiores detalhes" in MAIN

    def test_a_recusa_usa_403_e_nao_401(self):
        # 401 faria o front pedir credencial de novo, como se a senha estivesse
        # errada. O acesso foi retirado; a credencial está certa.
        corpo = MAIN[MAIN.index("def _guard_acesso_revogado") : MAIN.index("def _issue_session")]
        assert "status_code=403" in corpo
        assert "ACESSO_REVOGADO" in corpo


class TestAGuardaEChamada(unittest.TestCase):
    def test_issue_session_chama_a_guarda(self):
        # Rota sem leitor é o padrão que este módulo já repetiu cinco vezes.
        corpo = MAIN[MAIN.index("def _issue_session") :][:900]
        assert "_guard_acesso_revogado(session_user)" in corpo

    def test_a_guarda_vem_depois_dos_contextos(self):
        # Antes de _attach_tenant_contexts a lista ainda não existe, e a
        # guarda recusaria todo mundo.
        corpo = MAIN[MAIN.index("def _issue_session") :][:900]
        assert corpo.index("_attach_tenant_contexts") < corpo.index("_guard_acesso_revogado")


class TestQuemNaoPodeSerBloqueado(unittest.TestCase):
    def test_quem_tem_organizacao_ativa_passa_direto(self):
        corpo = _sem_comentarios(
            MAIN[MAIN.index("def _guard_acesso_revogado") : MAIN.index("def _issue_session")]
        )
        # `ast.unparse` normaliza aspas para simples, entao asserção com aspas
        # DUPLAS nunca casaria. Este teste nasceu quebrado e ninguém soube:
        # o arquivo usava pytest enquanto a suíte usa unittest, e nunca rodou.
        # Comparação insensível a aspas para não repetir a armadilha.
        normalizado = corpo.replace('"', "'")
        assert "session_user.get('organizations')" in normalizado
        # E o que LIBERA precisa ser contexto real, não a lista crua: contexto
        # sintético (`legacy_fallback`) foi como uma conta revogada passou.
        assert "legacy_fallback" in normalizado
        assert "return" in corpo

    def test_o_autonomo_sem_vinculo_nenhum_nao_e_recusado(self):
        """total == 0 é o profissional autônomo. Tem de entrar."""
        assert "total > 0 and ativos == 0" in STORE

    def test_banco_indisponivel_falha_aberta(self):
        # Postgres fora do ar não pode virar bloqueio de quem tem acesso
        # legítimo — e a sessão sozinha não abre dado nenhum, porque as
        # políticas de leitura continuam valendo.
        corpo = MAIN[MAIN.index("def _guard_acesso_revogado") : MAIN.index("def _issue_session")]
        assert "except Exception" in corpo
        assert corpo.index("except Exception") < corpo.index("if revogado")

    def test_store_desligado_nao_bloqueia(self):
        corpo = MAIN[MAIN.index("def _guard_acesso_revogado") : MAIN.index("def _issue_session")]
        assert "TENANT_STORE.enabled" in corpo


class TestAConsultaOlhaOsTresEstados(unittest.TestCase):
    """Revogar o vínculo, desabilitar a conta e suspender a organização são
    três alavancas diferentes, e as três precisam produzir a mesma recusa."""

    def test_o_filtro_de_ativos_cobre_a_alavanca(self):
        # `pytest.mark.parametrize` virou subTest: este arquivo usava
        # pytest enquanto o resto da suite usa unittest, e por isso nunca
        # rodou na maquina de desenvolvimento — testes do controle de
        # acesso, justamente. Teste que nao roda nao protege nada.
        for condicao in [
            "membership.status = 'active'",
            "user_account.status = 'active'",
            "organization.status = 'active'",
        ]:
            with self.subTest(condicao=condicao):
                corpo = STORE[STORE.index("def access_was_revoked") : STORE.index("def access_contexts")]
                assert condicao in corpo

    def test_conta_o_total_sem_filtrar(self):
        # O total precisa contar TODOS os vínculos, inclusive os revogados —
        # é ele que separa "nunca teve" de "teve e perdeu".
        corpo = STORE[STORE.index("def access_was_revoked") : STORE.index("def access_contexts")]
        assert "count(*) AS total" in corpo


if __name__ == "__main__":
    unittest.main()
