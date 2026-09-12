"""O motor de preco do NR-1, e o oraculo que prova que o port nao mudou a regra.

DE ONDE VEM O ORACULO
---------------------
`pricing_nr1.py` e um port do pacote `froid-pricing-engine`, em TypeScript,
escrito pelo dono. Port e transcricao, e transcricao erra em silencio: um `<=`
onde era `<`, um arredondamento a mais, uma chave fora de ordem no payload do
hash. Nada disso quebra nada — produz numero diferente.

Os valores abaixo foram COLHIDOS do motor original rodando (`npx tsx`, node
v22.19.0, 11/09/2026), e nao calculados a mao nem pelo proprio port. As duas
implementacoes concordaram nos sete casos e no sha256. Se alguem mexer na conta
de um lado so, este teste e que avisa.

O caso 263/11 nao e arbitrario: e o efetivo e o numero de enderecos de um
cliente real, e e o exemplo que o README do motor original usa.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import pricing_nr1  # noqa: E402


# Colhido do motor em TypeScript. (trabalhadores, estabelecimentos) ->
# (total mensal em centavos, por trabalhador/mes em centavos)
ORACULO_TYPESCRIPT = {
    (263, 11): (573_750, 2_182),
    (100, 1): (170_000, 1_700),
    (300, 1): (420_000, 1_400),
    (1_000, 1): (1_071_000, 1_071),
    (3_000, 1): (2_381_000, 794),
    (1, 1): (21_500, 21_500),
    (5_000, 37): (4_411_000, 882),
    # OS EMPATES. Colhidos do mesmo motor em 11/09/2026, durante auditoria.
    #
    # Nenhum dos sete casos acima cai exatamente em meio centavo, e por isso a
    # bateria passava verde sobre uma divergencia real: `round()` do Python e
    # BANCARIO (empate para o par) e `Math.round` do JavaScript e metade para
    # CIMA. Numa varredura de 12 estabelecimentos por 4.000 trabalhadores os dois
    # discordavam em 33 combinacoes — e a mais banal e 64 pessoas num endereco.
    #
    # Um teste que so exercita o caso facil nao afirma a garantia: afirma que o
    # caso facil funciona.
    (64, 1): (116_000, 1_813),
    (144, 1): (225_000, 1_563),
    (400, 1): (513_000, 1_283),
    (208, 2): (325_000, 1_563),
    (1_920, 3): (1_713_600, 893),
}

HASH_TYPESCRIPT = "043dcbeecb79c313e8c1fe5fe0373b70107efca6b1232a8b2f3bfe744c097fea"


class OPortConcordaComOMotorOriginal(unittest.TestCase):
    def test_os_sete_casos_batem_centavo_a_centavo(self):
        for (trabalhadores, estabelecimentos), esperado in ORACULO_TYPESCRIPT.items():
            with self.subTest(trabalhadores=trabalhadores, estabelecimentos=estabelecimentos):
                r = pricing_nr1.calculate_pricing(
                    pricing_nr1.TABELA_VIGENTE, trabalhadores, estabelecimentos
                )
                self.assertEqual(
                    (r["monthlyTotalCents"], r["perWorkerMonthCents"]), esperado
                )

    def test_o_hash_e_o_mesmo_dos_dois_lados(self):
        """Byte a byte: o payload canonico reproduz o `JSON.stringify` da origem.

        Um espaco a mais no separador do JSON produziria digital diferente para
        a mesma tabela — e a conferencia entre as duas implementacoes deixaria
        de significar qualquer coisa.
        """
        self.assertEqual(pricing_nr1.pricing_hash(pricing_nr1.TABELA_VIGENTE), HASH_TYPESCRIPT)

    def test_a_memoria_de_calculo_acompanha_o_total(self):
        """Proposta sem memoria obriga o cliente a confiar no numero."""
        r = pricing_nr1.calculate_pricing(pricing_nr1.TABELA_VIGENTE, 263, 11)
        self.assertEqual([f["workersInTier"] for f in r["tierBreakdown"]], [100, 163, 0, 0])
        self.assertEqual(
            sum(f["subtotalCents"] for f in r["tierBreakdown"]), r["workersSubtotalCents"]
        )
        self.assertEqual(
            r["baseSubtotalCents"] + r["workersSubtotalCents"], r["monthlyTotalCents"]
        )


class DinheiroEInteiro(unittest.TestCase):
    """Centavo em ponto flutuante acumula erro que so aparece na fatura."""

    def test_todo_valor_devolvido_e_inteiro(self):
        r = pricing_nr1.calculate_pricing(pricing_nr1.TABELA_VIGENTE, 2_137, 9)
        for chave in (
            "baseSubtotalCents",
            "workersSubtotalCents",
            "monthlyTotalCents",
            "perWorkerMonthCents",
        ):
            with self.subTest(chave=chave):
                self.assertIsInstance(r[chave], int)
        for faixa in r["tierBreakdown"]:
            self.assertIsInstance(faixa["subtotalCents"], int)

    def test_a_tabela_vigente_so_tem_centavo_inteiro(self):
        self.assertIsInstance(pricing_nr1.TABELA_VIGENTE["baseEstablishmentCents"], int)
        for faixa in pricing_nr1.TABELA_VIGENTE["tiers"]:
            self.assertIsInstance(faixa["workerPriceCents"], int)

    def test_o_empate_vai_para_cima_e_nao_para_o_par(self):
        """A regra, e nao a ocorrencia.

        Corrigir os 33 casos encontrados e reafirma-los um a um deixaria a
        proxima mudanca de formula livre para reintroduzir `round()`. Isto aqui
        varre e exige a regra inteira.
        """
        divergentes = []
        for estabelecimentos in range(1, 13):
            for trabalhadores in range(1, 2_001):
                r = pricing_nr1.calculate_pricing(
                    pricing_nr1.TABELA_VIGENTE, trabalhadores, estabelecimentos
                )
                total = r["monthlyTotalCents"]
                meia_para_cima = (2 * total + trabalhadores) // (2 * trabalhadores)
                if r["perWorkerMonthCents"] != meia_para_cima:
                    divergentes.append((trabalhadores, estabelecimentos))
        self.assertEqual(
            [], divergentes[:5], f"{len(divergentes)} combinacoes arredondam para o par"
        )

    def test_o_valor_por_trabalhador_nao_passa_por_float(self):
        """Divisao em ponto flutuante perde precisao em efetivo grande.

        A aritmetica inteira nao e so pelo empate: `total / workers` num double
        de 53 bits ja nao e exato quando o total passa de alguns bilhoes de
        centavos, e o erro aparece no numero que o cliente le.
        """
        import ast

        fonte = (SERVER_DIR / "pricing_nr1.py").read_text(encoding="utf-8")
        # Pelo PARSER, e nao pelo texto do arquivo: o comentario que explica a
        # troca cita `round(total / workers)` de proposito, e uma varredura de
        # texto cru falharia contra a propria lapide. A lapide fica — e ela que
        # impede alguem de reintroduzir o bancario por ignorancia.
        expressao = None
        for no in ast.walk(ast.parse(fonte)):
            if isinstance(no, ast.Dict):
                for chave, valor in zip(no.keys, no.values):
                    if isinstance(chave, ast.Constant) and chave.value == "perWorkerMonthCents":
                        expressao = ast.dump(valor)
        self.assertIsNotNone(expressao, "perWorkerMonthCents nao encontrado no retorno")
        self.assertIn("FloorDiv", expressao, "a divisao deixou de ser inteira")
        self.assertNotIn("'round'", expressao, "voltou a usar round(), que e bancario")

    def test_o_valor_por_trabalhador_nao_reconstroi_o_total(self):
        """E arredondado, e serve SO para exibir.

        O teste existe para que ninguem o use como base de fatura achando que
        multiplicar de volta fecha. Com 263 trabalhadores nao fecha, e a
        diferenca e de centavos que viram reais num efetivo grande.
        """
        r = pricing_nr1.calculate_pricing(pricing_nr1.TABELA_VIGENTE, 263, 11)
        self.assertNotEqual(r["perWorkerMonthCents"] * 263, r["monthlyTotalCents"])


class TabelaQuebradaERecusada(unittest.TestCase):
    """Faixa com buraco nao produz erro: produz cobranca a menos, em silencio."""

    def _tabela(self, tiers):
        return {**pricing_nr1.TABELA_VIGENTE, "tiers": tiers}

    def test_buraco_entre_faixas_e_recusado(self):
        # A faixa 2 comecaria em 102, deixando o trabalhador 101 sem preco.
        tiers = [
            {"order": 1, "lowerBound": 1, "upperBound": 100, "workerPriceCents": 1_500},
            {"order": 2, "lowerBound": 102, "upperBound": None, "workerPriceCents": 1_250},
        ]
        with self.assertRaises(pricing_nr1.TabelaInvalida):
            pricing_nr1.calculate_pricing(self._tabela(tiers), 200, 1)

    def test_faixa_que_nao_comeca_em_um_e_recusada(self):
        tiers = [{"order": 1, "lowerBound": 2, "upperBound": None, "workerPriceCents": 1_500}]
        with self.assertRaises(pricing_nr1.TabelaInvalida):
            pricing_nr1.calculate_pricing(self._tabela(tiers), 10, 1)

    def test_so_a_ultima_faixa_pode_ser_aberta(self):
        tiers = [
            {"order": 1, "lowerBound": 1, "upperBound": None, "workerPriceCents": 1_500},
            {"order": 2, "lowerBound": 101, "upperBound": None, "workerPriceCents": 1_250},
        ]
        with self.assertRaises(pricing_nr1.TabelaInvalida):
            pricing_nr1.calculate_pricing(self._tabela(tiers), 200, 1)

    def test_preco_em_reais_e_recusado(self):
        """15.0 em vez de 1500 cobraria quinze centavos por trabalhador."""
        tiers = [{"order": 1, "lowerBound": 1, "upperBound": None, "workerPriceCents": 15.0}]
        with self.assertRaises(pricing_nr1.TabelaInvalida):
            pricing_nr1.calculate_pricing(self._tabela(tiers), 10, 1)

    def test_efetivo_zero_ou_negativo_e_recusado(self):
        """Zero trabalhador dividiria por zero no valor por trabalhador."""
        for trabalhadores, estabelecimentos in ((0, 1), (-5, 1), (10, 0), (10, -1)):
            with self.subTest(trabalhadores=trabalhadores, estabelecimentos=estabelecimentos):
                with self.assertRaises(pricing_nr1.TabelaInvalida):
                    pricing_nr1.calculate_pricing(
                        pricing_nr1.TABELA_VIGENTE, trabalhadores, estabelecimentos
                    )

    def test_booleano_nao_passa_por_inteiro(self):
        """`True` e `int` em Python, e `True` trabalhadores nao existe."""
        with self.assertRaises(pricing_nr1.TabelaInvalida):
            pricing_nr1.calculate_pricing(pricing_nr1.TABELA_VIGENTE, True, 1)


class ASimulacaoCarregaADigitalDaTabela(unittest.TestCase):
    """Valor sem a tabela que o produziu e proposta irreproduzivel."""

    def test_a_simulacao_declara_codigo_versao_e_hash(self):
        r = pricing_nr1.simular(263, 11)
        self.assertEqual(r["pricingTable"]["code"], "FROID-PRICING-2026-V01")
        self.assertEqual(r["pricingTable"]["version"], "1.0")
        self.assertEqual(r["pricingTable"]["sha256"], HASH_TYPESCRIPT)
        self.assertEqual(r["monthlyTotalCents"], 573_750)

    def test_o_nome_da_tabela_nao_entra_no_hash(self):
        """Renomear nao muda a conta.

        Se o nome entrasse, uma correcao de rotulo invalidaria a digital de toda
        proposta ja emitida sob aquela tabela.
        """
        renomeada = {**pricing_nr1.TABELA_VIGENTE, "name": "Outro nome", "status": "draft"}
        self.assertEqual(pricing_nr1.pricing_hash(renomeada), HASH_TYPESCRIPT)

    def test_mudar_a_base_muda_a_digital(self):
        outra = {**pricing_nr1.TABELA_VIGENTE, "baseEstablishmentCents": 50_000}
        self.assertNotEqual(pricing_nr1.pricing_hash(outra), HASH_TYPESCRIPT)


class OBancoEOModuloNaoPodemDivergir(unittest.TestCase):
    """A migration 032 semeia a tabela; `pricing_nr1.py` a declara. Sao COPIAS.

    Copia entre SQL e Python diverge em silencio, e aqui a divergencia produz um
    preco no painel e outro na simulacao publica — sem erro, sem log, visivel so
    quando um cliente compara a tela com a proposta.

    O teste le o TEXTO da migration com regex e compara valor a valor. Nao
    precisa de banco, e por isso roda em qualquer maquina — inclusive onde a
    suite de Postgres e pulada, que e onde este tipo de divergencia costuma
    passar.
    """

    @classmethod
    def setUpClass(cls):
        cls.sql = (
            SERVER_DIR / "migrations" / "032_nr1_pricing_tables.sql"
        ).read_text(encoding="utf-8")

    def test_a_base_semeada_e_a_do_modulo(self):
        achado = re.search(r"'active',\s*\n\s*(\d+),", self.sql)
        self.assertIsNotNone(achado, "base nao encontrada no INSERT da migration")
        self.assertEqual(
            int(achado.group(1)),
            pricing_nr1.TABELA_VIGENTE["baseEstablishmentCents"],
        )

    def test_o_hash_semeado_e_o_que_o_modulo_calcula(self):
        """Hash gravado errado planta a RECUSA em producao.

        A aplicacao reconfere o hash antes de calcular: divergiu, ela nao
        precifica. Uma migration com hash errado derrubaria a simulacao inteira
        no primeiro acesso, e o sintoma nao apontaria para o SQL.
        """
        achado = re.search(r"'([0-9a-f]{64})'", self.sql)
        self.assertIsNotNone(achado, "hash nao encontrado na migration")
        self.assertEqual(
            achado.group(1), pricing_nr1.pricing_hash(pricing_nr1.TABELA_VIGENTE)
        )

    def test_as_faixas_semeadas_sao_as_do_modulo(self):
        linhas = re.findall(
            r"\('FROID-PRICING-2026-V01', (\d+), (\d+), (\d+|NULL), (\d+)\)", self.sql
        )
        self.assertEqual(len(linhas), len(pricing_nr1.TABELA_VIGENTE["tiers"]))
        for (ordem, inferior, superior, preco), faixa in zip(
            linhas, pricing_nr1.TABELA_VIGENTE["tiers"]
        ):
            with self.subTest(faixa=faixa["order"]):
                self.assertEqual(int(ordem), faixa["order"])
                self.assertEqual(int(inferior), faixa["lowerBound"])
                self.assertEqual(
                    None if superior == "NULL" else int(superior), faixa["upperBound"]
                )
                self.assertEqual(int(preco), faixa["workerPriceCents"])

    def test_o_codigo_e_a_vigencia_batem(self):
        self.assertIn("'" + pricing_nr1.TABELA_VIGENTE["code"] + "'", self.sql)
        self.assertIn("DATE '" + pricing_nr1.TABELA_VIGENTE["validFrom"] + "'", self.sql)

    def test_so_existe_uma_tabela_ativa_por_vez(self):
        """Duas ativas produziriam duas propostas com precos diferentes no mesmo
        dia, e nada indicaria qual valia."""
        self.assertIn("nr1_pricing_uma_ativa_por_vez", self.sql)
        self.assertIn("WHERE status = 'active'", self.sql)

    def test_nao_existe_tabela_de_simulacao_paralela(self):
        """O preco aceito mora no `commercial_snapshot` do livro de aceites.

        A primeira versao desta migration criava `nr1_pricing_simulations`, e
        ela teria nascido SEM ESCRITOR. Guardar o mesmo fato em dois lugares e o
        padrao que mais custou tempo nesta casa: a copia que ninguem consome
        diverge da que e consumida, e so aparece quando alguem compara as duas.

        A mencao no comentario da migration e lapide, e fica: ela existe para
        ninguem recriar a tabela por ignorancia.
        """
        self.assertNotIn("CREATE TABLE IF NOT EXISTS nr1_pricing_simulations", self.sql)
        self.assertNotIn("INSERT INTO nr1_pricing_simulations", self.sql)
        self.assertIn("commercial_snapshot", self.sql)


class ARotaPublicaNaoDependeDeAlguemTerLogado(unittest.TestCase):
    """`nr1_active_pricing_table` prepara o esquema, e os vizinhos nao precisam.

    O CASO, 11/09/2026, no primeiro deploy: contentor recem-criado, migration
    032 ainda nao aplicada, e a rota publica de preco devolvendo 503 nas duas
    paginas. A tabela nao existia porque NADA a tinha criado ainda.

    As migrations sobem SOB DEMANDA: `ensure_schema` roda na primeira vez que um
    metodo de conexao de DONO toca o banco. Cinquenta e quatro metodos do store
    NAO a chamam, e isso e deliberado — os que usam o papel `runtime` nao podem
    rodar DDL, e contam com o fato de que algum caminho autenticado ja rodou
    antes deles.

    Este e o unico que nao pode contar com isso: e a unica leitura de banco
    servida numa rota PUBLICA, sem autenticacao. Se depender de alguem ter
    logado, o simulador do site fica quebrado para o visitante — que e
    exatamente quem ele existe para atender.

    A regra que este teste afirma nao e "todo metodo chama ensure_schema", que
    seria falsa. E "o metodo servido ao publico nao depende de outro ter rodado".
    """

    @classmethod
    def setUpClass(cls):
        cls.store = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")

    def _corpo(self, nome):
        import ast

        for no in ast.walk(ast.parse(self.store)):
            if isinstance(no, ast.FunctionDef) and no.name == nome:
                return ast.get_source_segment(self.store, no) or ""
        raise AssertionError(f"metodo {nome} nao encontrado")

    def test_a_leitura_da_tabela_prepara_o_esquema(self):
        corpo = self._corpo("nr1_active_pricing_table")
        self.assertIn("self.ensure_schema()", corpo)
        # E a preparacao vem ANTES da leitura, senao nao adianta.
        self.assertLess(
            corpo.index("self.ensure_schema()"),
            corpo.index("self._connect(runtime=True)"),
        )

    def test_a_leitura_continua_com_o_papel_restrito(self):
        """DDL com conexao de dono, SELECT com o papel de runtime.

        Ler a tabela com a conexao de dono funcionaria e seria pior: a rota e
        publica, e privilegio a mais numa rota sem autenticacao e privilegio
        que so faz falta no dia do incidente.
        """
        corpo = self._corpo("nr1_active_pricing_table")
        self.assertIn("self._connect(runtime=True)", corpo)


if __name__ == "__main__":
    unittest.main()
