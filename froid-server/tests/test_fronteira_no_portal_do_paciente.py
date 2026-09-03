"""O paciente nao le o texto escrito para o profissional.

Achado da avaliacao de arquitetura, 02/09/2026. Dois defeitos em direcoes
OPOSTAS, e por isso nenhum dos dois aparecia como sintoma:

A TELA MOSTRAVA TUDO. `PatientPortalPage` renderizava `item.report` cru. Esse
texto e montado por `buildDissonanceReportText` e contem, por construcao, o
rotulo tecnico do sinal — "Sorriso falso / falsa calma", "Shutdown psiquico /
dissociacao", "Risco de retraumatizacao" — e a linha "Sugestao tecnica ao
profissional: ...". O bloco e liberavel ao paciente.

O PDF NAO MOSTRAVA NADA. `report-pdf.ts` chamava
`patientViewFor(d.title || d.report)`, mas `title` nunca foi persistido: o tipo
so tinha id, timestamp, elapsedSeconds, zone e report. A busca e por chave
EXATA, entao recebia o paragrafo inteiro, nunca casava, e o
`.filter(visao !== null)` apagava tudo.

A salvaguarda existia, foi escrita exatamente para isto, e o proprio teste dela
diz por que: "Um relatorio de producao trazia 'Sorriso falso / falsa calma' e
'Mitigar validando a fala sem confrontar bruscamente'. Serve ao profissional,
que tem formacao para contextualizar. Dito a alguem sobre si, sozinho, num PDF
que circula, o mesmo texto vira veredito sem juiz."

Ela so nunca foi ligada de um lado, e do outro nao tinha a chave.
"""

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

PAINEL = SERVER_DIR.parent / "froid-dashboard" / "src"
PORTAL = (PAINEL / "pages" / "PatientPortalPage.tsx").read_text(encoding="utf-8")
SESSAO = (PAINEL / "pages" / "LiveSession.tsx").read_text(encoding="utf-8")
TIPOS = (PAINEL / "lib" / "session-report.ts").read_text(encoding="utf-8")
TRADUCAO = (PAINEL / "lib" / "dissonance-patient-view.ts").read_text(encoding="utf-8")


class OPortalNaoMostraTextoDeProfissional(unittest.TestCase):
    def test_o_portal_NAO_renderiza_report_cru(self):
        """`{item.report}` era a linha inteira do defeito."""
        self.assertNotIn("{item.report}", PORTAL)

    def test_o_portal_usa_a_traducao(self):
        self.assertIn("patientViewFor(item.title", PORTAL)
        self.assertIn('from "../lib/dissonance-patient-view"', PORTAL)

    def test_sinal_sem_traducao_e_OMITIDO(self):
        """Cair no texto do profissional e o acidente que a traducao existe para
        impedir. Omitir e a unica alternativa segura."""
        i = PORTAL.index("patientViewFor(item.title")
        trecho = PORTAL[i : i + 200]
        self.assertIn("if (!visao) return null;", trecho)


class OTituloEGravado(unittest.TestCase):
    """Sem ele a traducao nao tem chave, e a salvaguarda vira um filtro que
    apaga tudo — que foi o estado do PDF do paciente ate hoje."""

    def test_o_tipo_persistido_tem_title(self):
        i = TIPOS.index("dissonances: Array<{")
        trecho = TIPOS[i : i + 700]
        self.assertIn("title?: string;", trecho)

    def test_a_sessao_grava_o_titulo_tecnico(self):
        self.assertIn("title: classifyDissonance(z, displayAudio).title", SESSAO)

    def test_o_titulo_atravessa_ate_o_registro(self):
        i = SESSAO.index("elapsedSeconds: state.elapsedSeconds,")
        trecho = SESSAO[i : i + 200]
        self.assertIn("title: entry.title,", trecho)


class ATraducaoContinuaCobrindoOsSinais(unittest.TestCase):
    """O portao so protege se houver traducao para o que o motor emite. Um
    titulo novo sem entrada aqui sai OMITIDO — seguro, mas silencioso."""

    def test_os_titulos_do_motor_tem_traducao(self):
        # Os que a tela do profissional pode emitir, conferidos em LiveSession.
        for titulo in (
            "Sorriso falso / falsa calma",
            "Shutdown psíquico / dissociação",
        ):
            self.assertIn(titulo, TRADUCAO, f"sem tradução para: {titulo}")

    def test_a_traducao_nunca_prescreve(self):
        """O texto do profissional traz "Sugestão técnica ao profissional".
        Nenhuma descrição de paciente pode carregar isso."""
        self.assertNotIn("Sugestão técnica", TRADUCAO)


if __name__ == "__main__":
    unittest.main()
