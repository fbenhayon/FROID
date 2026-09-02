"""A correcao do que o FROID escreveu, na palavra de quem estava la.

Caso real de 02/09/2026. O paciente leu o relatorio da propria sessao e apontou
quatro erros:

  - uma cidade trocada (o relatorio dizia Boston; era Glen Cove, NY);
  - uma inferencia afetiva que ninguem disse — "saudade da esposa e criancas",
    quando a familia esta junta;
  - um trecho que ficou sem sentido;
  - uma palavra que caiu do resumo.

Nenhum era de indice acustico. Todos vieram da camada semantica: transcricao e
resumo gerado.

Nao havia onde registrar. `clinicalNotes` e {id, text, timestamp} — texto livre
sem alvo, sem autor e sem precedencia. A correcao ficaria num campo geral, sem
apontar o trecho errado, e quem abrisse o relatorio depois leria o erro.

E o aviso de LGPD do produto ja prometia ao paciente a "correcao de dados
incompletos, inexatos ou desatualizados". A promessa existia; o mecanismo, nao.
"""

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
PAINEL_DIR = SERVER_DIR.parent / "froid-dashboard" / "src"
TIPOS = (PAINEL_DIR / "lib" / "session-report.ts").read_text(encoding="utf-8")
COMPONENTE = (
    PAINEL_DIR / "components" / "report" / "CorrecoesDoRelatorio.tsx"
).read_text(encoding="utf-8")
RELATORIO = (PAINEL_DIR / "pages" / "SessionReport.tsx").read_text(encoding="utf-8")


class OOriginalNaoEReescrito(unittest.TestCase):
    """Apagar o erro apagaria junto tres coisas.

    A auditoria do que o sistema afirmou; a evidencia de que a correcao foi
    necessaria; e o par (o que o FROID disse / o que era verdade) — o material
    mais proximo de um gabarito que existira antes de haver coleta rotulada.
    """

    def test_a_correcao_e_ACRESCENTADA_nunca_substitui(self):
        trecho = MAIN[MAIN.index("async def add_session_correction") :][:2200]
        self.assertIn("correcoes.append(correcao)", trecho)
        # Nao pode tocar no resumo nem na transcricao originais.
        self.assertNotIn('report["conversationSummaries"] =', trecho)
        self.assertNotIn('report["transcript"] =', trecho)

    def test_o_trecho_errado_e_GUARDADO(self):
        self.assertIn('"trechoOriginal": trecho', MAIN)

    def test_a_lista_tem_teto_como_a_de_notas(self):
        trecho = MAIN[MAIN.index("async def add_session_correction") :][:2200]
        self.assertIn("correcoes[-500:]", trecho)


class AOrigemNaoSeMistura(unittest.TestCase):
    """O que o paciente relata sobre si e o que o profissional observa sao
    evidencias de naturezas diferentes. Fundi-las apagaria a distincao que as
    torna uteis — e e a mesma distincao que separa Y_self de Y_observer em
    qualquer estudo de validade serio."""

    def test_origem_e_obrigatoria_e_restrita(self):
        self.assertIn('origem: str = Field(pattern="^(profissional|paciente)$")', MAIN)

    def test_quem_registrou_e_campo_SEPARADO_de_quem_apontou(self):
        # O profissional transcreve o apontamento do paciente: sao duas pessoas
        # diferentes, e colapsar isso atribuiria ao profissional o que o
        # paciente disse.
        trecho = MAIN[MAIN.index("async def add_session_correction") :][:2200]
        self.assertIn('"origem": payload.origem', trecho)
        self.assertIn('"registradoPor": owner_email', trecho)


class ATaxonomiaVeioDosCasosReais(unittest.TestCase):
    def test_os_quatro_tipos_existem_no_servidor(self):
        for tipo in (
            "transcricao_incorreta",
            "inferencia_indevida",
            "fato_incorreto",
            "trecho_incoerente",
        ):
            self.assertIn(tipo, MAIN)

    def test_os_quatro_tipos_existem_no_painel(self):
        for tipo in (
            "transcricao_incorreta",
            "inferencia_indevida",
            "fato_incorreto",
            "trecho_incoerente",
        ):
            self.assertIn(tipo, TIPOS)

    def test_inferencia_indevida_e_destacada_das_demais(self):
        """E a unica em que o sistema AFIRMOU algo que ninguem disse.

        As outras tres sao erro de captacao; esta e conteudo inventado, e num
        relatorio clinico isso pesa diferente.
        """
        i = COMPONENTE.index("TIPO_COR")
        trecho = COMPONENTE[i : i + 600]
        self.assertIn("inferencia_indevida", trecho)
        self.assertIn("red-", trecho)


class ACorrecaoEhLidaANTES(unittest.TestCase):
    def test_o_bloco_vem_antes_da_procedencia_e_dos_numeros(self):
        """Correcao que aparece depois do texto corrigido chega tarde: a leitura
        clinica ja aconteceu."""
        self.assertLess(
            RELATORIO.index("<CorrecoesDoRelatorio"),
            RELATORIO.index("<ProcedenciaDoRelatorio"),
        )

    def test_a_tela_mostra_as_DUAS_versoes(self):
        self.assertIn("O FROID escreveu", COMPONENTE)
        self.assertIn("Correto", COMPONENTE)

    def test_a_precedencia_de_leitura_e_declarada(self):
        self.assertIn("a correção tem precedência de leitura", COMPONENTE)


class RespostaNaoJsonNaoQuebraATela(unittest.TestCase):
    def test_le_texto_antes_de_json(self):
        """Erro do servidor nao e JSON, e `.json()` nele produz "Unexpected
        token 'I'" no lugar do motivo real — defeito ja vivido neste projeto."""
        self.assertIn("await resposta.text()", COMPONENTE)


class DissonanciaProdutivaNaoEDefeito(unittest.TestCase):
    """O resumo do corte nao existe so para registrar.

    Ele deve dizer em poucas palavras a substancia do que foi tratado, de um
    jeito que produza um ponto de dissonancia entre paciente e profissional e
    traga os dois de volta ao assunto. Quando o paciente discorda de uma LEITURA
    ancorada no que ele de fato disse, isso e o mecanismo funcionando.

    Mas dissonancia so tem valor clinico se o paciente NAO puder descarta-la
    como defeito. Um erro factual — "saudade da esposa e criancas" quando a
    familia esta junta — nao e uma versao mais forte de dissonancia: ele ensina
    que o relatorio nao e confiavel, e a proxima discordancia legitima e
    descartada junto.

    Fidelidade e pre-condicao da friccao, nao o oposto dela. Por isso os cinco
    tipos nao podem viver no mesmo balde.
    """

    def test_o_quinto_tipo_existe_nas_duas_pontas(self):
        self.assertIn("leitura_contestada", MAIN)
        self.assertIn("leitura_contestada", TIPOS)

    def test_a_fronteira_e_uma_funcao_e_nao_espalhada_pelo_codigo(self):
        # Num lugar so: espalhar a regra por `if tipo === ...` faria as duas
        # nocoes divergirem na primeira vez que alguem acrescentasse um tipo.
        self.assertIn("export function ehDefeitoDoSistema", TIPOS)
        self.assertIn('return tipo !== "leitura_contestada"', TIPOS)

    def test_a_tela_separa_as_duas_listas(self):
        self.assertIn("ehDefeitoDoSistema(c.tipo)", COMPONENTE)
        self.assertIn("O que o sistema errou", COMPONENTE)
        self.assertIn("Leituras contestadas", COMPONENTE)

    def test_leitura_contestada_NAO_usa_cor_de_alerta(self):
        """Pinta-la de vermelho junto com os defeitos empurraria o resumo para
        uma neutralidade que nao provoca nada — e provocar e o que ele existe
        para fazer."""
        i = COMPONENTE.index("const TIPO_COR")
        bloco = COMPONENTE[i : COMPONENTE.index("};", i)]
        linha = [l for l in bloco.splitlines() if "leitura_contestada" in l]
        self.assertTrue(linha)
        self.assertNotIn("red-", linha[0])
        self.assertNotIn("amber-", linha[0])

    def test_o_paciente_NAO_corrige_uma_leitura(self):
        """Chamar a versao dele de "correto" decidiria, na tipografia, uma
        questao que e clinica: numa leitura contestada existem duas leituras,
        nao uma certa e uma errada."""
        self.assertIn('"O que o paciente diz"', COMPONENTE)
        self.assertIn('defeito ? "O FROID escreveu" : "Leitura do FROID"', COMPONENTE)

    def test_so_o_defeito_e_riscado(self):
        # Riscar a leitura do FROID afirmaria que ela esta errada, e ela nao esta.
        self.assertIn('defeito ? "line-through decoration-slate-600" : ""', COMPONENTE)


if __name__ == "__main__":
    unittest.main()
