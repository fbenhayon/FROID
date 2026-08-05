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


if __name__ == "__main__":
    unittest.main()
