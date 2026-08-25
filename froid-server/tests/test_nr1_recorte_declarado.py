"""Recorte sem coorte suficiente e declarado, e nao omitido.

Suprimir e ocultar. Declarar insuficiente e documentar. Ate 25/08/2026 o produto
so sabia fazer a primeira coisa: o painel devolvia lista vazia e o inventario
devolvia HTTP 409 — a empresa pagava o ciclo e nao recebia documento nenhum.

O problema nao e so comercial. Painel vazio nao e neutro: o cliente le "nao ha
risco aqui", que e exatamente a conclusao que a ausencia de dado nao autoriza. O
contrato revisado fechou essa porta em duas clausulas, e a norma diz o mesmo por
outro caminho — 1.5.7.3.1 manda consolidar no inventario os dados da
identificacao de perigos, e nao apenas os riscos que couberam numa
classificacao; 1.5.4.2.1.3 e explicito ao mandar registrar no inventario o risco
cuja medida nao pode ser adotada de imediato.

Estes testes cobrem tres coisas, e a distincao importa:

  1. o texto declarado nao vaza contagem, e indica o remedio certo por portao;
  2. a linha declarada e inteira ou nao existe, nunca meio classificada;
  3. o SQL que produz o veredito nao devolve o numero que o piso protege.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import nr1_compliance  # noqa: E402

MIGRACAO = (SERVER_DIR / "migrations" / "028_recorte_insuficiente_declarado.sql").read_text(
    encoding="utf-8"
)
MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
STORE = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")


class OTextoDeclaradoNaoVazaEIndicaOCaminho(unittest.TestCase):
    def test_nenhuma_nota_cita_contagem_de_resposta_do_recorte(self):
        """O numero esta abaixo do piso por definicao.

        Publica-lo na nota devolveria pela porta dos fundos exatamente a coorte
        que o piso recusou mostrar no painel — e a nota vai para o documento que
        o empregador le.
        """
        for portao in nr1_compliance.SUPPRESSION_GATES:
            with self.subTest(portao=portao):
                nota = nr1_compliance.escalation_note(portao)
                self.assertNotRegex(nota, r"\b\d+\s+respostas? (concluidas|reunidas|obtidas)")
                self.assertNotIn("respostas neste recorte", nota)

    def test_a_amostra_exigida_pode_aparecer_porque_e_numero_da_propria_empresa(self):
        """Sai do efetivo que a contratante declarou, nao da coleta."""
        nota = nr1_compliance.escalation_note(
            "representatividade", required_responses=20, declared_headcount=20
        )
        self.assertIn("20 trabalhadores", nota)
        self.assertIn("20 respostas substantivas", nota)

    def test_cada_portao_indica_o_remedio_que_de_fato_resolve(self):
        """Dizer so "insuficiente" faz a empresa perseguir adesao onde adesao nao resolve.

        Recorte abaixo do piso de anonimato nao publica por mais adesao que
        haja, porque o piso olha o TAMANHO DO GRUPO. Recorte reprovado na
        representatividade publica se a adesao subir. Sao remedios opostos, e o
        cliente que recebe o errado gasta um ciclo inteiro no caminho errado.
        """
        anonimato = nr1_compliance.escalation_note("anonimato")
        self.assertIn("Nenhuma adesao adicional o publica", anonimato)
        self.assertIn("Avaliacao Ergonomica Preliminar", anonimato)

        representatividade = nr1_compliance.escalation_note("representatividade")
        self.assertIn("publica se a adesao subir", representatividade)
        self.assertIn("1.5.3.3", representatividade)

        efetivo = nr1_compliance.escalation_note("efetivo_nao_declarado")
        self.assertIn("declarar o efetivo", efetivo)

    def test_toda_nota_nega_a_leitura_de_ausencia_de_risco(self):
        for portao in nr1_compliance.SUPPRESSION_GATES:
            with self.subTest(portao=portao):
                nota = nr1_compliance.escalation_note(portao)
                self.assertIn("NAO significa ausencia de risco", nota)
                self.assertIn("permanece integral", nota)

    def test_portao_desconhecido_estoura_em_vez_de_devolver_texto_vazio(self):
        """Nota vazia num documento de fiscalizacao e pior que erro no deploy."""
        with self.assertRaises(ValueError):
            nr1_compliance.escalation_note("portao_que_nao_existe")

    def test_a_ordem_dos_achados_e_estavel(self):
        """Documento que muda de ordem entre duas geracoes parece adulterado."""
        criterios = nr1_compliance.DEFAULT_CRITERIA
        linhas = [
            {"unit_id": "b", "dimension_id": "d2", "nr1_factor": "workload_demand",
             "gate": "anonimato", "required_responses": None, "declared_headcount": None},
            {"unit_id": "a", "dimension_id": "d1", "nr1_factor": "work_organization",
             "gate": "representatividade", "required_responses": 20, "declared_headcount": 20},
            {"unit_id": "a", "dimension_id": "d3", "nr1_factor": "autonomy_control",
             "gate": "anonimato", "required_responses": None, "declared_headcount": None},
        ]
        uma = [a.dimension_id for a in nr1_compliance.unclassifiable_findings(linhas, criterios)]
        outra = [
            a.dimension_id
            for a in nr1_compliance.unclassifiable_findings(list(reversed(linhas)), criterios)
        ]
        self.assertEqual(uma, outra)


class ALinhaDeclaradaEInteiraOuNaoExiste(unittest.TestCase):
    def test_o_banco_recusa_linha_meio_classificada(self):
        """Linha pela metade e a que um auditor le como risco baixo.

        Uma linha com risk_level='insuficiente' mas severidade preenchida, ou o
        contrario, seria pior que qualquer dos dois estados puros: parece
        avaliacao e nao e.
        """
        self.assertIn("psychosocial_risk_inventory_classificada_ou_declarada", MIGRACAO)
        restricao = MIGRACAO[MIGRACAO.index("ADD CONSTRAINT psychosocial_risk_inventory_classificada_ou_declarada"):]
        restricao = restricao[: restricao.index("NOT VALID")]
        # Classificada: os quatro numeros presentes, sem portao.
        self.assertIn("risk_level <> 'insuficiente'", restricao)
        self.assertIn("cohort_size IS NOT NULL", restricao)
        self.assertIn("suppression_gate IS NULL", restricao)
        # Declarada: os quatro nulos, com portao e com nota.
        self.assertIn("risk_level = 'insuficiente'", restricao)
        self.assertIn("cohort_size IS NULL", restricao)
        self.assertIn("suppression_gate IS NOT NULL", restricao)
        self.assertIn("escalation_note <> ''", restricao)

    def test_a_coorte_do_recorte_reprovado_nao_e_gravada(self):
        """Gravar o tamanho real poria no DOCUMENTO a contagem que o painel nega.

        O inventario e legivel pelo empregador — e o PGR dele. Guardar ali o
        numero que o piso recusou publicar seria a mesma reidentificacao, com um
        passo a mais.
        """
        trecho = MAIN[MAIN.index("declarados_para_gravar = ["):]
        trecho = trecho[: trecho.index("for achado in declarados")]
        self.assertIn('"cohort_size": None', trecho)
        self.assertIn('"mean_score": None', trecho)
        self.assertIn('"severity": None', trecho)
        self.assertIn('"probability": None', trecho)

    def test_nulo_nao_vira_zero_em_lugar_nenhum(self):
        """int(valor or 0) gravaria "coorte de zero pessoa", que parece medida."""
        import tenant_store

        self.assertIsNone(tenant_store._ou_nulo(None, int))
        self.assertEqual(tenant_store._ou_nulo(0, int), 0)
        self.assertEqual(tenant_store._ou_nulo("7", int), 7)
        # E o INSERT usa o helper, nao a conversao direta.
        insert = STORE[STORE.index("def nr1_store_inventory"):]
        insert = insert[: insert.index("def nr1_list_inventory")]
        self.assertIn('_ou_nulo(row.get("cohort_size"), int)', insert)
        self.assertNotIn('int(row["cohort_size"])', insert)

    def test_a_listagem_poe_o_nao_avaliado_depois_do_critico(self):
        """Em DESC o Postgres poe NULL primeiro.

        Sem NULLS LAST, os recortes que NAO foram avaliados encabecariam o
        inventario, acima dos riscos criticos — a primeira coisa que o leitor ve
        seria a que menos informa.
        """
        listagem = STORE[STORE.index("def nr1_list_inventory"):]
        listagem = listagem[: listagem.index("# -- Plano de ação")]
        self.assertIn("NULLS LAST", listagem)
        self.assertIn("_ou_nulo(row[8], int)", listagem)

    def test_o_declarado_entra_no_mesmo_documento_e_nao_num_anexo(self):
        """Folha a parte e folha que ninguem abre."""
        trecho = MAIN[MAIN.index("stored = TENANT_STORE.nr1_store_inventory("):]
        trecho = trecho[: trecho.index("review_interval_months=")]
        self.assertIn("+ declarados_para_gravar", trecho)


class OSqlNaoDevolveONumeroQueOPisoProtege(unittest.TestCase):
    def test_a_funcao_nao_retorna_contagem_de_resposta(self):
        assinatura = MIGRACAO[MIGRACAO.index("RETURNS TABLE ("):]
        assinatura = assinatura[: assinatura.index(")\nLANGUAGE")]
        colunas = [
            linha.strip().rstrip(",").split()[0]
            for linha in assinatura.splitlines()[1:]
            if linha.strip()
        ]
        # Lista fechada, e nao lista de proibidos: acrescentar coluna aqui passa
        # a ser decisao explicita. Uma checagem por palavra proibida deixaria
        # passar o proximo nome que ninguem pensou em proibir.
        self.assertEqual(
            colunas,
            [
                "unit_id",
                "dimension_id",
                "nr1_factor",
                "gate",
                "required_responses",
                "declared_headcount",
            ],
        )

    def test_abaixo_do_piso_da_campanha_nao_ha_quebra_por_recorte(self):
        """Numa campanha minuscula, dizer quais unidades apareceram ja informa.

        Uma unidade so entra no agrupamento se teve ao menos uma resposta. Com a
        campanha inteira abaixo do piso, listar unidades revelaria quem
        respondeu em que setor — com poucas pessoas, isso aponta.
        """
        corpo = MIGRACAO[MIGRACAO.index("CREATE OR REPLACE FUNCTION froid_nr1_unclassifiable_cohorts"):]
        self.assertIn("IF campaign_total < froid_nr1_min_cohort_total() THEN\n        RETURN;", corpo)
        self.assertIn("IF required_total IS NULL OR campaign_total < required_total THEN", corpo)

    def test_a_funcao_tem_os_mesmos_guardas_do_agregado(self):
        """SECURITY DEFINER sem guarda le campanha de outro inquilino."""
        corpo = MIGRACAO[MIGRACAO.index("CREATE OR REPLACE FUNCTION froid_nr1_unclassifiable_cohorts"):]
        self.assertIn("SECURITY DEFINER", corpo)
        self.assertIn("campaign_org <> froid_current_organization_id()", corpo)
        self.assertIn("froid_membership_is_active()", corpo)
        self.assertIn("campaign_status <> 'closed'", corpo)

    def test_a_funcao_e_a_negacao_exata_do_having_do_agregado(self):
        """Se as duas divergirem, um recorte some das duas listas ou aparece nas duas."""
        agregado = (SERVER_DIR / "migrations" / "025_representativeness_floor.sql").read_text(
            encoding="utf-8"
        )
        self.assertIn("HAVING count(*) >= effective_cut_floor", agregado)
        self.assertIn("HAVING count(*) < effective_cut_floor", MIGRACAO)
        # E os dois usam o mesmo denominador.
        for lado in (agregado, MIGRACAO):
            self.assertIn("coalesce(max(unit.headcount), 0)", lado)
            self.assertIn("THEN coalesce(campaign_headcount, 0) ELSE 0 END", lado)

    def test_a_funcao_e_concedida_ao_papel_de_runtime(self):
        """Funcao aplicada e sem GRANT falha na primeira leitura, longe do deploy."""
        self.assertIn(
            "GRANT EXECUTE ON FUNCTION froid_nr1_unclassifiable_cohorts(uuid, integer)",
            MIGRACAO,
        )
        self.assertIn("REVOKE ALL ON FUNCTION froid_nr1_unclassifiable_cohorts", MIGRACAO)


class OsEndpointsParamDeCalar(unittest.TestCase):
    def test_o_inventario_de_campanha_encerrada_nao_devolve_mais_409(self):
        """Era o pior resultado possivel: pagou o ciclo e nao recebeu documento.

        E ficou sem nada para mostrar a uma fiscalizacao que continua cobrando
        dela, porque a obrigacao do PGR nao depende de a coleta ter dado certo.
        """
        trecho = MAIN[MAIN.index("async def generate_nr1_inventory"):]
        trecho = trecho[: trecho.index("async def list_nr1_inventory")]
        # A unica 409 que resta e a da coleta ainda aberta, que e outra coisa.
        self.assertIn("encerre a coleta antes de gerar o inventário", trecho)
        self.assertNotIn("campanha sem coorte suficiente para gerar inventário", trecho)
        self.assertNotIn("suppression_notice(total)", trecho)

    def test_o_painel_declara_nos_dois_casos(self):
        """Campanha que publica parte dos recortes tem de dizer do resto.

        Mostrar tres setores e calar sobre o quarto afirma, pelo silencio, que o
        quarto esta bem.
        """
        painel = MAIN[MAIN.index("async def read_nr1_panel"):]
        painel = painel[: painel.index("@app.")] if "@app." in painel[10:] else painel
        # Ramo sem nenhum recorte publicavel.
        self.assertIn('"declared": declarados or _nr1_campaign_level_declaration', painel)
        # Ramo com resultado.
        self.assertIn('"declared": declarados,', painel)

    def test_a_declaracao_nao_aparece_com_a_coleta_aberta(self):
        """Insuficiencia de resultado que ainda nao existe seria afirmacao falsa."""
        fonte = MAIN[MAIN.index("def _nr1_declared_findings"):]
        fonte = fonte[: fonte.index("def _nr1_campaign_level_declaration")]
        self.assertIn('if progress.get("status") != "closed":', fonte)
        self.assertIn("return []", fonte)

    def test_falha_ao_declarar_nao_derruba_quem_tem_resultado(self):
        """A declaracao e acrescimo; o agregado e o servico."""
        fonte = MAIN[MAIN.index("def _nr1_declared_findings"):]
        fonte = fonte[: fonte.index("def _nr1_campaign_level_declaration")]
        self.assertIn("except Exception:", fonte)
        self.assertIn("LOGGER.exception", fonte)

    def test_a_resposta_separa_classificado_de_declarado(self):
        """Anunciar 15 riscos avaliados quando 3 nao foram avaliados e mentira."""
        trecho = MAIN[MAIN.index("async def generate_nr1_inventory"):]
        trecho = trecho[: trecho.index("async def list_nr1_inventory")]
        self.assertIn('"declared_rows": len(declarados_para_gravar)', trecho)
        self.assertIn('"inventory_rows": stored', trecho)

    def test_recorte_declarado_nao_semeia_medida_no_plano(self):
        """Medida de prevencao contra risco que nao foi avaliado e medida inventada.

        1.5.5.2.1 manda o plano indicar medidas conforme a CLASSIFICACAO de
        1.5.4.4.3 — e aqui nao houve classificacao. O que o caso pede e
        complementacao metodologica, que e o que a nota de escalonamento diz, e
        nao uma linha de plano com responsavel e prazo para um risco
        desconhecido.
        """
        trecho = MAIN[MAIN.index("async def generate_nr1_inventory"):]
        trecho = trecho[: trecho.index("async def list_nr1_inventory")]
        self.assertIn("seed = nr1_compliance.action_plan_seed(graded)", trecho)
        self.assertNotIn("action_plan_seed(graded + declarados", trecho)


class ATelaMostraOQueNaoFoiAvaliado(unittest.TestCase):
    """De nada adianta o servidor declarar se a tela continua calando.

    O defeito original era visual antes de ser tecnico: quem abria o painel e
    nao via nada concluia que nao havia risco. Declarar no JSON e nao desenhar
    na tela deixaria o defeito exatamente onde estava.
    """

    @classmethod
    def setUpClass(cls):
        cls.pagina = (
            SERVER_DIR.parent
            / "froid-dashboard"
            / "src"
            / "pages"
            / "Nr1Dashboard.tsx"
        ).read_text(encoding="utf-8")

    def test_a_tela_desenha_os_recortes_declarados(self):
        self.assertIn("DeclaredFindings", self.pagina)
        self.assertIn("Recortes sem avaliação conclusiva", self.pagina)

    def test_a_tela_repete_que_nao_e_ausencia_de_risco(self):
        """A frase precisa estar onde a pessoa le, e nao so no documento."""
        self.assertIn("não</strong> significa ausência de risco", self.pagina)

    def test_desenha_nos_dois_ramos_do_painel(self):
        """Um painel que mostra tres setores e cala sobre o quarto afirma que o
        quarto esta bem."""
        self.assertEqual(self.pagina.count("<DeclaredFindings achados={panel.declared}"), 2)

    def test_a_tela_nao_pede_coorte_do_recorte_reprovado(self):
        """O tipo nao tem o campo, e nao pode ganhar um por descuido."""
        tipo = self.pagina[self.pagina.index("type Declared = {"):]
        tipo = tipo[: tipo.index("};")]
        for proibido in ("cohort_size", "mean_score", "severity", "probability"):
            with self.subTest(campo=proibido):
                self.assertNotIn(proibido, tipo)

    def test_cada_portao_tem_rotulo_proprio_na_tela(self):
        rotulos = self.pagina[self.pagina.index("const GATE_LABEL"):]
        rotulos = rotulos[: rotulos.index("};")]
        for portao in nr1_compliance.SUPPRESSION_GATES:
            with self.subTest(portao=portao):
                self.assertIn(portao, rotulos)


class ONivelInsuficienteNaoEUmGrau(unittest.TestCase):
    def test_nao_entra_na_escala_de_risco(self):
        """Se entrasse, seria comparado com "low" como se fosse grau da mesma regua."""
        self.assertNotIn(nr1_compliance.UNCLASSIFIABLE_LEVEL, nr1_compliance.RISK_LEVELS)

    def test_a_matriz_de_gradacao_nao_o_conhece(self):
        for nivel in nr1_compliance.RISK_LEVELS:
            self.assertNotEqual(nivel, nr1_compliance.UNCLASSIFIABLE_LEVEL)
        # E nenhuma funcao de gradacao o devolve.
        fonte = (SERVER_DIR / "nr1_compliance.py").read_text(encoding="utf-8")
        arvore = ast.parse(fonte)
        for no in ast.walk(arvore):
            if isinstance(no, ast.FunctionDef) and no.name in {
                "risk_level_for", "grade", "grade_all", "suggested_measure_type_for_level",
            }:
                corpo = ast.get_source_segment(fonte, no) or ""
                with self.subTest(funcao=no.name):
                    self.assertNotIn("insuficiente", corpo)


if __name__ == "__main__":
    unittest.main()
