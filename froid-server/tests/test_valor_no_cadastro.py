"""A etapa do valor, e o que ela existe para impedir.

O CASO
------
O contrato do FROID NR-1 remete a Proposta Comercial quanto a preco, prazo,
quantidade de trabalhadores, estabelecimentos, periodicidade e vigencia
(clausulas 1.5, 13.1 e 14.1). Ate 11/09/2026 o sistema NAO guardava nenhuma
evidencia de qual proposta a empresa havia aceitado: o comprovante de aceite
demonstrava o texto exato do contrato, e nada sobre o valor. Numa discussao
sobre preco, o contrato dizia "veja a Proposta" e nao havia proposta registrada.

A etapa 4 do cadastro fecha essa metade: a empresa ve o valor calculado sobre a
estrutura que acabou de cadastrar, confirma, e o aceite entra no MESMO livro
append-only do aceite juridico — com a versao e o sha256 da tabela comercial no
lugar do documento.
"""

import ast
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO = SERVER_DIR.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
CADASTRO = (
    REPO / "froid-dashboard" / "src" / "pages" / "Nr1CompanyOnboarding.tsx"
).read_text(encoding="utf-8")


def _corpo_da_funcao(fonte: str, nome: str) -> str:
    """Recorte pelo parser, e nao por janela de texto."""
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            return ast.get_source_segment(fonte, no) or ""
    raise AssertionError(f"funcao {nome} nao encontrada")


class AEtapaDoValorEntreSetoresEConferencia(unittest.TestCase):
    def test_os_cinco_passos_estao_na_ordem(self):
        for numero, titulo in (
            (1, "A empresa"),
            (2, "Estabelecimentos"),
            (3, "Setores"),
            (4, "Valor"),
            (5, "Conferência"),
        ):
            with self.subTest(passo=numero):
                self.assertIn(
                    f'<Passo numero={{{numero}}} atual={{passo}} titulo="{titulo}" />',
                    CADASTRO,
                )

    def test_o_painel_nao_calcula_preco(self):
        """Repetir a formula aqui seria a decima terceira copia do preco.

        Em 11/09/2026 havia doze, e tres bases diferentes circulando ao mesmo
        tempo. A tela pergunta ao motor e mostra a resposta.
        """
        for literal in ("1500", "1250", "9.30", "6.55", "12,50", "20000", "50000"):
            with self.subTest(literal=literal):
                self.assertNotIn(literal, CADASTRO)
        self.assertIn("/api/nr1/pricing/simulate?trabalhadores=", CADASTRO)

    def test_sem_valor_nao_da_para_continuar(self):
        """Seguir sem valor deixaria a empresa contratar sem ter visto preco —
        que e exatamente o que esta etapa existe para impedir."""
        self.assertIn("disabled={!valor || !valorConfirmado || confirmandoValor}", CADASTRO)

    def test_a_caixa_de_confirmacao_nao_vem_marcada(self):
        self.assertIn("checked={valorConfirmado}", CADASTRO)
        self.assertIn("useState(false);\n  const [erroDoValor", CADASTRO.replace("\r\n", "\n"))

    def test_a_falha_do_calculo_aparece_e_oferece_saida(self):
        """Tela que some com o valor sem dizer por que parece bug de permissao."""
        self.assertIn("Não foi possível calcular o valor.", CADASTRO)
        self.assertIn("Tentar de novo", CADASTRO)

    def test_a_procedencia_do_numero_acompanha_o_numero(self):
        """Sem a tabela e a digital, seis meses depois ninguem sabe de onde saiu."""
        self.assertIn("valor.pricingTable.code", CADASTRO)
        self.assertIn("valor.pricingTable.sha256.slice(0, 16)", CADASTRO)


class OServidorNaoConfiaNoNumeroDaTela(unittest.TestCase):
    def setUp(self):
        self.corpo = _corpo_da_funcao(MAIN, "nr1_pricing_acceptance")

    def test_o_efetivo_vem_do_banco_e_nao_do_corpo(self):
        """Aceitar o efetivo informado permitiria declarar 10, pagar por 10 e
        operar com 300."""
        self.assertIn("TENANT_STORE.nr1_list_units(", self.corpo)
        self.assertIn('u["unit_type"] == "site"', self.corpo)
        self.assertIn('int(u.get("headcount") or 0)', self.corpo)

    def test_o_preco_e_recalculado_no_servidor(self):
        self.assertIn("pricing_nr1.simular(", self.corpo)
        self.assertIn("_nr1_pricing_tabela_vigente()", self.corpo)

    def test_tela_desatualizada_nao_vira_aceite_de_outro_valor(self):
        """A tela diz QUAL numero mostrou; divergiu, o servidor recusa."""
        self.assertIn('body.get("monthly_total_cents")', self.corpo)
        self.assertIn('calculo["monthlyTotalCents"]', self.corpo)
        self.assertIn("409", self.corpo)

    def test_so_quem_contrata_confirma_o_valor(self):
        """Confirmar preco e ato de contratacao, como assinar o contrato."""
        self.assertIn('{"owner", "administrator"}', self.corpo)
        self.assertIn("403", self.corpo)

    def test_o_aceite_do_valor_entra_no_livro_com_versao_e_digital(self):
        self.assertIn("_record_legal_documents(", self.corpo)
        self.assertIn('"nr1_commercial_proposal"', self.corpo)
        self.assertIn('calculo["pricingTable"]["sha256"]', self.corpo)
        self.assertIn("commercial_snapshot=", self.corpo)

    def test_estrutura_incompleta_recusa_antes_de_precificar(self):
        """Zero trabalhador dividiria por zero no valor por trabalhador."""
        self.assertIn("if not estabelecimentos or trabalhadores <= 0:", self.corpo)


class ATabelaAdulteradaNaoPrecifica(unittest.TestCase):
    """Digital que nao fecha produz RECUSA, e nao preco errado."""

    def setUp(self):
        self.corpo = _corpo_da_funcao(MAIN, "_nr1_pricing_tabela_vigente")

    def test_o_hash_do_banco_e_reconferido(self):
        self.assertIn("hmac.compare_digest", self.corpo)
        self.assertIn("pricing_nr1.pricing_hash", self.corpo)

    def test_a_recusa_usa_o_nome_do_motor_de_origem(self):
        """Quem conhece o PRICING_HASH_MISMATCH do pacote reconhece este."""
        self.assertIn("PRICING_HASH_MISMATCH", self.corpo)
        self.assertIn("503", self.corpo)

    def test_sem_espelho_a_resposta_declara_de_onde_veio(self):
        """Devolver a tabela do modulo calado esconderia o caso em que o banco
        tem outra."""
        self.assertIn('return pricing_nr1.TABELA_VIGENTE, "modulo"', self.corpo)
        self.assertIn('return do_banco, "postgres"', self.corpo)


if __name__ == "__main__":
    unittest.main()
