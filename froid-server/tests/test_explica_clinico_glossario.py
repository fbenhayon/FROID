# -*- coding: utf-8 -*-
"""O glossario do FROID Explica clinico, preso a tela que ele descreve.

O defeito que este arquivo existe para impedir foi medido em 06/09/2026, numa
sessao real. Perguntado "o que quer dizer isso IND. ESPECTRAL 0.110", o FROID
Explica respondeu que a metrica "nao esta diretamente mencionada nas
informacoes disponiveis". Estava: o painel escreve `IND. ESPECTRAL` e o
contexto carrega `spectral_band_index`, e nada traduzia um no outro.

As garantias travadas aqui sao quatro, e nenhuma e sobre o texto do glossario:

1. **Nao ha rotulo na tela sem ficha.** A tabela do painel e a fonte; o
   catalogo tem de cobri-la inteira. Metrica nova no painel quebra este teste
   antes de chegar ao profissional como "nao consta".
2. **As zonas e as regras faciais nao sao copia solta.** As doze zonas vem de
   `froid_core`; as seis regras faciais sao confrontadas com o fonte de
   `froid_facs`.
3. **Ausencia nunca vira numero.** Chave ausente e chave nula produzem texto de
   ausencia, e o texto nao contem valor nenhum.
4. **Alguem consome.** A instrucao e o prompt do endpoint clinico saem deste
   modulo, e o painel envia os dois campos que o modulo le.
"""

from __future__ import annotations

import ast
import io
import re
import sys
import unittest
from pathlib import Path

SERVIDOR = Path(__file__).resolve().parents[1]
if str(SERVIDOR) not in sys.path:
    sys.path.insert(0, str(SERVIDOR))

RAIZ = SERVIDOR.parent
LIVE_SESSION = RAIZ / "froid-dashboard" / "src" / "pages" / "LiveSession.tsx"
AI_INSIGHTS = RAIZ / "froid-dashboard" / "src" / "components" / "panels" / "AIInsights.tsx"

import explica_clinico  # noqa: E402
import froid_core  # noqa: E402

def _ler(caminho: Path) -> str:
    with io.open(caminho, encoding="utf-8") as arquivo:
        return arquivo.read()


MAIN = _ler(SERVIDOR / "main.py")
FACS = _ler(SERVIDOR / "froid_facs.py")
DISSONANCIA = _ler(SERVIDOR / "froid_dissonance.py")
PAINEL = _ler(LIVE_SESSION)
INSIGHTS = _ler(AI_INSIGHTS)


def _bloco(fonte: str, abertura: str, fechamento: str) -> str:
    inicio = fonte.index(abertura)
    fim = fonte.index(fechamento, inicio)
    return fonte[inicio:fim]


def _corpo_python(fonte: str, nome: str) -> str:
    """O corpo de uma funcao, pelo parser.

    Recorte por numero de linha ou por janela de caracteres ja quebrou duas
    vezes nesta casa so porque um comentario cresceu. Aqui o recorte e pela
    definicao.
    """
    arvore = ast.parse(fonte)
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            return chr(10).join(
                ast.get_source_segment(fonte, item) or "" for item in no.body
            )
    raise AssertionError(f"funcao {nome!r} nao encontrada")


def _sem_quebra(texto: str) -> str:
    """Compara conteudo, nao a coluna onde a linha foi quebrada."""
    return re.sub(r"\s+", " ", texto)


def regras_faciais_do_motor() -> dict[int, str]:
    """Cada REGRA facial do motor, inteira, por zona.

    A unidade e o `if` que decide, nao a chamada a `set_zone`: as AUs vivem na
    CONDICAO, e a zona 7 ainda monta a lista numa variavel antes de chamar.
    Recortar a chamada devolvia um trecho onde AU23 nao aparece — o teste
    acusava divergencia que nao existia, que e o defeito descrito na secao 3 do
    rigor de engenharia (teste que afirma o mecanismo, e nao a garantia).

    Regex com janela fixa falha pela mesma razao, e ainda cortava o `else` da
    zona 6 no meio.
    """
    arvore = ast.parse(FACS)
    alvo = next(
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.FunctionDef) and no.name == "detect_facial_dissonance"
    )

    def zonas_de(no: ast.AST) -> list[int]:
        return [
            int(filho.args[0].value)
            for filho in ast.walk(no)
            if isinstance(filho, ast.Call)
            and isinstance(filho.func, ast.Name)
            and filho.func.id == "set_zone"
            and filho.args
            and isinstance(filho.args[0], ast.Constant)
        ]

    regras: dict[int, str] = {}
    for comando in alvo.body:
        if not isinstance(comando, ast.If):
            continue
        fonte = ast.get_source_segment(FACS, comando) or ""
        for zona in zonas_de(comando):
            regras[zona] = fonte
    return regras


def rotulos_da_tabela() -> list[str]:
    """Os rotulos que o painel de fato renderiza, lidos do proprio painel.

    Recorte pelo NOME da definicao, nunca por numero de linha: recorte por
    linha ja quebrou duas vezes nesta casa so por comentario crescer.
    """
    bloco = _bloco(PAINEL, "const simplifiedMetricEntries", "\n  ];")
    return re.findall(r'\[\s*"([^"]+)"', bloco)


def rotulos_dos_tooltips() -> list[str]:
    bloco = _bloco(PAINEL, "const SIMPLIFIED_METRIC_TOOLTIPS", "\n};")
    return re.findall(r'^\s{2}"?([A-Z0-9][^":\n]*?)"?:\s*$', bloco, flags=re.MULTILINE)


class ATabelaDoPainelTemFichaInteira(unittest.TestCase):
    def test_todo_rotulo_renderizado_tem_ficha(self):
        faltando = [
            rotulo
            for rotulo in rotulos_da_tabela()
            if rotulo not in explica_clinico.INDICE_POR_ROTULO
        ]
        self.assertEqual(
            faltando,
            [],
            "rotulo na tela sem ficha no glossario: o profissional que digitar "
            "esse nome recebe 'nao consta' sobre um numero que esta na tela dele",
        )

    def test_o_catalogo_nao_inventa_rotulo_que_a_tela_nao_tem(self):
        na_tela = set(rotulos_da_tabela())
        sobrando = [i.rotulo for i in explica_clinico.CATALOGO if i.rotulo not in na_tela]
        self.assertEqual(
            sobrando, [], "ficha para rotulo que nao existe mais no painel"
        )

    def test_os_tooltips_e_a_tabela_descrevem_o_mesmo_conjunto(self):
        # Dois catalogos no mesmo arquivo divergem em silencio (padrao 2.7).
        self.assertEqual(sorted(set(rotulos_da_tabela())), sorted(set(rotulos_dos_tooltips())))

    def test_toda_chave_interna_existe_no_painel_ou_no_contexto(self):
        audio = set(re.findall(r'"([a-z0-9_]+)",', _bloco(PAINEL, "const REPORT_AUDIO_KEYS", "] as const;")))
        # Campos que o painel monta no topo do contexto, fora de audio_meta.
        do_contexto = {
            "ipm_score",
            "idm_score",
            "dominant_zone",
            "dissonance_count",
            "emotional_tone",
            "words_per_minute",
        }
        orfas = [
            i.chave
            for i in explica_clinico.CATALOGO
            if i.chave and i.chave not in audio and i.chave not in do_contexto
        ]
        self.assertEqual(orfas, [], "ficha apontando para campo que ninguem emite")

    def test_todo_marcador_declarado_existe_no_motor_de_dissonancia(self):
        chaves = set(re.findall(r'MarkerSpec\(\s*"([a-z0-9_]+)"', DISSONANCIA))
        orfaos = [
            i.marcador
            for i in explica_clinico.CATALOGO
            if i.marcador and i.marcador not in chaves
        ]
        self.assertEqual(orfaos, [], "ficha prometendo regua que o servidor nao calcula")


class AsZonasVemDaFonte(unittest.TestCase):
    def test_as_doze_zonas_sao_as_do_motor(self):
        self.assertEqual(explica_clinico.ZONAS, dict(froid_core.PERCEPTION_ZONES))
        self.assertEqual(sorted(explica_clinico.ZONAS), list(range(1, 13)))

    def test_as_regras_faciais_batem_com_o_motor_facial(self):
        """A tabela de regras e copia declarada; aqui ela e confrontada.

        `detect_facial_dissonance` e codigo imperativo, nao tabela — extrair a
        tabela de la seria refatorar um motor em producao. A copia fica, e este
        teste e o preco dela: mexeu na regra, o teste cai.
        """
        por_zona = regras_faciais_do_motor()
        self.assertEqual(
            sorted(por_zona),
            sorted(explica_clinico.REGRAS_FACIAIS),
            "o conjunto de zonas com regra facial mudou no motor e nao no glossario",
        )
        for zona, (aus, _descricao) in explica_clinico.REGRAS_FACIAIS.items():
            corpo = por_zona[zona]
            for au in aus:
                self.assertIn(
                    au,
                    corpo,
                    f"a regra da zona {zona} nao cita mais {au} no motor facial",
                )

    def test_a_pergunta_por_uma_zona_recebe_o_eixo_dela(self):
        texto = explica_clinico.glossario_do_painel("como interpreto ZONAS Zona 12", {})
        self.assertIn("Crenças e Ações Conflitantes", texto)
        self.assertIn("AU4", texto)
        self.assertEqual(explica_clinico.zonas_citadas("ZONAS Zona 12"), [12])

    def test_numero_solto_sem_a_palavra_zona_nao_vira_zona(self):
        self.assertEqual(explica_clinico.zonas_citadas("o IPM esta em 7"), [])

    def test_numero_fora_da_faixa_nao_vira_zona(self):
        self.assertEqual(explica_clinico.zonas_citadas("a zona 47 existe?"), [])


class OCasamentoTemFronteira(unittest.TestCase):
    """Substring sem fronteira ja custou caro aqui: "como" dentro de
    *comodidade*, "corpo" dentro de *corporativo*. Com rotulos de tres letras o
    estrago seria diario."""

    def test_o_rotulo_da_tela_e_encontrado(self):
        achados = explica_clinico.indices_citados("o que quer dizer isso IND. ESPECTRAL 0.110")
        self.assertEqual([i.rotulo for i in achados], ["IND. ESPECTRAL"])

    def test_variacoes_de_acento_e_separador_colidem(self):
        for pergunta in ("índice espectral", "ind espectral", "IND.ESPECTRAL"):
            with self.subTest(pergunta=pergunta):
                achados = [i.rotulo for i in explica_clinico.indices_citados(pergunta)]
                self.assertIn("IND. ESPECTRAL", achados)

    def test_tom_nao_casa_dentro_de_sintomas(self):
        self.assertEqual(explica_clinico.indices_citados("quais sintomas o paciente relata"), [])

    def test_corte_nao_casa_dentro_de_desconforto(self):
        self.assertEqual(explica_clinico.indices_citados("houve desconforto no relato"), [])

    def test_beta_nao_casa_dentro_de_alfabeto(self):
        self.assertEqual(explica_clinico.indices_citados("leia o alfabeto"), [])

    def test_sub_harmonico_sobrevive_a_grafia_livre(self):
        achados = [i.rotulo for i in explica_clinico.indices_citados("o que e sub-h 5-12")]
        self.assertIn("SUB-H 5-12", achados)


class AAusenciaNuncaViraNumero(unittest.TestCase):
    def test_chave_ausente_do_contexto_se_declara(self):
        texto = explica_clinico.glossario_do_painel("explique o MFCC7", {})
        linha = next(l for l in texto.splitlines() if l.startswith("- Valor nesta sessao"))
        self.assertIn("nao enviado pelo painel", linha)
        self.assertNotRegex(linha, r"\d")

    def test_chave_presente_e_nula_se_declara_como_nao_apurada(self):
        contexto = {"session_biomarkers": {"mfcc7": None}}
        texto = explica_clinico.glossario_do_painel("explique o MFCC7", contexto)
        linha = next(l for l in texto.splitlines() if l.startswith("- Valor nesta sessao"))
        self.assertIn("SEM APURACAO", linha)
        self.assertNotRegex(linha, r"\d")

    def test_o_traco_do_painel_sobe_como_ausencia_e_nao_como_texto(self):
        # `formatMetricValue` devolve "--" para nulo. Ele e declaracao, nao valor.
        contexto = {"panel_metrics": {"TOM": "--"}}
        texto = explica_clinico.glossario_do_painel("o que e TOM", contexto)
        linha = next(l for l in texto.splitlines() if l.startswith("- Valor nesta sessao"))
        self.assertIn("SEM APURACAO", linha)

    def test_zero_medido_continua_sendo_zero(self):
        # A regra e "ausencia nao vira zero", nao "zero nao existe".
        contexto = {"session_biomarkers": {"mfcc7": 0.0}}
        texto = explica_clinico.glossario_do_painel("explique o MFCC7", contexto)
        linha = next(l for l in texto.splitlines() if l.startswith("- Valor nesta sessao"))
        self.assertIn("0.0", linha)
        self.assertNotIn("SEM APURACAO", linha)

    def test_o_corte_por_limite_de_contexto_se_declara(self):
        """Recorte silencioso engana quem le — e aqui quem le e o modelo.

        Pergunta que cita mais rotulos do que cabe recebe as primeiras fichas e
        o AVISO do que ficou de fora, com os nomes.
        """
        pergunta = (
            "explique IPM IDM ZONAS TOM P/MIN DISSO. MFCC7 MFCC9 "
            "DMFCC7 DMFCC9 ZCR JITTER"
        )
        citados = explica_clinico.indices_citados(pergunta)
        self.assertGreater(len(citados), explica_clinico.MAX_FICHAS)
        texto = explica_clinico.glossario_do_painel(pergunta, {})
        aviso = next(l for l in texto.splitlines() if l.startswith("[") and "omitida" in l)
        for indice in citados[explica_clinico.MAX_FICHAS :]:
            self.assertIn(indice.rotulo, aviso)

    def test_a_regua_ausente_nao_vira_dentro_da_faixa(self):
        contexto = {"session_biomarkers": {"jitter": 0.12}}
        texto = explica_clinico.glossario_do_painel("explique o JITTER", contexto)
        self.assertIn("nao veio no contexto desta pergunta", texto)
        self.assertNotIn("situacao: dentro", texto)

    def test_a_regua_enviada_aparece_com_faixa_e_direcao(self):
        contexto = {
            "session_biomarkers": {"jitter": 0.12},
            "panel_markers": [
                {
                    "key": "jitter",
                    "band": [0.01, 0.08],
                    "direction": "acima",
                    "interpretation": "Perturbacao de periodo acima da base.",
                }
            ],
        }
        texto = explica_clinico.glossario_do_painel("explique o JITTER", contexto)
        self.assertIn("faixa deste paciente: 0.01 a 0.08", texto)
        self.assertIn("situacao: acima", texto)

    def test_o_tom_declara_que_nao_tem_apuracao_no_produto(self):
        # O servidor publica `emotional_tone` vazio de proposito desde
        # 02/09/2026. A ficha nao pode sugerir que existe leitura de tom.
        ficha = explica_clinico.INDICE_POR_ROTULO["TOM"]
        self.assertIn("SEM CAPACIDADE DE APURACAO", ficha.medida)


class AsRestricoesProibemODefeitoObservado(unittest.TestCase):
    def test_a_instrucao_proibe_negar_metrica_que_esta_no_glossario(self):
        instrucao = _sem_quebra(explica_clinico.instrucao())
        self.assertIn("nao esta mencionada", instrucao)
        self.assertIn("PROIBIDO", instrucao)

    def test_a_instrucao_proibe_numero_que_nao_veio(self):
        instrucao = _sem_quebra(explica_clinico.instrucao())
        self.assertIn("sem capacidade de apuracao", instrucao)
        self.assertIn("nunca zero", instrucao)

    def test_a_instrucao_pede_o_que_a_medida_abre(self):
        # A reclamacao era profundidade, e o contrato e onde ela e exigida.
        instrucao = _sem_quebra(explica_clinico.instrucao())
        self.assertIn("O QUE ISSO ABRE", instrucao)
        self.assertIn("O QUE DERRUBARIA A LEITURA", instrucao)

    def test_a_instrucao_respeita_o_idioma_pedido(self):
        self.assertIn("Respond in American English", explica_clinico.instrucao("Respond in American English"))

    def test_a_instrucao_mantem_a_fronteira_clinica(self):
        instrucao = _sem_quebra(explica_clinico.instrucao())
        self.assertIn("NAO DIAGNOSTIQUE", instrucao)
        self.assertIn("norma populacional", instrucao)


class OGlossarioEConsumido(unittest.TestCase):
    """Padrao 2.1: peca correta que ninguem le e o defeito mais comum da casa."""

    def test_o_prompt_carrega_o_de_para_completo(self):
        prompt = explica_clinico.montar_prompt(
            pergunta="IND. ESPECTRAL",
            contexto={},
            contexto_cientifico="",
            contexto_da_sessao="",
            transcricao="",
        )
        self.assertIn("IND. ESPECTRAL = spectral_band_index", prompt)
        self.assertIn("DNA FLOOD = dna_autonomic_flooding", prompt)
        self.assertIn("PERGUNTA DO PROFISSIONAL", prompt)

    def test_a_tabela_leva_os_valores_quando_o_painel_os_envia(self):
        """Quase toda leitura util e cruzada, e o cruzamento precisa dos vizinhos.

        A ficha do IND. ESPECTRAL manda abrir as cinco bandas ao lado; a do DNA
        FLOOD manda conferir DNA INFRA e DNA VOCAL antes de ler o composto. Sem
        a tabela inteira com valores, esses conselhos seriam instrucoes que o
        modelo nao tem como seguir.
        """
        contexto = {"panel_metrics": {"IND. ESPECTRAL": "0.110", "DELTA": "0.240"}}
        texto = explica_clinico.glossario_do_painel("IND. ESPECTRAL", contexto)
        self.assertIn("IND. ESPECTRAL = spectral_band_index = 0.110", texto)
        self.assertIn("DELTA = spectral_delta_0_4hz = 0.240", texto)
        # Rotulo que o painel nao mandou nao vira valor nenhum.
        self.assertIn("GAMA = spectral_gamma_30_80hz = nao enviado", texto)

    def test_o_de_para_cobre_todos_os_rotulos(self):
        prompt = explica_clinico.montar_prompt(
            pergunta="qualquer coisa",
            contexto={},
            contexto_cientifico="",
            contexto_da_sessao="",
            transcricao="",
        )
        for rotulo in rotulos_da_tabela():
            with self.subTest(rotulo=rotulo):
                self.assertIn(rotulo, prompt)

    def test_o_endpoint_clinico_usa_o_modulo(self):
        self.assertIn("import explica_clinico", MAIN)
        corpo = _corpo_python(MAIN, "_query_froid_knowledge")
        self.assertIn("explica_clinico.instrucao(", corpo)
        self.assertIn("explica_clinico.montar_prompt(", corpo)

    def test_o_endpoint_nao_carrega_mais_o_prompt_antigo(self):
        # A instrucao antiga pedia so "de modo objetivo", e foi ela que produziu
        # duas frases de ressalva sobre uma pergunta que pedia leitura.
        self.assertNotIn(
            "de modo objetivo, sem diagnosticar e sem inventar", MAIN
        )

    def test_a_queda_local_tambem_usa_o_catalogo(self):
        corpo = _corpo_python(MAIN, "_fallback_froid_explica_result")
        self.assertIn("explica_clinico.indices_citados(query_text)", corpo)

    def test_o_teto_de_saida_cabe_o_contrato(self):
        # Escopado a rota clinica: a rota de analytics tem outro prompt e outro
        # teto, e travar o arquivo inteiro faria este teste defender o teto
        # alheio.
        corpo = _corpo_python(MAIN, "_query_froid_knowledge")
        self.assertIn("max_tokens=FROID_EXPLICA_MAX_TOKENS", corpo)
        self.assertNotIn("max_tokens=900", corpo)


class OPainelEnviaOQueOGlossarioLe(unittest.TestCase):
    def test_o_painel_envia_a_tabela_e_as_reguas(self):
        bloco = _bloco(PAINEL, "const getFroidExplicaContext", "\n  }, [")
        self.assertIn("panel_metrics", bloco)
        self.assertIn("panel_markers", bloco)

    def test_a_tabela_enviada_e_a_mesma_que_a_tela_renderiza(self):
        # Um segundo catalogo montado so para o Explica divergiria da tela na
        # primeira metrica nova — e a divergencia apareceria como o assistente
        # citando um numero que nao esta escrito em lugar nenhum.
        self.assertIn(
            "metricas: simplifiedMetricEntries",
            PAINEL,
        )
        self.assertIn("marcadores: allMarkerReadings", PAINEL)

    def test_o_painel_nao_transforma_ipm_ausente_em_zero(self):
        bloco = _bloco(INSIGHTS, "const buildClinicalContext", "\n  }, [")
        self.assertNotIn("Number(ipmScore || 0)", bloco)
        self.assertIn("ipm_score: ipmScore ?? null", bloco)

    def test_o_painel_nao_conta_zero_dissonancia_sem_zona_apurada(self):
        bloco = _bloco(INSIGHTS, "const buildClinicalContext", "\n  }, [")
        self.assertIn("safeZones.length", bloco)


if __name__ == "__main__":
    unittest.main()
