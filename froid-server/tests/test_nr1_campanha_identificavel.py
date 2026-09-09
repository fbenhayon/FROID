"""A lista de campanhas passa a identificar cada uma, e a contar convites.

Em 09/09/2026 um cliente criou quatro campanhas onde deviam existir duas — dois
pares de titulos identicos — e emitiu convites na errada. Nao havia como ele
acertar: a lista devolvia titulo, estado e janela, e nada mais. Nem a hora de
criacao, nem quantos convites cada campanha ja tinha. Campanha nao aceita edicao
nem renomeacao, entao o engano ficou.

O que se afirma aqui e a FORMA do SQL e, sobretudo, uma distincao: a contagem de
convites nunca pode virar zero por falta de permissao. A policy de RLS de
assessment_invitations nomeia tres papeis; `occupational_health` lista campanhas
e nao esta entre eles. Um COUNT sob RLS devolveria 0 para ele, e "nenhum convite
emitido" impresso sobre uma campanha em plena coleta seria medida inventada, nao
medida ausente — a diferenca que a regra 1.1 do rigor de engenharia existe para
guardar.

Nao ha banco nesta suite: o comportamento real das policies contra um Postgres
de verdade nao e exercitado. O que se compara e o espelho entre a lista de
papeis em Python e a policy na migration, que e justamente o par que diverge em
silencio (padrao 2.7).
"""

import ast
import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

MIGRACAO_010 = (
    SERVER_DIR / "migrations" / "010_nr1_psychosocial_compliance.sql"
).read_text(encoding="utf-8")
STORE_FONTE = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")

STORE_ARVORE = ast.parse(STORE_FONTE)


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


class ListaIdentificaCadaCampanha(unittest.TestCase):
    """Titulo e estado nao bastam quando duas campanhas se chamam igual."""

    def setUp(self):
        self.no = funcao(STORE_ARVORE, "nr1_list_campaigns")
        self.sql = sql_de(self.no)

    def test_seleciona_o_que_distingue_duas_homonimas(self):
        for coluna in (
            "campaign.reference_period",
            "campaign.target_headcount",
            "campaign.opens_at",
            "campaign.created_at",
        ):
            self.assertIn(coluna, self.sql, coluna)

    def test_ordena_com_desempate_estavel(self):
        # Duas campanhas criadas no mesmo dia nascem com a janela sugerida
        # IGUAL — o formulario a preenche sozinho. Ordenar so por opens_at
        # deixava a ordem das duas ao criterio do plano de execucao, e a lista
        # trocava de ordem entre dois carregamentos sem nada ter mudado.
        self.assertIn(
            "ORDER BY campaign.opens_at DESC, campaign.created_at DESC", self.sql
        )

    def test_devolve_os_campos_que_a_tela_le(self):
        chaves = {
            n.value
            for n in ast.walk(self.no)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        }
        for chave in ("created_at", "invitations", "reference_period", "unit_name"):
            self.assertIn(chave, chaves, chave)


class ContagemDeConvitesNaoInventaZero(unittest.TestCase):
    """A diferenca entre 'nenhum convite' e 'nao pude contar'."""

    def setUp(self):
        self.sql = sql_de(funcao(STORE_ARVORE, "nr1_list_campaigns"))

    def test_a_contagem_e_condicionada_ao_papel(self):
        self.assertIn("CASE WHEN froid_has_role(", self.sql)
        self.assertIn(
            "SELECT count(*) FROM assessment_invitations invitation", self.sql
        )

    def test_o_case_nao_tem_else(self):
        # CASE sem ELSE devolve NULL. Um ELSE 0 aqui — que parece defensivo —
        # publicaria "nenhum convite emitido" sobre campanha em coleta, para
        # todo papel fora da policy. Ausencia de apuracao nao e zero.
        trecho = self.sql[self.sql.index("CASE WHEN froid_has_role(") :]
        trecho = trecho[: trecho.index(" END")]
        self.assertNotIn("ELSE", trecho.upper())

    def test_o_none_sobrevive_ate_o_dicionario(self):
        fonte = ast.unparse(funcao(STORE_ARVORE, "nr1_list_campaigns"))
        self.assertIn("'invitations': None if row[10] is None else int(row[10])", fonte)
        # int(row[10] or 0) e a forma que apagaria a distincao — e e exatamente
        # a forma que se escreve sem pensar.
        self.assertNotIn("int(row[10] or 0)", fonte)

    def test_a_lista_de_papeis_espelha_a_policy_da_migration(self):
        # Copia de uma regra que vive no SQL. Se a policy for ESTREITADA e esta
        # tupla nao acompanhar, o COUNT volta a 0 sob RLS e a tela afirma o que
        # nao apurou — a direcao perigosa da divergencia.
        bloco = MIGRACAO_010[
            MIGRACAO_010.index("CREATE POLICY assessment_invitations_manage") :
        ]
        bloco = bloco[: bloco.index("WITH CHECK")]
        papeis_sql = re.search(
            r"froid_has_role\(ARRAY\[([^\]]+)\]", bloco, re.S
        )
        self.assertIsNotNone(papeis_sql, "policy sem froid_has_role")
        na_policy = tuple(
            sorted(re.findall(r"'([a-z_]+)'", papeis_sql.group(1)))
        )
        self.assertEqual(
            na_policy, tuple(sorted(constante("NR1_INVITATION_READER_ROLES")))
        )


if __name__ == "__main__":
    unittest.main()
