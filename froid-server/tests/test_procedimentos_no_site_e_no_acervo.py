# -*- coding: utf-8 -*-
"""Os procedimentos novos estao no site e no acervo do FROID Explica, e cada
afirmacao deles tem lastro no codigo.

Pedido do dono (19/10/2026): "esses procedimentos serao consultados pelos
usuarios e o FROID Explica deve estar apto a descrever nos detalhes". A regra
desta casa para texto de produto: antes de publicar descricao de
funcionalidade, conferir a afirmacao no codigo, nao noutra pagina do site
(padrao 2.4, rotulo que promete o que nao entrega). Este teste faz essa
conferencia por construcao: cada frase-chave das notas e do site e procurada
no painel ou no servidor.
"""

from __future__ import annotations

import io
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SERVIDOR = Path(__file__).resolve().parents[1]
if str(SERVIDOR) not in sys.path:
    sys.path.insert(0, str(SERVIDOR))

import main  # noqa: E402
from tools.liberar_notas_froid import LIBERADAS  # noqa: E402

RAIZ = SERVIDOR.parent
NOTAS = SERVIDOR / "knowledge" / "approved" / "Notas_tecnicas_FROID"
NOTA_CLINICA = NOTAS / "FROID_Clinica_Papeis_Agenda_Cotas_Visibilidade.md"
NOTA_EXPLICA = NOTAS / "FROID_Explica_O_Que_Consulta_E_Como_Responde.md"
PAINEL = RAIZ / "froid-dashboard" / "src"
SITE = RAIZ / "froid-site"


def _ler(caminho: Path) -> str:
    with io.open(caminho, encoding="utf-8") as arquivo:
        return arquivo.read()


def _sem_acento(texto: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").lower()


class AsNotasExistemEEstaoLiberadas(unittest.TestCase):
    def test_as_duas_notas_estao_no_acervo_e_na_lista_de_liberacao(self):
        for nota in (NOTA_CLINICA, NOTA_EXPLICA):
            self.assertTrue(nota.exists(), nota.name)
            self.assertIn(nota.name, LIBERADAS, "nota sem liberacao nao chega ao Explica")
            self.assertTrue(LIBERADAS[nota.name].strip())

    def test_as_notas_nao_prometem_o_que_o_painel_nao_faz(self):
        # As tres afirmacoes vetadas da memoria da casa, e a gravacao de audio.
        for nota in (NOTA_CLINICA, NOTA_EXPLICA):
            texto = _sem_acento(_ler(nota))
            self.assertNotIn("sete emocoes", texto, nota.name)
            self.assertNotIn("grava audio", texto.replace("nao grava audio", ""), nota.name)
            self.assertNotIn("reouca", texto, nota.name)

    def test_cada_afirmacao_da_nota_da_clinica_tem_lastro_no_codigo(self):
        papeis = _ler(PAINEL / "components" / "psique" / "PapeisV2.tsx")
        agenda = _ler(PAINEL / "components" / "psique" / "AgendaInterna.tsx")
        # As frases dos motivos vivem no modulo puro desde 20/10/2026 (item 13).
        motivos = _ler(PAINEL / "lib" / "agenda-interna.ts")
        carimbo = _ler(PAINEL / "lib" / "contexto-organizacao.ts")
        migracao_054 = _ler(SERVIDOR / "migrations" / "054_cota_conta_e_paciente_do_clinico.sql")
        servidor = _ler(SERVIDOR / "main.py")
        acesso = _ler(SERVIDOR / "tenant_access.py")
        migracao = _ler(SERVIDOR / "migrations" / "053_psique_scheduling_supervisor.sql")
        self.assertIn("Ativar papéis V2 nesta clínica", papeis)
        self.assertIn('"CLINICAL_SUPERVISOR"', papeis)
        self.assertIn("Agenda da clínica", agenda)
        self.assertIn("Minha agenda", agenda)
        self.assertIn("fora da disponibilidade cadastrada do clínico", motivos)
        self.assertIn("o clínico já tem atendimento nesse horário", motivos)
        self.assertIn("Você vê o nome dos seus pacientes; os demais, por identificador.", agenda)
        self.assertIn('CARIMBO_SOLO = "Solo"', carimbo)
        self.assertIn("Sem carimbo (sessão anterior ao registro)", carimbo)
        self.assertIn("O limite de sessões atribuído a você nesta clínica foi atingido.", servidor)
        self.assertIn('"supervisor": frozenset({', acesso)
        self.assertIn("report_visibility", servidor)
        # O supervisor marca e ve tudo (053), e o nome so vai a secretaria,
        # administracao e clinico do atendimento.
        self.assertIn("ARRAY['SECRETARY','ORG_ADMIN','CLINICAL_SUPERVISOR','CLINICIAN']", migracao)
        self.assertIn("'patient_name',CASE WHEN psique_v2_role_check(ARRAY['SECRETARY','ORG_ADMIN'])", migracao)
        # 054: na lista de pacientes o clinico recebe o nome so dos seus.
        self.assertIn("pa.membership_id=member AND pa.status='active'", migracao_054)
        self.assertIn("'names_scope',escopo", migracao_054)

    def test_cada_afirmacao_da_nota_do_explica_tem_lastro_no_codigo(self):
        import explica_clinico
        import explica_ferramentas

        nomes = {f["name"] for f in explica_ferramentas.FERRAMENTAS}
        self.assertEqual(
            nomes,
            {"cortes_da_sessao", "sessoes_do_paciente", "pacientes_do_profissional",
             "agregado_da_clinica", "trecho_da_transcricao", "referencia_populacional"},
        )
        # Fase 5: a referencia populacional e lista fechada de medidas, piso de
        # coorte e sem SQL do modelo.
        import data_froid_referencia
        self.assertIn("piso de coorte", explica_clinico.instrucao(com_ferramentas=True))
        self.assertIn("NAO uma norma", explica_clinico.instrucao(com_ferramentas=True))
        self.assertGreater(len(data_froid_referencia.MEDIDAS), 20)
        self.assertIn("CoorteInsuficiente", _ler(SERVIDOR / "data_froid_referencia.py"))
        self.assertIn("No maximo 200 palavras", explica_clinico._CONTRATO)
        self.assertIn("TABELA em markdown", explica_clinico._CONTRATO_DE_ANALISE)
        self.assertIn("NAO GRAVA AUDIO", explica_clinico.instrucao())
        self.assertIn("vs base", _ler(SERVIDOR / "explica_clinico.py"))


class OExplicaEncontraAsNotasPorPalavra(unittest.TestCase):
    """O caminho local (sem ChromaDB) ja devolve as notas para as perguntas
    que o profissional vai fazer. A busca vetorial entra na reindexacao."""

    def setUp(self):
        self._dir = patch.object(main, "FROID_APPROVED_KNOWLEDGE_DIR", str(SERVIDOR / "knowledge" / "approved"))
        self._cache = patch.object(main, "APPROVED_KNOWLEDGE_CACHE", None)
        self._dir.start()
        self._cache.start()

    def tearDown(self):
        self._cache.stop()
        self._dir.stop()

    def _rotulos(self, pergunta: str) -> str:
        _docs, rotulos = main._query_local_froid_knowledge(pergunta, limit=4)
        return " | ".join(rotulos)

    def test_perguntas_sobre_a_clinica_trazem_a_nota_da_clinica(self):
        for pergunta in (
            "como ativar a agenda da clinica e conceder papeis",
            "quem pode ver o nome do paciente na agenda, supervisor ou secretaria",
            "o que acontece quando a cota de sessoes do profissional esgota",
            "por que meu paciente aparece com carimbo Solo e outro com o nome da clinica",
        ):
            self.assertIn("Clinica no FROID Psique", self._rotulos(pergunta), pergunta)

    def test_perguntas_sobre_o_assistente_trazem_a_nota_do_explica(self):
        for pergunta in (
            "o froid explica consegue comparar os cortes e as sessoes do paciente",
            "quais ferramentas o assistente consulta e o que ele nao faz",
        ):
            self.assertIn("O FROID Explica: o que ele consulta", self._rotulos(pergunta), pergunta)


class OSiteDescreveOsMesmosProcedimentos(unittest.TestCase):
    def test_o_faq_tem_as_quatro_perguntas_novas(self):
        faq = _ler(SITE / "faq.html")
        for pergunta in (
            "Como os pacientes ficam separados?",
            "Como funcionam os papéis, as cotas e a visibilidade numa clínica?",
            "Como ativar e usar a agenda da clínica?",
            "O que o FROID Explica consegue consultar sobre as minhas sessões?",
        ):
            self.assertIn(pergunta, faq)
        self.assertIn('id="uso-e-contratacao"', faq)

    def test_precos_nao_diz_mais_que_nao_ha_cota_por_profissional(self):
        precos = _ler(SITE / "precos.html")
        self.assertNotIn("sem cota por profissional", precos)
        self.assertIn("limite de sessões", precos)

    def test_a_pagina_do_explica_descreve_cortes_e_consultas(self):
        pagina = _ler(SITE / "froid-explica.html")
        self.assertIn("todos os cortes da sessão", pagina)
        self.assertIn("tabela por corte", pagina)
        self.assertIn("sob o mesmo acesso que a pessoa já tem no painel", pagina)

    def test_como_funciona_aponta_para_o_faq_da_clinica(self):
        pagina = _ler(SITE / "como-funciona-clinico.html")
        self.assertIn('href="faq.html#uso-e-contratacao"', pagina)
        self.assertIn('carimbo "Solo"', pagina)

    def test_nenhuma_pagina_editada_ganhou_mojibake(self):
        for nome in ("faq", "froid-explica", "como-funciona-clinico", "precos"):
            texto = _ler(SITE / f"{nome}.html")
            self.assertNotRegex(texto, r"Ã.|â€", nome)


if __name__ == "__main__":
    unittest.main()
