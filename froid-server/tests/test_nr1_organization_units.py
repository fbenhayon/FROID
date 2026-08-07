"""Estrutura da empresa no NR-1: quem pode criar, e o que a estrutura promete.

organization_units existia desde a migration 010 com esquema, GRANT e politica
de RLS completos — e era so LIDO. Quatro LEFT JOIN, nenhuma insercao. Na pratica
a estrutura de cada cliente entrava no banco a mao.

Estes testes cobrem a camada que faltava, e principalmente a coerencia entre as
duas autorizacoes: a da aplicacao e a do banco. Divergencia entre elas produz um
403 que o banco teria permitido, ou o contrario — e nenhum dos dois aparece em
teste de caminho feliz.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from tenant_access import (  # noqa: E402
    CLINICAL_IDENTIFIED_PERMISSIONS,
    ROLE_PERMISSIONS,
    effective_role_permissions,
)

MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
STORE = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
MIGRATION = (
    SERVER_DIR / "migrations" / "010_nr1_psychosocial_compliance.sql"
).read_text(encoding="utf-8")


def _politica_manage() -> str:
    inicio = MIGRATION.index("CREATE POLICY organization_units_manage")
    return MIGRATION[inicio : MIGRATION.index(";", MIGRATION.index("WITH CHECK", inicio))]


class AutorizacaoCoerenteTests(unittest.TestCase):
    """A aplicacao e o banco precisam nomear os MESMOS papeis."""

    def test_os_papeis_que_gerenciam_sao_os_mesmos_nas_duas_camadas(self):
        politica = _politica_manage()
        no_banco = set(re.findall(r"'(owner|administrator|compliance_manager)'", politica))
        na_aplicacao = {
            papel
            for papel, permissoes in ROLE_PERMISSIONS.items()
            if "nr1.unit.manage" in permissoes
        }
        self.assertEqual(no_banco, na_aplicacao, f"banco={sorted(no_banco)} app={sorted(na_aplicacao)}")

    def test_o_dono_da_empresa_consegue_cadastrar_a_propria_estrutura(self):
        # Quem chega pelo OAuth e cria a organizacao e o owner dela. Sem esta
        # permissao o cadastro guiado nao sai do primeiro passo.
        self.assertIn("nr1.unit.manage", ROLE_PERMISSIONS["owner"])
        self.assertIn("nr1.unit.list", ROLE_PERMISSIONS["owner"])

    def test_quem_so_acompanha_le_mas_nao_altera(self):
        oh = ROLE_PERMISSIONS["occupational_health"]
        self.assertIn("nr1.unit.list", oh)
        self.assertNotIn("nr1.unit.manage", oh)

    def test_profissional_clinico_nao_toca_na_estrutura_da_empresa(self):
        for papel in ("professional", "supervisor", "auditor"):
            permissoes = ROLE_PERMISSIONS[papel]
            self.assertNotIn("nr1.unit.manage", permissoes, papel)
            self.assertNotIn("nr1.unit.list", permissoes, papel)

    def test_estrutura_nao_e_dado_clinico_e_sobrevive_ao_estreitamento(self):
        """Numa organizacao 'enterprise' o empregador perde o acesso clinico.

        Unidade e setor descrevem o AMBIENTE de trabalho, nao uma pessoa — entao
        precisam continuar valendo depois do corte. Se algum dia entrarem na
        lista de permissoes clinicas, o empregador deixa de conseguir descrever
        a propria empresa.
        """
        self.assertNotIn("nr1.unit.manage", CLINICAL_IDENTIFIED_PERMISSIONS)
        efetivas = effective_role_permissions("owner", "enterprise")
        self.assertIn("nr1.unit.manage", efetivas)
        # E o corte clinico continua fazendo o que promete.
        self.assertNotIn("reports.read_all", efetivas)


class RegrasDeEstruturaTests(unittest.TestCase):
    """A hierarquia e de dois niveis por exigencia da norma, nao por atalho."""

    def _corpo(self, funcao: str) -> str:
        inicio = STORE.index(f"def {funcao}(")
        return STORE[inicio : STORE.index("\n    def ", inicio + 10)]

    def test_setor_exige_estabelecimento(self):
        corpo = self._corpo("nr1_create_unit")
        self.assertIn('unit_type == "sector" and not parent_unit_id', corpo)

    def test_estabelecimento_nao_tem_pai(self):
        corpo = self._corpo("nr1_create_unit")
        self.assertIn('unit_type == "site" and parent_unit_id', corpo)

    def test_o_pai_precisa_ser_da_mesma_organizacao(self):
        # A RLS ja filtra a leitura, mas a checagem explicita transforma um
        # vinculo cruzado em erro na hora, e nao em linha orfa depois.
        corpo = self._corpo("nr1_create_unit")
        self.assertIn("AND organization_id = %s", corpo)
        self.assertIn("unidade pai inexistente", corpo)

    def test_o_pai_de_um_setor_precisa_ser_estabelecimento(self):
        corpo = self._corpo("nr1_create_unit")
        self.assertIn('pai[0] != "site"', corpo)

    def test_nao_existe_exclusao_de_unidade(self):
        """1.5.7.3.3.1 manda guardar o inventario por vinte anos.

        O inventario aponta para a unidade. Apagar a linha deixaria o registro
        antigo sem referencia — por isso arquivar e a unica remocao, e por isso
        a propria migration usa ON DELETE RESTRICT.
        """
        self.assertNotIn("DELETE FROM organization_units", STORE)
        self.assertIn("ON DELETE RESTRICT", MIGRATION)
        corpo = self._corpo("nr1_update_unit")
        self.assertIn('"active", "archived"', corpo)

    def test_arquivar_estabelecimento_com_setores_ativos_e_recusado(self):
        corpo = self._corpo("nr1_update_unit")
        self.assertIn("parent_unit_id = %s AND status = 'active'", corpo)
        self.assertIn("arquive ou mova os setores", corpo)

    def test_efetivo_nunca_fica_negativo(self):
        corpo = self._corpo("nr1_create_unit")
        self.assertIn("max(0, int(headcount))", corpo)


class EndpointsTests(unittest.TestCase):
    def _rota(self, decorador: str) -> str:
        i = MAIN.index(decorador)
        j = MAIN.find("\n@app.", i + len(decorador))
        return MAIN[i:] if j == -1 else MAIN[i:j]

    def test_listar_exige_a_permissao_de_leitura(self):
        rota = self._rota('@app.get("/api/organizations/{organization_id}/nr1/units")')
        self.assertIn('"nr1.unit.list"', rota)

    def test_criar_e_alterar_exigem_a_permissao_de_gestao(self):
        for decorador in (
            '@app.post("/api/organizations/{organization_id}/nr1/units"',
            '@app.patch("/api/organizations/{organization_id}/nr1/units/{unit_id}")',
        ):
            rota = self._rota(decorador)
            self.assertIn('"nr1.unit.manage"', rota, decorador)

    def test_regra_de_estrutura_violada_vira_400_e_nao_500(self):
        rota = self._rota('@app.post("/api/organizations/{organization_id}/nr1/units"')
        self.assertIn("except ValueError as exc:", rota)
        self.assertIn("status_code=400", rota)

    def test_a_listagem_devolve_o_efetivo_por_estabelecimento(self):
        # O piso de anonimato e propriedade da UNIDADE: uma matriz grande nao
        # salva a filial pequena, e a tela precisa avisar antes da campanha.
        rota = self._rota('@app.get("/api/organizations/{organization_id}/nr1/units")')
        self.assertIn("headcount_by_site", rota)


if __name__ == "__main__":
    unittest.main()
