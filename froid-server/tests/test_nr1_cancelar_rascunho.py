"""Cancelar um rascunho vazio — a saida que estava desenhada e nao tinha camada.

Ate 09/09/2026 campanha criada por engano ficava para sempre. Nao havia rota que
a removesse, e o FROID Explica respondia "nao se exclui" — doutrina correta,
porque o inventario de riscos tem guarda de vinte anos e apagar a campanha que o
originou apagaria a evidencia que defende a empresa. So que ela nao alcanca o
caso que de fato acontece: o rascunho duplicado, sem convite nenhum, sem
resposta nenhuma, que nenhum inventario referencia.

O estado 'cancelled' e valido em assessment_campaigns desde a migration 010 e
nenhum caminho de codigo chegava nele (padrao 2.1: a peca existe, esta correta, e
nada a consome).

Os dois portoes — so rascunho, so sem convite — sao afirmados NO SQL e nao no
endpoint: portao em Python vale para quem passa por ele, portao no WHERE vale
para todos. E ha um teste sobre a coincidencia que sustenta o NOT EXISTS: ele
roda sob a mesma RLS que esconde convites, entao seria vacuamente verdadeiro
para um papel fora da policy.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import tenant_access  # noqa: E402

MIGRACAO_010 = (
    SERVER_DIR / "migrations" / "010_nr1_psychosocial_compliance.sql"
).read_text(encoding="utf-8")
STORE_FONTE = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
MAIN_FONTE = (SERVER_DIR / "main.py").read_text(encoding="utf-8")

STORE_ARVORE = ast.parse(STORE_FONTE)
MAIN_ARVORE = ast.parse(MAIN_FONTE)


def funcao(arvore: ast.AST, nome: str) -> ast.AST:
    """A definicao com este nome, em qualquer profundidade.

    Recorte pelo parser, nunca por linha ou por janela de caracteres: recorte
    por janela ja quebrou duas vezes nesta casa por crescimento de comentario.
    """
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            return no
    raise AssertionError(f"funcao {nome} nao existe")


def sql_de(no: ast.AST) -> str:
    """Todo literal de texto dentro da funcao, junto e sem espaco duplo."""
    partes = [
        n.value
        for n in ast.walk(no)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]
    return re.sub(r"\s+", " ", " ".join(partes))


def constante(nome: str):
    """O valor de uma atribuicao de modulo, avaliado como literal."""
    for no in STORE_ARVORE.body:
        alvos = []
        if isinstance(no, ast.Assign):
            alvos = [a.id for a in no.targets if isinstance(a, ast.Name)]
        elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
            alvos = [no.target.id]
        if nome in alvos and no.value is not None:
            return ast.literal_eval(no.value)
    raise AssertionError(f"constante {nome} nao existe em tenant_store.py")


class CancelarNaoEApagar(unittest.TestCase):
    """So o rascunho vazio sai da frente, e a linha continua no banco."""

    def setUp(self):
        self.no = funcao(STORE_ARVORE, "nr1_cancel_campaign")
        self.sql = sql_de(self.no)

    def test_e_um_update_de_estado_e_nunca_um_delete(self):
        self.assertIn("UPDATE assessment_campaigns", self.sql)
        self.assertIn("SET status='cancelled'", self.sql)
        self.assertNotIn("DELETE", self.sql.upper())

    def test_so_alcanca_rascunho(self):
        # Campanha aberta pode ja ter resposta; encerrada sustenta o
        # inventario, que tem guarda de vinte anos.
        self.assertIn("status='draft'", self.sql)

    def test_so_alcanca_campanha_sem_nenhum_convite(self):
        # Rascunho com convite tem link distribuido: ele nao abre hoje, mas
        # revive no instante em que a coleta abrir. Cancelar o mataria em
        # silencio, e os links sao mostrados uma unica vez.
        self.assertIn("NOT EXISTS", self.sql)
        self.assertIn("FROM assessment_invitations invitation", self.sql)

    def test_os_dois_portoes_estao_no_SQL_e_nao_no_endpoint(self):
        # O endpoint e um chamador entre os possiveis. Portao em Python vale
        # para quem passa por ele; portao no WHERE vale para todos.
        endpoint = ast.unparse(funcao(MAIN_ARVORE, "cancel_nr1_campaign"))
        self.assertNotIn("draft", endpoint.split('"""')[-1])

    def test_recusa_devolve_conflito_e_diz_o_motivo(self):
        endpoint = ast.unparse(funcao(MAIN_ARVORE, "cancel_nr1_campaign"))
        self.assertIn("status_code=409", endpoint)
        self.assertIn("rascunho", endpoint)
        self.assertIn("convite", endpoint)

    def test_o_papel_que_cancela_enxerga_os_convites(self):
        """O NOT EXISTS roda sob a mesma RLS que esconde convites.

        Para um papel fora da policy ele seria vacuamente verdadeiro, e o
        rascunho com convites seria cancelado como se estivesse vazio. Hoje
        isso nao acontece porque `nr1.campaigns.manage` mora so em
        compliance_manager, que esta na policy — mas essa coincidencia nao
        estava escrita em lugar nenhum, e conceder a permissao a um papel novo
        quebraria a guarda sem quebrar teste nenhum.
        """
        leitores = set(constante("NR1_INVITATION_READER_ROLES"))
        gerentes = {
            papel
            for papel in tenant_access.VALID_ROLES
            if "nr1.campaigns.manage" in tenant_access.ROLE_PERMISSIONS.get(
                papel, frozenset()
            )
        }
        self.assertTrue(gerentes, "ninguem gerencia campanha")
        self.assertLessEqual(
            gerentes,
            leitores,
            "papel que cancela campanha mas nao enxerga convite: o NOT EXISTS "
            "do cancelamento passaria a valer sempre",
        )


class OEstadoCanceladoJaExistiaNoBanco(unittest.TestCase):
    """A saida estava desenhada e nao tinha camada acima (padrao 2.1)."""

    def test_a_migration_010_ja_aceitava_cancelled(self):
        bloco = MIGRACAO_010[MIGRACAO_010.index("CREATE TABLE IF NOT EXISTS assessment_campaigns") :]
        bloco = bloco[: bloco.index(");")]
        self.assertIn("'cancelled'", bloco)

    def test_agora_existe_quem_o_escreva(self):
        self.assertIn("SET status='cancelled'", sql_de(funcao(STORE_ARVORE, "nr1_cancel_campaign")))

    def test_a_rota_esta_publicada_e_exige_a_permissao_de_campanha(self):
        self.assertIn(
            '@app.post("/api/organizations/{organization_id}/nr1/campaigns/'
            '{campaign_id}/cancel")',
            MAIN_FONTE,
        )
        endpoint = ast.unparse(funcao(MAIN_ARVORE, "cancel_nr1_campaign"))
        self.assertIn("_require_enterprise_context", endpoint)
        self.assertIn("nr1.campaigns.manage", endpoint)

    def test_o_cancelamento_e_auditado(self):
        endpoint = ast.unparse(funcao(MAIN_ARVORE, "cancel_nr1_campaign"))
        self.assertIn("nr1.campaign.cancel", endpoint)


if __name__ == "__main__":
    unittest.main()
