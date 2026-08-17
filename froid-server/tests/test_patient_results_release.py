"""Os dois portões entre a sessão e a área do paciente, e o que NÃO passa por eles.

O paciente só vê uma sessão quando duas coisas são verdadeiras ao mesmo tempo:
o profissional habilitou o acesso daquele paciente aos resultados, e liberou
aquela sessão específica. As duas decisões são do profissional.

O terceiro caso é o que este arquivo mais protege: a exportação LGPD NÃO passa
por nenhum dos dois portões. Portabilidade é direito do titular sobre o dado
dele, e um controle de produto não pode reduzi-la.

Estes testes afirmam sobre o texto-fonte, e não sobre o comportamento em
execução, porque main.py depende de fastapi e o ambiente de teste deste
repositório não o instala — mesma razão e mesmo estilo dos testes vizinhos.
"""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _funcao(fonte: str, nome: str) -> str:
    """Recorta o corpo de uma função de topo de módulo."""
    padrao = rf"\ndef {re.escape(nome)}\(.*?(?=\ndef |\n@app\.|\Z)"
    encontrado = re.search(padrao, fonte, re.DOTALL)
    assert encontrado, f"função {nome} não encontrada"
    return encontrado.group(0)


class PatientResultsReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = (ROOT / "froid-server" / "main.py").read_text(encoding="utf-8")

    # ---------- portão 1: permissão do paciente ----------

    def test_area_do_paciente_verifica_permissao(self):
        corpo = _funcao(self.backend, "_reports_for_patient_session")
        self.assertIn("_patient_results_enabled(patient)", corpo)
        self.assertIn("return []", corpo)

    def test_cadastro_antigo_mantem_acesso(self):
        # Tirar acesso em silêncio de quem já via seria pior que o contrário.
        corpo = _funcao(self.backend, "_patient_results_enabled")
        self.assertIn("if value is None:", corpo)
        self.assertIn("return True", corpo)

    def test_convite_novo_nasce_desligado(self):
        # Liberar dado clínico ao paciente é ato do profissional, e ato não se
        # pratica por omissão.
        self.assertIn(
            "patient_results_enabled = bool(body.get(\"patient_results_enabled\"))",
            self.backend,
        )

    # ---------- portão 2: liberação da sessão ----------

    def test_sessao_nao_liberada_nao_aparece(self):
        corpo = _funcao(self.backend, "_reports_for_patient_session")
        self.assertIn("release = _report_patient_release(report)", corpo)
        self.assertIn("if not release[\"released\"]:", corpo)
        self.assertIn("continue", corpo)

    def test_relatorio_antigo_conta_como_liberado(self):
        corpo = _funcao(self.backend, "_report_patient_release")
        self.assertIn("\"released\": True", corpo)
        self.assertIn("\"legacy\": True", corpo)

    def test_liberar_exige_ao_menos_um_item(self):
        self.assertIn(
            "Selecione ao menos um item para compor o relatório do paciente",
            self.backend,
        )

    # ---------- o filtro morde no servidor, não na tela ----------

    def test_item_nao_selecionado_nao_sai_do_servidor(self):
        corpo = _funcao(self.backend, "_sanitize_report_for_patient")
        self.assertIn("allowed_keys = list(PATIENT_REPORT_ALWAYS) + selected", corpo)

    def test_selecao_desconhecida_e_descartada(self):
        corpo = _funcao(self.backend, "_normalize_patient_report_items")
        self.assertIn("if key in chosen", corpo)
        self.assertIn("PATIENT_REPORT_ITEM_KEYS", corpo)

    def test_identidade_do_documento_entra_sempre(self):
        # Um relatório que não diz de quem é, de quando é e quem o assina não é
        # um relatório. E a retenção de transcrição é informação de titular.
        for chave in ("sessionId", "createdAt", "patient", "professional", "transcriptRetention"):
            self.assertIn(f'"{chave}"', self.backend.split("PATIENT_REPORT_ALWAYS")[1][:600])

    # ---------- o que NÃO passa pelos portões ----------

    def test_exportacao_lgpd_ignora_os_dois_portoes(self):
        corpo = _funcao(self.backend, "_reports_for_patient_privacy_export")
        self.assertNotIn("_patient_results_enabled", corpo)
        self.assertNotIn("_report_patient_release", corpo)

    def test_endpoint_de_exportacao_usa_o_caminho_proprio(self):
        trecho = self.backend.split("patient_portal_privacy_export")[1][:900]
        self.assertIn("_reports_for_patient_privacy_export(patient_session)", trecho)
        self.assertNotIn("_reports_for_patient_session(patient_session)", trecho)

    def test_desligar_nao_fecha_o_portal(self):
        # O portal carrega o canal pelo qual a LGPD é atendida. O controle
        # governa resultados, nunca o acesso em si.
        trecho = self.backend.split("set_patient_results_access")[1][:1400]
        self.assertIn("DESLIGAR NÃO FECHA O PORTAL", trecho)

    # ---------- quem pode mexer ----------

    def test_alterar_permissao_exige_vinculo_com_o_paciente(self):
        # A checagem saiu de dentro do endpoint e virou funcao, porque a leitura
        # do estado precisa da mesma prova que a escrita.
        trecho = self.backend.split("set_patient_results_access")[1][:2600]
        self.assertIn("_professional_linked_to_patient(owner_email, patient_id)", trecho)
        self.assertIn("Paciente não vinculado a este profissional", trecho)

    def test_ler_permissao_exige_o_mesmo_vinculo(self):
        # Ler tambem revela: quem nao atende o paciente nao fica sabendo se ele
        # ve os resultados.
        trecho = self.backend.split("get_patient_results_access")[1][:1600]
        self.assertIn("_professional_linked_to_patient(owner_email, patient_id)", trecho)
        self.assertIn("Paciente não vinculado a este profissional", trecho)

    def test_vinculo_vale_por_convite_ou_por_relatorio(self):
        corpo = _funcao(self.backend, "_professional_linked_to_patient")
        self.assertIn("SESSION_INVITES.values()", corpo)
        self.assertIn("_can_access_report(report, owner_email)", corpo)
        # Sem email ou sem id nao ha vinculo — evita que string vazia case com
        # campo vazio de um cadastro incompleto.
        self.assertIn("if not owner_email or not patient_id:", corpo)
        self.assertIn("return False", corpo)

    def test_liberacao_passa_pela_autorizacao_de_relatorio(self):
        trecho = self.backend.split("set_session_report_patient_release")[1][:1600]
        self.assertIn('"reports.update"', trecho)
        self.assertIn("_can_access_report(report, owner_email)", trecho)

    def test_liberacao_fica_em_auditoria(self):
        trecho = self.backend.split("set_session_report_patient_release")[1][:2600]
        self.assertIn("report.patient_release.update", trecho)
        self.assertIn("report.patient_release.revoke", trecho)

    # ---------- catálogo único ----------

    def test_catalogo_da_tela_vem_do_mesmo_lugar_que_filtra(self):
        # A tela não pode oferecer um item que o filtro desconhece.
        trecho = self.backend.split("get_session_report_patient_release")[1][:1600]
        self.assertIn("for key, label in PATIENT_REPORT_ITEMS", trecho)


if __name__ == "__main__":
    unittest.main()
