"""O acervo do profissional nao pode sumir da propria listagem.

Apurado em 13/09/2026, em producao: 65 relatorios de sessao gravados em
/data/session_reports.json, 16 pacientes, e o painel mostrando DOIS. Nenhum
erro na tela, HTTP 200 na resposta, nada no log.

Dois defeitos somados, os dois da mesma familia — uma leitura que fracassa ou
que e filtrada devolve "vazio" com cara de sucesso:

1. `_accessible_session_reports` recortava por organizacao ANTES de considerar
   autoria. Relatorio antigo, gravado sem organizationId, resolve para a
   organizacao derivada do E-MAIL do autor; assim que a mesma conta passa a
   operar sob outra organizacao — clinica com CNPJ, empresa NR-1, ou o
   contexto vindo do PostgreSQL em vez do fallback legado — o id corrente
   deixa de bater e o acervo inteiro sai da lista.

2. O painel ignorava a resposta do servidor quando ela vinha vazia
   (`if (remote.length)`) e seguia exibindo o cache do navegador. Foi esse
   cache que exibiu os dois pacientes, dando ao sumico a aparencia de uma
   lista curta em vez de uma falha.

A regra que estes testes fixam: autoria sobrevive a troca de organizacao, e
falha de leitura nunca se disfarca de acervo vazio.
"""

import json
import os
import sys
import tempfile
import unittest

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

import main  # noqa: E402
from tenant_access import AccessContext  # noqa: E402

AUTOR = "psi@exemplo.com"
COLEGA = "outro@exemplo.com"
ORG_DO_EMAIL = str(main.stable_uuid("organization", AUTOR))
ORG_DA_CLINICA = "11111111-1111-4111-8111-111111111111"


def relatorio(session_id, email, organization_id=None, nome="Paciente"):
    registro = {
        "sessionId": session_id,
        "professionalEmail": email,
        "patient": {"name": nome, "id": "p-" + session_id},
        "createdAt": "2026-01-01T00:00:00Z",
    }
    if organization_id is not None:
        registro["organizationId"] = organization_id
    return registro


class AcervoEmDisco(unittest.TestCase):
    """Base comum: um arquivo de acervo de verdade, em disco, por teste."""

    def escrever_acervo(self, registros):
        caminho = os.path.join(
            tempfile.mkdtemp(prefix="froid-acervo-"), "session_reports.json"
        )
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(registros, arquivo, ensure_ascii=False)
        original = main.FROID_SESSION_REPORTS_PATH
        main.FROID_SESSION_REPORTS_PATH = caminho
        self.addCleanup(setattr, main, "FROID_SESSION_REPORTS_PATH", original)
        return caminho

    def corromper(self, caminho):
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write("{isto nao e json")

    def listar_como(self, email, organization_id):
        """Roda a listagem real com o usuario e o contexto informados."""
        contexto = (
            AccessContext.create(
                organization_id=organization_id,
                membership_id="22222222-2222-4222-8222-222222222222",
                user_id="33333333-3333-4333-8333-333333333333",
                roles=["owner", "professional"],
            )
            if organization_id
            else None
        )
        original_user = main._current_user_from_request
        original_auth = main._authorize_tenant_request
        main._current_user_from_request = lambda request: {"email": email}
        main._authorize_tenant_request = lambda *a, **k: contexto
        self.addCleanup(setattr, main, "_current_user_from_request", original_user)
        self.addCleanup(setattr, main, "_authorize_tenant_request", original_auth)
        relatorios, _contexto = main._accessible_session_reports(None)
        return relatorios


class AutoriaSobreviveATrocaDeOrganizacao(AcervoEmDisco):
    """O defeito de producao, reproduzido e fechado."""

    def test_relatorio_sem_organizationId_continua_visivel_ao_autor(self):
        self.escrever_acervo(
            {
                "s1": relatorio("s1", AUTOR, None, "Antigo Um"),
                "s2": relatorio("s2", AUTOR, None, "Antigo Dois"),
            }
        )
        # A conta agora opera sob a organizacao da clinica (derivada do CNPJ),
        # e nao mais sob a derivada do e-mail. Antes da correcao: lista vazia.
        self.assertEqual(len(self.listar_como(AUTOR, ORG_DA_CLINICA)), 2)

    def test_relatorio_carimbado_com_a_organizacao_antiga_continua_visivel(self):
        self.escrever_acervo({"s1": relatorio("s1", AUTOR, ORG_DO_EMAIL, "Carimbado")})
        self.assertEqual(len(self.listar_como(AUTOR, ORG_DA_CLINICA)), 1)

    def test_na_organizacao_de_origem_nada_muda(self):
        self.escrever_acervo({"s1": relatorio("s1", AUTOR, ORG_DO_EMAIL, "Mesmo lugar")})
        self.assertEqual(len(self.listar_como(AUTOR, ORG_DO_EMAIL)), 1)

    def test_sem_contexto_de_organizacao_o_autor_tambem_ve_o_que_e_dele(self):
        self.escrever_acervo({"s1": relatorio("s1", AUTOR, None, "Sem contexto")})
        self.assertEqual(len(self.listar_como(AUTOR, "")), 1)


class OIsolamentoEntreProfissionaisContinuaDePe(AcervoEmDisco):
    """A correcao devolve o que e SEU. Nada alem disso."""

    def test_relatorio_de_colega_nao_aparece_nem_na_mesma_organizacao(self):
        self.escrever_acervo({"s1": relatorio("s1", COLEGA, ORG_DA_CLINICA, "Do colega")})
        self.assertEqual(self.listar_como(AUTOR, ORG_DA_CLINICA), [])

    def test_relatorio_de_colega_nao_aparece_em_outra_organizacao(self):
        self.escrever_acervo({"s1": relatorio("s1", COLEGA, None, "Do colega")})
        self.assertEqual(self.listar_como(AUTOR, ORG_DA_CLINICA), [])

    def test_a_listagem_separa_dois_autores_no_mesmo_arquivo(self):
        self.escrever_acervo(
            {
                "s1": relatorio("s1", AUTOR, None, "Meu"),
                "s2": relatorio("s2", COLEGA, None, "Dele"),
            }
        )
        meus = self.listar_como(AUTOR, ORG_DA_CLINICA)
        self.assertEqual([r["sessionId"] for r in meus], ["s1"])


class FalhaDeLeituraNaoViraAcervoVazio(AcervoEmDisco):
    """"Nao consegui ler" e "voce nao tem nada" param de ter a mesma cara."""

    def test_arquivo_corrompido_levanta_em_modo_estrito(self):
        self.corromper(self.escrever_acervo({"s1": relatorio("s1", AUTOR)}))
        with self.assertRaises(main.SessionReportStoreUnavailable):
            main._load_session_reports(strict=True)

    def test_arquivo_corrompido_ainda_degrada_para_vazio_fora_do_modo_estrito(self):
        self.corromper(self.escrever_acervo({"s1": relatorio("s1", AUTOR)}))
        # Os chamadores de escrita e de contagem nao podem derrubar a
        # requisicao inteira; so a LISTAGEM usa strict.
        self.assertEqual(main._load_session_reports(strict=False), {})

    def test_json_que_nao_e_objeto_tambem_levanta(self):
        caminho = self.escrever_acervo({})
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write("[1, 2, 3]")
        with self.assertRaises(main.SessionReportStoreUnavailable):
            main._load_session_reports(strict=True)

    def test_arquivo_ausente_e_vazio_de_verdade_nos_dois_modos(self):
        caminho = self.escrever_acervo({})
        os.remove(caminho)
        self.assertEqual(main._load_session_reports(strict=True), {})
        self.assertEqual(main._load_session_reports(strict=False), {})

    def test_a_listagem_responde_503_quando_o_acervo_esta_ilegivel(self):
        from fastapi import HTTPException

        self.corromper(self.escrever_acervo({"s1": relatorio("s1", AUTOR)}))
        with self.assertRaises(HTTPException) as capturado:
            self.listar_como(AUTOR, ORG_DO_EMAIL)
        self.assertEqual(capturado.exception.status_code, 503)


class UmRegistroRuimNaoApagaOsOutros(AcervoEmDisco):
    """A decifragem de um relatorio nao decide o destino do acervo inteiro."""

    def test_falha_de_decifragem_isola_o_registro(self):
        self.escrever_acervo(
            {
                "bom1": relatorio("bom1", AUTOR, None, "Integro Um"),
                "ruim": {
                    "sessionId": "ruim",
                    "professionalEmail": AUTOR,
                    "transcript_encrypted": "conteudo-que-nao-decifra",
                    "patient": {"name": "Com problema"},
                },
                "bom2": relatorio("bom2", AUTOR, None, "Integro Dois"),
            }
        )

        class CifraQueQuebra:
            def reveal(self, *args, **kwargs):
                # ValueError de proposito: NAO e TokenEncryptionError. Era
                # exatamente esta a excecao que subia e zerava o acervo todo.
                raise ValueError("chave rotacionada")

        original = main.CLINICAL_TEXT_CIPHER
        main.CLINICAL_TEXT_CIPHER = CifraQueQuebra()
        self.addCleanup(setattr, main, "CLINICAL_TEXT_CIPHER", original)

        carregado = main._load_session_reports(reveal_transcripts=True, strict=True)
        self.assertEqual(len(carregado), 3)
        self.assertTrue(carregado["ruim"].get("transcript_storage_locked"))
        self.assertEqual(carregado["bom1"]["patient"]["name"], "Integro Um")
        self.assertEqual(carregado["bom2"]["patient"]["name"], "Integro Dois")


class ASessaoAbreParaOAutor(AcervoEmDisco):
    """A rota do relatorio unico nao pode recusar quem escreveu o relatorio.

    Segundo ato do mesmo defeito, apurado quando o painel ja listava os
    pacientes: clicar na sessao levava a "Relatorio nao encontrado — ainda nao
    foi gerado neste navegador". O relatorio existia, tinha sido gerado, e o
    servidor devolvia 403. A regra de alcance estava escrita A MAO em tres
    rotas de relatorio unico, alem da listagem, e as copias divergiram — a
    listagem passou a respeitar autoria e as tres continuaram sem respeitar.

    Hoje existe _report_within_context e as quatro chamam a mesma funcao.
    """

    def abrir(self, rotina, session_id, email, organization_id):
        import asyncio

        contexto = AccessContext.create(
            organization_id=organization_id,
            membership_id="22222222-2222-4222-8222-222222222222",
            user_id="33333333-3333-4333-8333-333333333333",
            roles=["owner", "professional"],
        )
        originais = {
            nome: getattr(main, nome)
            for nome in (
                "_current_user_from_request",
                "_tenant_context_from_request",
                "_authorize_tenant_request",
                "_record_tenant_success",
            )
        }
        for nome, valor in originais.items():
            self.addCleanup(setattr, main, nome, valor)
        main._current_user_from_request = lambda request: {"email": email}
        main._tenant_context_from_request = lambda request: contexto
        main._authorize_tenant_request = lambda *a, **k: contexto
        main._record_tenant_success = lambda *a, **k: None
        return asyncio.run(rotina(session_id, None))

    def test_o_autor_abre_a_sessao_sob_outra_organizacao(self):
        self.escrever_acervo({"s1": relatorio("s1", AUTOR, None, "Paciente")})
        devolvido = self.abrir(main.get_session_report, "s1", AUTOR, ORG_DA_CLINICA)
        self.assertEqual(devolvido.get("sessionId"), "s1")

    def test_as_metricas_da_sessao_abrem_pelo_mesmo_motivo(self):
        self.escrever_acervo({"s1": relatorio("s1", AUTOR, None, "Paciente")})
        self.abrir(main.get_session_report_metrics, "s1", AUTOR, ORG_DA_CLINICA)

    def test_relatorio_carimbado_com_a_organizacao_antiga_tambem_abre(self):
        self.escrever_acervo({"s1": relatorio("s1", AUTOR, ORG_DO_EMAIL, "Paciente")})
        devolvido = self.abrir(main.get_session_report, "s1", AUTOR, ORG_DA_CLINICA)
        self.assertEqual(devolvido.get("sessionId"), "s1")

    def test_a_sessao_de_um_colega_continua_recusada(self):
        from fastapi import HTTPException

        self.escrever_acervo({"s1": relatorio("s1", COLEGA, None, "Do colega")})
        with self.assertRaises(HTTPException) as capturado:
            self.abrir(main.get_session_report, "s1", AUTOR, ORG_DA_CLINICA)
        self.assertEqual(capturado.exception.status_code, 403)

    def test_as_metricas_de_um_colega_continuam_recusadas(self):
        from fastapi import HTTPException

        self.escrever_acervo({"s1": relatorio("s1", COLEGA, None, "Do colega")})
        with self.assertRaises(HTTPException) as capturado:
            self.abrir(main.get_session_report_metrics, "s1", AUTOR, ORG_DA_CLINICA)
        self.assertEqual(capturado.exception.status_code, 403)

    def test_a_regra_de_alcance_tem_um_dono_so(self):
        """Se alguem reescrever a mao de novo, este teste avisa."""
        fonte = open(
            os.path.join(SERVER_DIR, "main.py"), encoding="utf-8"
        ).read()
        self.assertNotIn(
            "_report_organization_id(report) != request_context.organization_id",
            fonte,
        )
        # 1 definicao + 4 chamadas (listagem, GET, metrics, DELETE).
        self.assertEqual(fonte.count("_report_within_context("), 5)


class OPainelNaoDescartaARespostaDoServidor(unittest.TestCase):
    """A metade da correcao que vive no navegador, fixada na fonte.

    O guarda `if (remote.length)` fazia a resposta do servidor ser ignorada
    justamente quando ela contradizia o cache local. Sem isto, corrigir o
    backend nao muda o que o profissional ve.
    """

    ARQUIVOS = (
        "froid-dashboard/src/pages/ProfessionalDashboardSummary.tsx",
        "froid-dashboard/src/pages/Dashboard.tsx",
    )

    def fonte(self, relativo):
        """A fonte SEM os comentarios.

        O que se afirma aqui e sobre o codigo que roda. Os comentarios citam o
        guarda removido de proposito, para que quem procurar por ele ache a
        explicacao — e sem esta limpeza a citacao derrubaria o teste.
        """
        raiz = os.path.dirname(SERVER_DIR)
        with open(os.path.join(raiz, relativo), encoding="utf-8") as arquivo:
            bruto = arquivo.read()
        return chr(10).join(
            linha
            for linha in bruto.splitlines()
            if not linha.strip().startswith("//")
        )

    def test_o_guarda_que_descartava_resposta_vazia_nao_existe_mais(self):
        for relativo in self.ARQUIVOS:
            fonte = self.fonte(relativo)
            self.assertNotIn("if (remote.length)", fonte, relativo)
            self.assertNotIn("if (remoteReports.length)", fonte, relativo)

    def test_falha_do_servidor_tem_estado_visivel(self):
        for relativo in self.ARQUIVOS:
            fonte = self.fonte(relativo)
            self.assertIn("setReportsError", fonte, relativo)
            self.assertIn('role="alert"', fonte, relativo)

    def test_a_falha_de_rede_nao_e_mais_engolida_em_silencio(self):
        for relativo in self.ARQUIVOS:
            self.assertNotIn(".catch(() => undefined)", self.fonte(relativo), relativo)


if __name__ == "__main__":
    unittest.main()
