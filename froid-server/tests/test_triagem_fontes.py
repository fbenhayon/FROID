"""A triagem nao pode confundir texto tecnico com segredo comercial.

Os dois falsos positivos abaixo apareceram na primeira execucao, contra a nota
tecnica da NR-1, e cada um bloquearia conteudo legitimo:

  * "margem de erro" — estatistica — casava com o padrao financeiro;
  * "1.5.4.4.5.3" — numeracao de subitem da norma — casava com o padrao de
    endereco IP.

Uma triagem que erra assim treina quem a usa a ignorar o alerta, e aí ela
deixa de proteger.
"""

import importlib.util
from pathlib import Path
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

TOOL = SERVER_DIR / "tools" / "triagem_fontes_explica.py"


def load():
    spec = importlib.util.spec_from_file_location("triagem_fontes_explica", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FalsoPositivoTests(unittest.TestCase):
    def setUp(self):
        self.tool = load()

    def categorias(self, texto: str) -> list[str]:
        return sorted(self.tool.classificar(texto)["achados"])

    def test_margem_de_erro_nao_e_financeiro(self):
        texto = (
            "O FROID calcula a diferenca padronizada e tambem a margem de erro "
            "dessa diferenca, que depende de quantas pessoas responderam."
        )
        self.assertNotIn("financeiro", self.categorias(texto))

    def test_margem_de_lucro_e_financeiro(self):
        self.assertIn(
            "financeiro", self.categorias("A margem de lucro projetada e de 62%.")
        )

    def test_numeracao_de_subitem_da_norma_nao_e_endereco(self):
        for subitem in ("1.5.4.4.4", "1.5.4.4.5.3", "1.5.7.3.2", "1.5.4.4.4.1"):
            texto = f"Conforme o subitem {subitem} da NR-1, a avaliacao considera."
            self.assertNotIn(
                "infra_interna", self.categorias(texto), f"subitem {subitem}"
            )

    def test_endereco_de_servidor_de_verdade_e_detectado(self):
        self.assertIn(
            "infra_interna",
            self.categorias("Conecte em 204.168.229.32 para publicar."),
        )

    def test_a_palavra_token_sozinha_nao_e_credencial(self):
        # O convite anonimo do NR-1 e explicado em termos de token de uso unico.
        texto = "O link do convite carrega um token de uso unico, que expira."
        self.assertNotIn("credencial", self.categorias(texto))

    def test_token_com_valor_atribuido_e_credencial(self):
        self.assertIn("credencial", self.categorias("token=abc123def456"))
        self.assertIn("credencial", self.categorias("senha: 12345678"))


class FalsoPositivoDaBaseRealTests(unittest.TestCase):
    """Frases exatas que a triagem marcou errado na base de producao.

    Cada uma bloquearia literatura publica. Ficam aqui verbatim porque texto
    inventado por mim nao teria produzido nenhuma delas — foi preciso rodar
    contra os 142 arquivos reais para descobrir.
    """

    def setUp(self):
        self.tool = load()

    def categorias(self, texto: str) -> list[str]:
        return sorted(self.tool.classificar(texto)["achados"])

    def test_valoracao_de_expressao_facial_nao_e_valuation_de_empresa(self):
        texto = (
            "Neural evidence for cultural differences in the valuation of "
            "positive facial expressions. Soc. Cogn. Affect. Neurosci."
        )
        self.assertNotIn("financeiro", self.categorias(texto))

    def test_valuation_de_empresa_continua_sendo_detectado(self):
        for texto in (
            "valuation da empresa estimado em R$ 12 milhoes",
            "rodada pre-money de R$ 4 milhoes",
        ):
            self.assertIn("financeiro", self.categorias(texto), texto)

    def test_rodape_do_google_patents_nao_e_estrategia_juridica(self):
        texto = (
            "including priority claims, publications, legal status, "
            "reassignments, and litigation. Google has not performed a legal "
            "analysis and makes no representation."
        )
        self.assertNotIn("juridico_interno", self.categorias(texto))

    def test_estrategia_juridica_de_verdade_continua_sendo_detectada(self):
        for texto in (
            "a estrategia de litigio prevista para o caso",
            "provisao para contingencia trabalhista de R$ 200 mil",
        ):
            self.assertIn("juridico_interno", self.categorias(texto), texto)

    def test_processo_concorrente_nao_e_analise_de_mercado(self):
        texto = "o pipeline executa dois processos concorrentes na mesma GPU."
        self.assertNotIn("rota_de_produto", self.categorias(texto))

    def test_analise_de_mercado_continua_sendo_detectada(self):
        self.assertIn(
            "rota_de_produto",
            self.categorias("analise dos concorrentes diretos no segmento"),
        )


class ImplementacaoProprietariaTests(unittest.TestCase):
    """A fronteira entre interpretar e calcular.

    A triagem inicial encontrou 48 documentos "Arquitetura FROID_*" e nao tinha
    rotulo para eles: nao sao financeiros nem roadmap, sao a propriedade
    intelectual central. Excluir tudo que fala do FROID mataria o produto — o
    Explica existe para explicar o FROID. Excluir nada entrega o algoritmo.
    """

    def setUp(self):
        self.tool = load()

    def categorias(self, texto: str) -> list[str]:
        return sorted(self.tool.classificar(texto)["achados"])

    def test_o_que_ajuda_a_interpretar_nao_e_bloqueado(self):
        for texto in (
            "IPM alto com fala lenta sugere retardo psicomotor; confirme com a escuta.",
            "A zona 7 indica ambivalencia entre o dito e o expresso.",
            "Dissonancia e quando fala e face apontam para lados diferentes.",
            "O painel compara sempre contra a linha de base do proprio paciente.",
        ):
            self.assertEqual(self.categorias(texto), [], texto)

    def test_o_que_revela_o_calculo_e_bloqueado(self):
        for texto in (
            "Pesos proprietarios adotados: minuto -4: 10%, minuto -3: 15%.",
            "A formula do IPM soma as bandas normalizadas por ponderacao.",
            "O limiar de deteccao de dissonancia foi fixado empiricamente.",
            "Matriz de transicao entre as 12 zonas, com os coeficientes de ponderacao.",
        ):
            self.assertIn("implementacao_proprietaria", self.categorias(texto), texto)

    def test_implementacao_bloqueia_antes_de_qualquer_liberacao(self):
        indexar, motivo = self.tool.propor(
            "paper.md",
            {"achados": {"implementacao_proprietaria": ["x"]}, "sinais_literatura": 9},
        )
        self.assertFalse(indexar)
        self.assertIn("calcula", motivo)


class AfirmacaoClinicaTests(unittest.TestCase):
    """O risco que nao e segredo comercial.

    A auditoria encontrou na base uma tabela cruzando IPM e IDM com
    "Interpretacao Clinica" (dissociacao, somatizacao, luto agudo) e "Acao
    Sugerida" (acolher, conter, investigar resistencias). Nao revelava peso
    nem formula — o detector de segredo a liberaria — e era o arquivo mais
    perigoso da base.
    """

    def setUp(self):
        self.tool = load()

    def categorias(self, texto: str) -> list[str]:
        return sorted(self.tool.classificar(texto)["achados"])

    def test_construto_atribuido_a_metrica_e_bloqueado(self):
        for texto in (
            "IDM negativo profundo: paciente parece calmo, mas ha conflito "
            "profundo reprimido (somatizacao).",
            "IPM baixo com queda brusca indica dissociacao ou shutdown.",
            "Dissociacao evidente quando a zona 7 entra em faixa vermelha.",
            "A dissonancia facial-vocal revela afeto reprimido.",
        ):
            self.assertIn("afirmacao_clinica", self.categorias(texto), texto)

    def test_prescricao_de_conduta_e_bloqueada(self):
        for texto in (
            "Acao Sugerida: conter, acolher a emocao, reduzir a ativacao.",
            "Interpretacao Clinica do quadro observado na sessao.",
            "Recomenda-se acompanhar a evolucao comparando baseline e cortes.",
        ):
            self.assertIn("afirmacao_clinica", self.categorias(texto), texto)

    def test_literatura_sobre_os_mesmos_construtos_nao_e_bloqueada(self):
        # Um artigo serio de psicopatologia fala de dissociacao e somatizacao o
        # tempo todo. Bloquear isso empobreceria a base exatamente na area em
        # que o FROID precisa ser forte. O que distingue e a PROXIMIDADE de uma
        # metrica do produto — o sistema atribuindo o construto a uma leitura.
        for texto in (
            "Dissociative symptoms are prevalent in patients with borderline "
            "personality disorder, according to the reviewed literature.",
            "A somatizacao e um fenomeno descrito extensamente na literatura "
            "psicanalitica e psiquiatrica desde o inicio do seculo XX.",
            "Psychomotor retardation has been associated with major depressive "
            "disorder in several acoustic studies.",
        ):
            self.assertNotIn("afirmacao_clinica", self.categorias(texto), texto)

    def test_a_medida_descrita_como_medida_nao_e_bloqueada(self):
        # O texto que as fichas tecnicas usam precisa passar. Se o proprio
        # padrao correto for bloqueado, a categoria e inutil.
        for texto in (
            "O IPM e um indice composto da intensidade global de ativacao, "
            "lido contra a linha de base do proprio paciente.",
            "A zona 7 apresentou desvio de 2,4 desvios-padrao em relacao a "
            "referencia do paciente, sustentado por tres janelas.",
            "A dissonancia facial-vocal conta eventos de divergencia entre "
            "canais medidos na mesma janela de tempo.",
        ):
            self.assertNotIn("afirmacao_clinica", self.categorias(texto), texto)

    def test_a_frase_que_nega_o_construto_nao_e_bloqueada(self):
        # Estas sao as secoes "O que nao afirma" das fichas tecnicas — o texto
        # que existe justamente para impedir a afirmacao clinica. A primeira
        # versao da categoria reprovava as proprias fichas do FROID.
        for texto in (
            "IPM baixo nao e embotamento, shutdown nem dissociacao.",
            "Dissonancia nao e mentira, disfarce nem repressao.",
            "A dissonancia nao e indicador de dissociacao ou somatizacao.",
            "Desvio extremo de zona nunca significa conflito profundo.",
            "Reducao de taxa verbal nao e retardo psicomotor.",
            "O IDM nao infere conteudo reprimido a partir de ausencia de sinal.",
        ):
            self.assertNotIn("afirmacao_clinica", self.categorias(texto), texto)

    def test_a_negacao_nao_serve_de_escudo_para_a_afirmacao_seguinte(self):
        # A guarda le uma janela curta. Uma negacao solta paragrafos antes nao
        # pode liberar uma afirmacao adiante.
        texto = (
            "O FROID nao substitui avaliacao clinica. " + ("Texto neutro. " * 20)
            + "IPM baixo indica dissociacao e shutdown do paciente."
        )
        self.assertIn("afirmacao_clinica", self.categorias(texto))

    def test_afirmacao_clinica_bloqueia_antes_do_segredo(self):
        indexar, motivo = self.tool.propor(
            "IDM vs IPM.md",
            {"achados": {"afirmacao_clinica": ["x"]}, "sinais_literatura": 9},
        )
        self.assertFalse(indexar)
        self.assertIn("clinica", motivo)


class PosturaTests(unittest.TestCase):
    """Na duvida, nao indexa."""

    def setUp(self):
        self.tool = load()

    def test_documento_sem_sinal_nenhum_nao_e_liberado(self):
        indexar, motivo = self.tool.propor(
            "arquivo_qualquer.md", {"achados": {}, "sinais_literatura": 0}
        )
        self.assertFalse(indexar)
        self.assertIn("revisar", motivo)

    def test_documento_do_froid_exige_revisao_mesmo_sem_indicio(self):
        indexar, _ = self.tool.propor(
            "FROID_Nota_Tecnica.md", {"achados": {}, "sinais_literatura": 0}
        )
        self.assertFalse(indexar)

    def test_literatura_publicada_e_liberada(self):
        indexar, motivo = self.tool.propor(
            "fpsyt-16-1656292.pdf.md", {"achados": {}, "sinais_literatura": 5}
        )
        self.assertTrue(indexar)
        self.assertIn("literatura", motivo)

    def test_credencial_bloqueia_ainda_que_pareca_literatura(self):
        indexar, motivo = self.tool.propor(
            "paper.md", {"achados": {"credencial": ["x"]}, "sinais_literatura": 9}
        )
        self.assertFalse(indexar)
        self.assertIn("credencial", motivo)

    def test_financeiro_bloqueia_ainda_que_pareca_literatura(self):
        indexar, _ = self.tool.propor(
            "relatorio.md", {"achados": {"financeiro": ["x"]}, "sinais_literatura": 9}
        )
        self.assertFalse(indexar)


class ManifestoTests(unittest.TestCase):
    def test_ingestao_le_o_manifesto_e_nega_por_padrao(self):
        source = (SERVER_DIR / "tools" / "ingest_approved_sources.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("--manifesto", source)
        self.assertIn('item.get("indexar") is True', source)
        # Ausente do manifesto significa fora, e nao dentro.
        self.assertIn("path.name not in permitidos", source)


if __name__ == "__main__":
    unittest.main()
