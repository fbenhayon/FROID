"""Achados da auditoria do modulo NR-1, travados como teste.

Cada classe aqui corresponde a um defeito encontrado lendo o codigo com a
pergunta "o que este numero significa se o dado vier diferente do esperado".
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

MIGRATIONS = SERVER_DIR / "migrations"


class CompletudeDaRespostaTests(unittest.TestCase):
    """Uma resposta quase vazia nao e um respondente.

    froid_nr1_submit_response aceita o envio quando ao menos UM item e valido —
    decisao certa na hora de gravar, porque descartar o que a pessoa respondeu
    seria pior. Mas essa resposta conta como respondente inteiro para o piso de
    cinquenta da campanha, e o piso deixaria de significar "cinquenta pessoas
    avaliaram este trabalho".

    Por dimensao o dado ja estava protegido: o agrupamento e por resposta e
    dimensao, entao quem nao respondeu nada de uma dimensao nao entra na coorte
    dela. O que faltava era enxergar a diferenca.
    """

    def setUp(self):
        self.sql = (MIGRATIONS / "023_response_completeness.sql").read_text(
            encoding="utf-8"
        )

    def test_existe_criterio_de_cobertura_documentado(self):
        self.assertIn("froid_nr1_min_response_coverage", self.sql)
        self.assertIn("0.50", self.sql)

    def test_a_funcao_compara_dimensoes_cobertas_com_as_do_instrumento(self):
        self.assertIn("froid_nr1_response_is_substantive", self.sql)
        self.assertIn("count(DISTINCT item.dimension_id)", self.sql)

    def test_instrumento_sem_dimensao_nao_aprova_por_divisao_degenerada(self):
        # Sem esta guarda, um instrumento sem itens tornaria toda resposta
        # "substantiva" por comparar zero com zero.
        self.assertIn("WHEN (SELECT n FROM totais) = 0 THEN FALSE", self.sql)

    def test_o_progresso_expoe_respostas_parciais(self):
        fonte = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
        inicio = fonte.index("def nr1_campaign_progress")
        # Ate o proximo metodo, e nao uma janela de N caracteres: a primeira
        # versao deste teste cortava antes do campo que queria verificar e
        # reprovava codigo correto.
        fim = fonte.index("    def ", inicio + 10)
        trecho = fonte[inicio:fim]
        self.assertIn("froid_nr1_response_is_substantive", trecho)
        self.assertIn("partial_responses", trecho)
        self.assertIn("substantive_responses", trecho)

    def test_as_funcoes_novas_tem_grant_e_revoke(self):
        self.assertIn("REVOKE ALL ON FUNCTION froid_nr1_min_response_coverage", self.sql)
        self.assertIn("GRANT EXECUTE ON FUNCTION froid_nr1_response_is_substantive", self.sql)


class DiferenciacaoTests(unittest.TestCase):
    """O que a auditoria verificou e encontrou correto.

    A suspeita era de supressao complementar faltando: com o total da campanha
    visivel e os recortes acima do piso publicados, subtrair revelaria o
    recorte suprimido.

    Revelaria a CONTAGEM dele, nao as respostas — e so porque nao existe
    nenhuma linha agregada que misture unidades. Se o painel algum dia passar a
    devolver uma media de campanha ao lado das medias por unidade, a media do
    recorte suprimido passa a ser derivavel por subtracao ponderada. Este teste
    existe para que essa linha nao apareca sem que alguem perceba.
    """

    def test_o_agregado_agrupa_por_unidade_e_nao_produz_total(self):
        sql = (MIGRATIONS / "014_nr1_audit_hardening.sql").read_text(encoding="utf-8")
        inicio = sql.index("RETURN QUERY")
        corpo = sql[inicio:]
        self.assertIn("GROUP BY scored.response_unit_id", corpo)
        self.assertIn("HAVING count(*) >= effective_cut_floor", corpo)

    def test_o_painel_nao_calcula_media_de_campanha(self):
        fonte = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        i = fonte.index("async def read_nr1_panel")
        trecho = fonte[i:i + 4000]
        # O painel devolve linhas por recorte e contagens de participacao.
        # Qualquer media agregada aqui reabriria a diferenciacao.
        self.assertNotIn("mean(", trecho)
        self.assertNotIn("campaign_mean", trecho)
        self.assertNotIn("overall_mean", trecho)

    def test_resultado_so_sai_com_a_campanha_encerrada(self):
        sql = (MIGRATIONS / "014_nr1_audit_hardening.sql").read_text(encoding="utf-8")
        self.assertIn("IF campaign_status <> 'closed' THEN", sql)


class PisoDaCampanhaTests(unittest.TestCase):
    """O piso passa a contar respostas substantivas.

    A migration 024 reproduz a funcao da 014 por copia, com uma unica
    alteracao. Este teste confere que a copia continua sendo copia: se alguem
    editar a 024 a mao e divergir da 014 em qualquer outro ponto, a diferenca
    aparece aqui em vez de aparecer num painel que grada errado.
    """

    def setUp(self):
        self.antiga = (MIGRATIONS / "014_nr1_audit_hardening.sql").read_text(
            encoding="utf-8"
        )
        self.nova = (MIGRATIONS / "024_campaign_floor_substantive.sql").read_text(
            encoding="utf-8"
        )

    def _corpo(self, texto: str) -> list:
        ini = texto.index("CREATE OR REPLACE FUNCTION froid_nr1_dimension_scores")
        fim = texto.index("$$;", texto.index("END;\n$$;", ini)) + 3
        # Ignora comentarios: eles sao a parte que MUDA de proposito.
        return [
            linha.rstrip()
            for linha in texto[ini:fim].splitlines()
            if linha.strip() and not linha.strip().startswith("--")
        ]

    def test_a_unica_diferenca_e_o_contador_do_piso(self):
        antiga = self._corpo(self.antiga)
        nova = self._corpo(self.nova)
        import difflib

        diff = [
            linha for linha in difflib.unified_diff(antiga, nova, lineterm="", n=0)
            if linha.startswith(("+", "-")) and not linha.startswith(("+++", "---"))
        ]
        self.assertEqual(len(diff), 3, "\n".join(diff))
        self.assertIn("AND response.completed;", diff[0])
        self.assertIn("froid_nr1_response_is_substantive", "\n".join(diff))

    def test_o_piso_usa_a_funcao_de_completude(self):
        self.assertIn(
            "AND froid_nr1_response_is_substantive(response.id);", self.nova
        )

    def test_a_funcao_continua_revogada_do_publico_e_concedida_ao_runtime(self):
        # CREATE OR REPLACE nao preserva grants de uma definicao anterior de
        # forma obvia; declarar de novo evita depender disso.
        self.assertIn(
            "REVOKE ALL ON FUNCTION froid_nr1_dimension_scores(uuid, integer) "
            "FROM PUBLIC", self.nova
        )
        self.assertIn("GRANT EXECUTE ON FUNCTION froid_nr1_dimension_scores", self.nova)

    def test_a_ordem_das_travas_e_preservada(self):
        # Organizacao, associacao ativa, campanha encerrada, piso. Nessa ordem:
        # trocar a ultima pelas primeiras vazaria a existencia da campanha.
        corpo = self.nova
        self.assertLess(
            corpo.index("froid_current_organization_id()"),
            corpo.index("campaign_status <> 'closed'"),
        )
        self.assertLess(
            corpo.index("campaign_status <> 'closed'"),
            corpo.index("campaign_total < froid_nr1_min_cohort_total()"),
        )

if __name__ == "__main__":
    unittest.main()
