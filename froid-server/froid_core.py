import numpy as np
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

import froid_dissonance
import froid_facs

class FroidColor(str, Enum):
    BRANCO = "BRANCO"
    AZUL = "AZUL"
    VERDE = "VERDE"
    AMARELO = "AMARELO"
    VERMELHO = "VERMELHO"
    PRETO = "PRETO"
    CINZA = "CINZA"

PERCEPTION_ZONES = {
    1:  "Não Reconhecido vs. Autovalidação",
    2:  "Pensamento Repetitivo vs. Pensamento Criativo e Independente",
    3:  "Tristeza vs. Paz Interior",
    4:  "Desconexão Emocional vs. Integração Emocional",
    5:  "Autocrítica vs. Amor Próprio",
    6:  "Amor Condicional vs. Amor Incondicional",
    7:  "Raiva vs. Aceitação da Mudança",
    8:  "Medo e Sobrecarga vs. Responsabilização",
    9:  "Expressão Emocional Suprimida vs. Autoexpressão Adequada",
    10: "Indignidade vs. Autoaceitação",
    11: "Crenças Rígidas vs. Abertura às Possibilidades",
    12: "Crenças e Ações Conflitantes vs. Crenças e Ações Congruentes",
}

COLOR_MEANINGS = {
    FroidColor.BRANCO:  "Zonas de compensação contendo menores quantidades de energia vocal (Offsetting)",
    FroidColor.AZUL:    "Zona com baixo nível de desequilíbrio",
    FroidColor.VERDE:   "Zona com nível médio de desequilíbrio",
    FroidColor.AMARELO: "Zona com alto nível de desequilíbrio",
    FroidColor.VERMELHO:"Zona com extremo nível de desequilíbrio",
    FroidColor.PRETO:   "Excesso global de energia em toda a voz",
    FroidColor.CINZA:   "Energia da voz normalizada/distribuída através de todas as zonas",
}

COMMITMENT_MODELS = {
    1: {"title": "COMPROMISSO GERAL", "zones": [1, 2, 3], "keywords": ["responsável", "escolhas", "consciência", "persistência"]},
    2: {"title": "RESPONSABILIDADE PESSOAL", "zones": [4, 8, 10], "keywords": ["passado", "autonomia", "protagonista", "responsabilidade"]},
    3: {"title": "AUTOESTIMA E AUTOACEITAÇÃO", "zones": [5, 10, 3], "keywords": ["respeito", "compaixão", "valor", "autocrítica"]},
    4: {"title": "CONTROLE DA RAIVA E REATIVIDADE", "zones": [7, 9, 8], "keywords": ["raiva", "impulso", "conflitos", "energia"]},
    5: {"title": "LIBERTAÇÃO DE CRENÇAS LIMITANTES", "zones": [11, 12, 2], "keywords": ["crenças", "limitações", "possibilidades", "aprendizados"]},
    6: {"title": "RELACIONAMENTOS SAUDÁVEIS", "zones": [6, 4, 9], "keywords": ["comunicar", "respeito", "reciprocidade", "conexão"]},
    7: {"title": "MUDANÇA PROFUNDA", "zones": [12, 7, 11], "keywords": ["padrões", "autossabotagem", "procrastinação", "identidade"]},
}

class FROIDColorimetryMapper:
    def __init__(self):
        self.perception_zones = PERCEPTION_ZONES
        self.color_scale = COLOR_MEANINGS

    def calculate_multimodal_deviation(self, zone_id, vocal_energy, baseline_energy, facial_dissonance_flag):
        energy_deviation_ratio = (vocal_energy - baseline_energy) / (baseline_energy + 1e-9)
        dissonance_multiplier = 2.5 if facial_dissonance_flag else 1.0
        return energy_deviation_ratio * dissonance_multiplier

    def map_color(self, final_deviation_score):
        if final_deviation_score <= -0.5: return FroidColor.BRANCO
        elif -0.5 < final_deviation_score <= 0.5: return FroidColor.AZUL
        elif 0.5 < final_deviation_score <= 1.5: return FroidColor.VERDE
        elif 1.5 < final_deviation_score <= 3.0: return FroidColor.AMARELO
        else: return FroidColor.VERMELHO

@dataclass
class SessionState:
    session_id: str
    created_at: float = field(default_factory=time.time)
    baseline_buffer: List[np.ndarray] = field(default_factory=list)
    baseline_locked: bool = False
    baseline_energy: Optional[np.ndarray] = None
    mapper: FROIDColorimetryMapper = field(default_factory=FROIDColorimetryMapper)
    # Ativação (média dos desvios absolutos das 12 zonas) medida DURANTE a
    # calibração. Guarda o centro e a dispersão do repouso desta pessoa nesta
    # sessão, para o IPM ser lido contra a régua dela e não contra uma constante.
    baseline_activation: List[float] = field(default_factory=list)
    activation_center: float = 0.0
    activation_scale: float = 0.0
    last_alert_signature: str = ""
    tick_count: int = 0
    word_windows: List[int] = field(default_factory=list)  # palavras por janela de 1s
    previous_mfcc7: Optional[float] = None
    previous_mfcc9: Optional[float] = None
    # De que ramo veio o MFCC anterior: "real" (PCM medido) ou "proxy"
    # (espectro gerado). Comparar janelas de ramos diferentes produz uma
    # derivada sem significado — ver o bloco que zera a referencia na troca.
    previous_mfcc_source: str = ""
    previous_delta_mfcc7: float = 0.0
    previous_delta_mfcc9: float = 0.0
    # F0 real, medida da forma de onda PCM enviada pelo navegador (froid_f0/YIN).
    # 0.0 = ainda sem medida vozeada. Atualizada pelo endpoint acústico e
    # incluída no payload de cada tick.
    latest_f0_mean: float = 0.0
    latest_f0_std: float = 0.0
    latest_f0_voiced_ratio: float = 0.0
    f0_updated_at: float = 0.0
    # PRAZO DE VALIDADE DA MEDIDA.
    #
    # Os tres carimbos de tempo (f0, features de voz e face) eram gravados e
    # NUNCA LIDOS. A consequencia, verificada: paciente muta o microfone no
    # minuto 3 e `latest_voice_features` nunca e limpo — o motor segue
    # publicando `real_pcm` sobre a ultima janela medida ate o fim da sessao, e
    # cada tick e contado como voz real na procedencia do relatorio.
    #
    # Com a camera e pior. A flag facial congela, e a confirmacao temporal — que
    # existe para matar pico isolado — se INVERTE: nada e mais "sustentado" que
    # um valor parado. Sai dissonancia facial-vocal CONFIRMADA no registro
    # clinico de um paciente cuja camera estava coberta.
    #
    # Os prazos saem da cadencia real de cada captura: o audio envia janelas de
    # 1 s e a face roda a 3 Hz. Quatro segundos sao quatro janelas perdidas;
    # dois segundos e meio sao mais de sete quadros faciais perdidos. Generosos
    # o bastante para oscilacao de rede, curtos o bastante para que microfone
    # mudo apareca como mudo.
    VALIDADE_VOZ_S: float = 4.0
    VALIDADE_FACE_S: float = 2.5
    # Piso de vozeamento para a janela contar como VOZ, e nao apenas como sinal.
    #
    # Mesmo valor que `froid_dissonance.py:217` ja usava para descartar janela
    # com desvio ruidoso demais. Aplicado uma etapa antes, ele impede que ruido
    # de sala calibre as baselines de repouso do paciente.
    PISO_DE_VOZEAMENTO: float = 0.30
    # Biomarcadores vocais REAIS (froid_voice) medidos do PCM do navegador, e o
    # buffer rolante de PCM usado para as bandas de modulação lentas.
    latest_voice_features: Optional[dict] = None
    voice_features_updated_at: float = 0.0
    pcm_buffer: Optional[np.ndarray] = None
    pcm_sample_rate: int = 16000
    baseline_mfcc7_real: float = 0.0
    baseline_mfcc9_real: float = 0.0
    # Baselines de repouso do paciente para as métricas base de dissonância
    # (F0, loudness, ZCR), calibradas por EMA durante os ~60s iniciais. 0.0 =
    # ainda sem referência (marcador relativo não é avaliado).
    baseline_f0_real: float = 0.0
    baseline_loudness_real: float = 0.0
    baseline_zcr_real: float = 0.0
    # Baselines das bandas de modulacao MEDIDAS (percentual da energia total de
    # modulacao). Existem porque os indices DNA sao desvio RELATIVO contra a
    # referencia — e comparar valor medido contra baseline derivada de proxy
    # misturaria duas reguas na mesma divisao.
    baseline_sub_5_12_real: float = 0.0
    baseline_sub_12_20_real: float = 0.0
    baseline_sub_20_40_real: float = 0.0
    baseline_energy_85_165_real: float = 0.0
    # Calibração PRÓPRIA das baselines de voz real (F0/loudness/ZCR/MFCC),
    # independente da baseline espectral: o microfone do paciente pode entrar
    # depois dos 60s iniciais; sem contador próprio, essas baselines ficariam
    # zeradas e os marcadores relativos jamais avaliariam.
    real_voice_baseline_ticks: int = 0
    # Marcações FACIAIS REAIS (froid_facs): AUs e dissonâncias faciais derivadas
    # dos blendshapes medidos pelo navegador. None = ainda sem face medida, e o
    # tick sai com `facs_source = "sem_apuracao"` e campos faciais nulos.
    latest_facial_aus: Optional[dict] = None
    latest_facs_flags: Optional[dict] = None
    latest_facs_details: Optional[dict] = None
    facial_updated_at: float = 0.0
    # Histórico da condição de dissonância evidente (>= 1 marcador fora da
    # métrica base, últimos ticks) para a confirmação temporal — evita
    # alertar sobre pico de um único tick.
    dissonance_history: List[bool] = field(default_factory=list)

    def update_f0(self, f0_mean: float, f0_std: float, voiced_ratio: float) -> None:
        # Só substitui por uma medida vozeada; silêncio/ruído (f0<=0) preserva
        # o último valor válido em vez de zerar o indicador.
        if f0_mean and f0_mean > 0.0:
            self.latest_f0_mean = float(f0_mean)
            self.latest_f0_std = float(f0_std)
            self.latest_f0_voiced_ratio = float(voiced_ratio)
            self.f0_updated_at = time.time()

    def ingest_pcm(self, signal: np.ndarray, sample_rate: int, keep_seconds: float = 3.0) -> np.ndarray:
        """Acumula PCM num buffer rolante (últimos keep_seconds) para dar
        resolução às bandas de modulação lentas. Retorna o buffer atual."""
        self.pcm_sample_rate = int(sample_rate)
        incoming = np.asarray(signal, dtype=np.float64)
        if self.pcm_buffer is None or self.pcm_buffer.size == 0:
            self.pcm_buffer = incoming
        else:
            self.pcm_buffer = np.concatenate([self.pcm_buffer, incoming])
        max_samples = int(keep_seconds * sample_rate)
        if self.pcm_buffer.size > max_samples:
            self.pcm_buffer = self.pcm_buffer[-max_samples:]
        return self.pcm_buffer

    def update_voice_features(self, features: Optional[dict]) -> None:
        """Registra o conjunto de biomarcadores vocais reais e sincroniza a F0."""
        if not features:
            return
        self.latest_voice_features = features
        self.voice_features_updated_at = time.time()
        self.update_f0(
            float(features.get("f0_mean") or 0.0),
            float(features.get("f0_var") or 0.0),
            float(features.get("f0_voiced_ratio") or 0.0),
        )

    def update_facial_features(self, blendshapes: Optional[dict]) -> None:
        """Recebe blendshapes faciais reais do navegador e deriva AUs +
        dissonâncias faciais (froid_facs), armazenando-as para o próximo tick."""
        if not blendshapes:
            return
        result = froid_facs.process_facial_frame(blendshapes)
        if not result.get("action_units"):
            return
        self.latest_facial_aus = result["action_units"]
        self.latest_facs_flags = result["flags"]
        self.latest_facs_details = result["details"]
        self.facial_updated_at = time.time()

    # Piso da dispersão, em unidades de desvio relativo. Uma calibração quase
    # sem variação produziria escala perto de zero, e qualquer respiração
    # depois disso saturaria o índice em 0 ou 100. Dois por cento é o menor
    # movimento que ainda vale como referência de repouso.
    ACTIVATION_SCALE_FLOOR = 0.02
    # Quantos ticks de calibração bastam para uma referência confiável. Abaixo
    # disso a mediana ainda dança demais.
    ACTIVATION_MIN_SAMPLES = 12
    # Ganho da sigmoide sobre o logaritmo da razão de ativação. Com 1.2, dobrar
    # a ativação do repouso leva o índice a ~69, quadruplicar a ~84 e reduzir à
    # metade a ~31 — a amplitude inteira fica em uso sem que a fala comum já
    # encoste no teto.
    ACTIVATION_GAIN = 1.2

    def _update_activation_reference(self, activation: float) -> None:
        """Aprende o centro e a dispersão do repouso desta sessão.

        Só coleta enquanto a linha de base não está travada — depois disso a
        régua fica fixa, senão o índice se readaptaria ao próprio movimento e
        voltaria a parecer inerte por outro caminho: uma ativação sustentada
        viraria o novo "normal" e o desvio desapareceria.
        """
        if self.baseline_locked and self.activation_scale > 0.0:
            return
        if not np.isfinite(activation):
            return
        self.baseline_activation.append(float(activation))
        # Limite defensivo: calibração não deveria passar de algumas centenas de
        # ticks, e uma lista sem teto vira vazamento numa sessão longa que nunca
        # trave a linha de base.
        if len(self.baseline_activation) > 600:
            self.baseline_activation = self.baseline_activation[-600:]
        if len(self.baseline_activation) < self.ACTIVATION_MIN_SAMPLES:
            return
        amostras = np.asarray(self.baseline_activation, dtype=np.float64)
        centro = float(np.median(amostras))
        # Desvio absoluto mediano, escalado para equivaler a um desvio-padrão em
        # distribuição normal. Mediana e MAD em vez de média e desvio-padrão
        # porque um pigarro ou uma batida de porta durante a calibração
        # deslocaria a régua da sessão inteira.
        mad = float(np.median(np.abs(amostras - centro))) * 1.4826
        self.activation_center = centro
        self.activation_scale = max(mad, self.ACTIVATION_SCALE_FLOOR)

    def _payload_sem_apuracao(self, motivo: str, face_medida: bool = False) -> dict:
        """O tick que nao mediu o espectro, dizendo isso — e sem perder o que MEDIU.

        Determinacao do dono do produto em 02/09/2026, e ela e absoluta:
        proibido simular. Quando nao ha capacidade de apuracao, o sistema
        INFORMA que nao ha — nunca supoe, nunca inventa.

        Quase tudo o que este motor publica deriva do vetor espectral de 12
        bandas: as Zonas, o IPM, o IDM, os MFCC, as bandas de modulacao, os
        sub-harmonicos e os indices DNA. Sem PCM real nao existe esse vetor, e
        ate hoje o laco preenchia a lacuna com ruido gaussiano de picos
        sorteados. Cada numero publicado depois disso era consequencia de um
        sorteio.

        Mas a regra corta dos DOIS lados. F0 e as AUs faciais chegam por
        caminhos proprios e podem estar medidas mesmo sem espectro; descarta-las
        seria inventar ausencia, que e o mesmo pecado com o sinal trocado. Elas
        saem preenchidas, e o resto sai NULO.

        O conjunto de chaves e o MESMO do payload normal. Um consumidor que le
        `audio_meta["f0_mean"]` nao pode quebrar so porque nao houve apuracao —
        e foi exatamente assim que quatro testes de integracao quebraram quando
        a primeira versao deste metodo devolveu um dicionario menor.
        """
        f0_medida = self.latest_f0_mean > 0.0
        return {
            "session_id": self.session_id,
            "timestamp_ms": int(time.time() * 1000),
            "apuracao_disponivel": False,
            "motivo_sem_apuracao": motivo,
            "ipm_score": None,
            "idm_score": None,
            "coherence_status": "SEM_APURACAO",
            "global_energy": {
                "cor_plot": "CINZA",
                "descricao": "Sem capacidade de apuracao",
            },
            "perception_zones": [],
            "realtime_alerts": [],
            # NO TOPO, como no payload medido — nao dentro de audio_meta.
            #
            # A primeira versao pos estas duas dentro de `audio_meta`, onde o
            # payload normal nao as tem: chave movida, nao preservada. O painel
            # entao nao as encontrava no lugar esperado e caia no proprio valor
            # de queda, `?? 5.0`, imprimindo "DR 5.00" sobre nenhuma medida.
            "dr_value": None,
            "commitment_models": [],
            # As chaves acompanham o evento real (`evident_markers`, nao
            # `markers`), pelo mesmo motivo de sempre: quem consome nao deve
            # descobrir a ausencia por KeyError.
            "dissonance_event": {
                "has_dissonance": False,
                "evident_count": 0,
                "categories": [],
                "evident_markers": [],
                "all_markers": [],
                "summary": "",
                "severity": 0.0,
                "mean_severity": 0.0,
                "voice_features_source": "sem_apuracao",
                "facs_source": "real_facs" if face_medida else "sem_apuracao",
            },
            "audio_meta": {
                "voice_real": False,
                # A face PODE ter sido medida sem voz. Apagar isso violaria a
                # regra na outra direcao: apurar e nao informar.
                "facial_real": face_medida,
                "voice_features_source": "sem_apuracao",
                "facs_source": "real_facs" if face_medida else "sem_apuracao",
                "f0_source": "yin_pcm" if f0_medida else "sem_apuracao",
                "baseline_locked": self.baseline_locked,
                "emotional_tone": "",
                "transcription_snippet": "",
                # F0 chega por endpoint proprio e sobrevive a ausencia do
                # espectro.
                "f0_mean": round(self.latest_f0_mean, 2) if f0_medida else 0.0,
                "f0_var": round(self.latest_f0_std, 2) if f0_medida else 0.0,
                "f0_voiced_ratio": round(self.latest_f0_voiced_ratio, 3) if f0_medida else 0.0,
                "facial_action_units": self.latest_facial_aus if face_medida else None,
                "jitter_unit": "internal_proxy_0_2_spectral_dispersion",
                "shimmer_unit": "internal_proxy_0_2_spectral_step_variation",
                "spectral_band_context": "voice_modulation_not_eeg",
                "baseline_progress": len(self.baseline_buffer),
                "baseline_target": 60,
                "dna_baseline_locked": self.baseline_locked,
                "mfcc9_delta_delta_spastic_threshold": None,
                "zone": None,
                "tema": None,
                "deviation_score": None,
                "facial_dissonance_detected": None,
                "dissonance_details": None,
                "model_id": None,
                "title": None,
                "zones": None,
                "theme": None,
                "neutro": None,
                "ansioso": None,
                "triste": None,
                "irritado": None,
                "alegre": None,
                "suprimido": None,
                "voice_baseline_ready": None,
                "jitter": None,
                "shimmer": None,
                "baseline_f0": None,
                "loudness_dbfs": None,
                "baseline_loudness": None,
                "zcr": None,
                "baseline_zcr": None,
                "mfcc7_delta_delta": None,
                "mfcc9_delta_delta": None,
                "dna_autonomic_flooding": None,
                "dna_dissociative_shutdown": None,
                "dna_somatoaffective_dissonance": None,
                "zone_deviations": None,
                "facial_dissonance_count": None,
                "words_per_window": None,
                "words_per_minute_10m": None,
                "total_words_session": None,
                "session_theme": None,
                "theme_minute_mark": None,
                "bioacoustic_window_ms": None,
                "mfcc7": None,
                "mfcc9": None,
                "mfcc7_delta": None,
                "mfcc9_delta": None,
                "mfcc9_delta_delta_spastic_alert": None,
                "baseline_mfcc7": None,
                "baseline_mfcc9": None,
                "spectral_delta_0_4hz": None,
                "spectral_theta_4_8hz": None,
                "spectral_alpha_8_12hz": None,
                "spectral_beta_12_30hz": None,
                "spectral_gamma_30_80hz": None,
                "spectral_band_index": None,
                "subharmonic_energy_5_12hz": None,
                "subharmonic_energy_12_20hz": None,
                "subharmonic_energy_20_40hz": None,
                "energy_85_165hz": None,
                "dna_infrasound_nuclear": None,
                "dna_limbic_modulation": None,
                "dna_neurogenic_resonance": None,
                "dna_vocal_basal_tension": None,
                "dna_subharmonic_index": None,
                "dna_facial_multiplier": None,
                "jitter_proxy_index": None,
                "shimmer_proxy_index": None,
                "speech_rate_proxy": None,
                "clinical_insight": None,
            },
        }

    def process_tick(self):
        """Um tick. Le SOMENTE o que foi medido e guardado neste estado.

        Ate 02/09/2026 este metodo recebia o vetor espectral e as flags faciais
        de fora, e o laco os preenchia com `MockBiometricStream`. Os tres
        parametros ficaram mortos quando a simulacao foi proibida — e parametro
        morto num metodo assim nao e so ruido: e a porta por onde alguem
        reinjeta dado nao medido sem que nada acuse. Fechada.
        """
        self.tick_count += 1
        voice_spectral_12 = None
        facs_dissonance_flags: dict = {}
        facs_details: dict = {}
        # Se há biomarcadores vocais REAIS medidos do PCM do paciente, o vetor
        # espectral de 12 bandas real substitui o simulado — passando a
        # alimentar as Zonas, o IPM, o IDM e a colorimetria com a voz de fato.
        agora = time.time()
        # Medida vencida nao e medida. Ver VALIDADE_VOZ_S.
        if (
            self.latest_voice_features is not None
            and agora - self.voice_features_updated_at > self.VALIDADE_VOZ_S
        ):
            self.latest_voice_features = None
        if (
            self.latest_facs_flags is not None
            and agora - self.facial_updated_at > self.VALIDADE_FACE_S
        ):
            self.latest_facs_flags = None
            self.latest_facs_details = None
            self.latest_facial_aus = None
        # A F0 tambem vence: sem isso, `f0_source` diria `yin_pcm` sobre um
        # valor de minutos atras.
        if self.latest_f0_mean > 0.0 and agora - self.f0_updated_at > self.VALIDADE_VOZ_S:
            self.latest_f0_mean = 0.0
            self.latest_f0_std = 0.0
            self.latest_f0_voiced_ratio = 0.0

        real = self.latest_voice_features
        tem_espectro = bool(
            real
            and isinstance(real.get("voice_spectral_12"), (list, tuple))
            and len(real["voice_spectral_12"]) == 12
        )
        # SINAL NAO E VOZ.
        #
        # O portao antigo aceitava qualquer janela com 12 posicoes preenchidas.
        # `froid_voice.extract_voice_features` so desiste com menos de 8
        # amostras ou silencio digital EXATO — uma janela de ruido de sala a
        # -62 dBFS, com `f0_voiced_ratio` zero, sai com o dicionario completo e
        # era carimbada como `real_pcm`.
        #
        # O estrago nao ficava no tick: as baselines de repouso eram calibradas
        # nesse ruido, e o primeiro tick de fala de verdade disparava marcadores
        # em varias categorias ao mesmo tempo — "dissonancia evidente multipla"
        # fabricada por referencia errada, gravada no documento clinico. E os
        # primeiros trinta segundos de consulta sao tipicamente o profissional
        # falando, com o paciente em silencio.
        #
        # O criterio nao e inventado aqui: `froid_dissonance.py:217` ja descarta
        # a janela com `f0_voiced_ratio < 0.30` por considerar o desvio ruidoso
        # demais. Mesma regua, aplicada uma etapa antes.
        vozeamento = float(
            (real or {}).get("f0_voiced_ratio")
            or self.latest_f0_voiced_ratio
            or 0.0
        )
        tem_voz_medida = tem_espectro and vozeamento >= self.PISO_DE_VOZEAMENTO
        # PROIBIDO SIMULAR. Sem espectro medido nao ha o que derivar, e o
        # honesto e dizer isso em vez de publicar 98 campos calculados sobre
        # ruido sorteado.
        if not tem_voz_medida:
            # A face pode estar sendo medida agora. Nao ha zona sem voz — toda
            # dissonancia facial-vocal e definida CONTRA a referencia vocal —
            # mas dizer que a face nao foi apurada, quando foi, seria inventar
            # ausencia. Uma coisa e nao medir; outra e medir e nao ter contra o
            # que comparar.
            face_medida = (
                self.latest_facs_flags is not None
                and self.latest_facs_details is not None
            )
            # O QUE DEPENDE DE CONTINUIDADE NAO SOBREVIVE AO BURACO.
            #
            # O retorno antecipado pula, corretamente, todo o calculo — e com
            # ele pula tambem as atualizacoes de estado no fim do tick. Tres
            # delas presumem que o tick anterior foi o segundo anterior:
            #
            #   `dissonance_history` alimenta a confirmacao temporal. Parada
            #   durante o buraco, ela guarda o que aconteceu ANTES dele, e uma
            #   unica leitura nova, minutos depois, completaria um padrao
            #   "sustentado" com valores de outro momento da consulta.
            #
            #   `previous_mfcc*` e a referencia das derivadas. Sem reset, a
            #   primeira delta apos o buraco compara janelas separadas por
            #   minutos e produz um pico que ninguem viveu — e picos de DDMFCC9
            #   alimentam o alerta de contracao espastica.
            #
            #   `last_alert_signature` suprime alerta repetido. Congelada, ela
            #   engoliria o primeiro alerta pos-buraco por parecer duplicata.
            #
            # A baseline NAO e zerada: ela foi construida sobre voz real e o
            # silencio nao a invalida.
            self.dissonance_history = []
            self.previous_mfcc7 = None
            self.previous_mfcc9 = None
            self.previous_delta_mfcc7 = 0.0
            self.previous_delta_mfcc9 = 0.0
            self.previous_mfcc_source = ""
            self.last_alert_signature = ""
            if tem_espectro:
                motivo = (
                    "janela sem voz vozeada: sinal presente, mas abaixo do piso "
                    "de vozeamento — ruido de sala nao e medida de voz"
                )
            else:
                motivo = "audio do paciente nao chegou ao motor nesta janela"
            return self._payload_sem_apuracao(
                motivo
                + (
                    "; a leitura facial foi medida, mas a dissonancia "
                    "facial-vocal exige referencia vocal"
                    if face_medida
                    else ""
                ),
                face_medida=face_medida,
            )
        voice_spectral_12 = np.asarray(real["voice_spectral_12"], dtype=np.float64)
        # Se há marcações FACIAIS REAIS (blendshapes do navegador -> AUs FACS),
        # elas substituem as flags/detalhes simulados recebidos — passando a
        # reger as dissonâncias faciais, os multiplicadores e os alertas.
        # Sem captura facial nao se inventa dissonancia. Antes, `facs_source`
        # ficava "mock" e as flags SORTEADAS do gerador regiam o multiplicador
        # 2.5, o dna_flooding e o dna_somato — com texto clinico pronto que
        # chegava a tela sem nenhuma marca de que fora gerado.
        facs_source = "sem_apuracao"
        if self.latest_facs_flags is not None and self.latest_facs_details is not None:
            facs_dissonance_flags = self.latest_facs_flags
            facs_details = self.latest_facs_details
            facs_source = "real_facs"
        else:
            facs_dissonance_flags = {i: False for i in range(1, 13)}
            facs_details = {i: None for i in range(1, 13)}
        # A baseline só é construída com VOZ REAL. Antes, o buffer acumulava
        # também o vetor simulado e travava após 60 ticks independentemente —
        # se o áudio real do paciente entrasse depois disso (cenário comum), a
        # baseline ficava congelada sobre dados simulados e TODOS os desvios de
        # zona, o IPM e o IDM passavam a comparar voz real contra referência
        # falsa. Sem voz real, a baseline permanece provisória e destravada.
        has_real_voice = bool(real and "voice_spectral_12" in real)
        if not self.baseline_locked:
            if has_real_voice:
                self.baseline_buffer.append(voice_spectral_12.copy())
                if len(self.baseline_buffer) >= 60:
                    stacked = np.stack(self.baseline_buffer)
                    self.baseline_energy = np.mean(stacked, axis=0)
                    self.baseline_locked = True
                else:
                    self.baseline_energy = np.mean(np.stack(self.baseline_buffer), axis=0)
            elif self.baseline_energy is None:
                # Referência provisória enquanto não há voz real medida.
                self.baseline_energy = np.ones(12) * 5.0

        if self.baseline_energy is None:
            self.baseline_energy = np.ones(12) * 5.0

        perception_zones = []
        global_deviations = []
        raw_deviations = []  # desvio VOCAL puro (sem M_fac), p/ o motor de dissonância
        has_critical_dissonance = False
        has_dissonance = False

        for zone_idx in range(1, 13):
            v_energy = float(voice_spectral_12[zone_idx - 1])
            b_energy = float(self.baseline_energy[zone_idx - 1])
            d_flag = facs_dissonance_flags.get(zone_idx, False)
            d_details = facs_details.get(zone_idx, None)
            raw_deviations.append((v_energy - b_energy) / (b_energy + 1e-9))

            dev_score = self.mapper.calculate_multimodal_deviation(zone_idx, v_energy, b_energy, d_flag)
            color = self.mapper.map_color(dev_score)
            global_deviations.append(dev_score)

            zone_payload = {
                "zone": zone_idx,
                "tema": self.mapper.perception_zones[zone_idx],
                "deviation_score": round(dev_score, 3),
                "cor_plot": color.value,
                "facial_dissonance_detected": d_flag,
                "dissonance_details": d_details,
            }
            perception_zones.append(zone_payload)

            if d_flag:
                has_dissonance = True
                if dev_score > 3.0:
                    has_critical_dissonance = True

        mean_abs_dev = np.mean(np.abs(global_deviations))
        ipm_activation = float(mean_abs_dev)

        # IPM (Índice de Potência Multimodal): sigmoide logística da ativação,
        # padronizada contra a linha de base DESTA sessão.
        #
        # Duas versões anteriores travaram, cada uma numa ponta: o mapa linear
        # prendia o índice em [50, 100], e a sigmoide que o substituiu foi
        # centrada em ativação = 1.0 — o que significa "cada zona desviando 100%
        # da linha de base, em média". Isso é evento extremo, não ativação
        # típica: medido, o índice ficava entre 19 e 25 com amplitude de 1 a 9
        # pontos numa escala de 100. A barra inerte.
        #
        # A causa é a mesma nas duas: um centro FIXO para uma grandeza cuja
        # escala depende da pessoa, do microfone e do ambiente. Aqui o centro e a
        # dispersão vêm da calibração da própria sessão — a mesma disciplina da
        # prova de eficácia do NR-1, onde cada setor é comparado consigo mesmo.
        #
        # z = k * ln(A / centro), e IPM = 100 * sigma(z).
        #
        # A razão logarítmica, e não a diferença padronizada. Minha primeira
        # tentativa dividiu pela DISPERSÃO do repouso — que mede o tremor do
        # sinal parado, não a faixa que a pessoa percorre falando. Medida, ela
        # saturava em 100 já na fala calma: trocar barra inerte embaixo por
        # barra inerte no topo não é correção.
        #
        # A razão contra o próprio repouso é a grandeza certa: "esta pessoa está
        # com o dobro da ativação dela em silêncio" quer dizer a mesma coisa em
        # qualquer microfone e em qualquer sala. O logaritmo torna a leitura
        # simétrica — metade da ativação afasta de 50 tanto quanto o dobro.
        self._update_activation_reference(ipm_activation)
        centro = float(self.activation_center)
        if centro <= self.ACTIVATION_SCALE_FLOOR:
            # Sem repouso medido ainda, ou repouso praticamente nulo. Sem régua
            # não se padroniza: o índice fica no meio, declaradamente neutro, em
            # vez de fingir precisão.
            ipm_score = 50.0
        else:
            razao = max(ipm_activation, 1e-6) / centro
            z = self.ACTIVATION_GAIN * float(np.log(razao))
            ipm_score = float(np.clip(100.0 / (1.0 + np.exp(-z)), 0.0, 100.0))
        # IDM escalar (a "bússola"): média COM SINAL dos desvios das 12 zonas.
        # Positivo = energia acima da baseline (hiperativação); negativo =
        # abaixo (hipoativação). Preserva a direção que o valor absoluto perdia.
        idm_signed = float(np.mean(global_deviations))

        mean_vocal = float(np.mean(voice_spectral_12))
        mean_baseline = float(np.mean(self.baseline_energy))
        global_energy_excess = mean_vocal > (mean_baseline * 2.0)

        if global_energy_excess:
            global_color = FroidColor.PRETO
        else:
            max_dev = max(abs(d) for d in global_deviations)
            if max_dev < 0.3:
                global_color = FroidColor.CINZA
            else:
                global_color = self.mapper.map_color(max(global_deviations))

        any_facs_active = any(facs_dissonance_flags.values()) or any(facs_details.values())
        # Embotamento afetivo = REDUÇÃO da resposta emocional: voz apagada
        # (energia abaixo da baseline) sem atividade facial. A condição anterior
        # disparava com energia ALTA (mean_vocal > baseline*1.3), invertendo o
        # sentido clínico. Corrigido para energia baixa.
        if mean_vocal < mean_baseline * 0.7 and not any_facs_active:
            coherence_status = "EMBOTAMENTO"
        elif has_critical_dissonance:
            coherence_status = "DISSONANCIA ALTA"
        elif has_dissonance:
            coherence_status = "DISSONANCIA"
        elif not self.baseline_locked:
            coherence_status = "NEUTRO"
        else:
            coherence_status = "COERENTE"

        # O SERVIDOR NAO CONTA PALAVRAS, e nao tem como contar.
        #
        # Ate 02/09/2026 esta linha era `int(np.random.poisson(2.4))`: um
        # sorteio a cada tick, incondicional, com ou sem audio. Dele saiam
        # tambem words_per_minute_10m, total_words_session e speech_rate_proxy
        # — quatro campos publicados a partir de um dado inventado.
        #
        # A transcricao acontece no NAVEGADOR, e e la que as palavras existem.
        # O painel ja recalcula tudo isso do texto real antes de exibir, e o
        # datamart grava a versao do painel. Nenhum dos quatro chegava a tela.
        #
        # Mas saida fabricada sem leitor e pior que saida errada com leitor:
        # ninguem a corrige, e o proximo que a ligar num grafico recebe um
        # numero inventado sem nenhum aviso. Zero e a leitura honesta de quem
        # nao mede.
        words_this_window = 0
        self.word_windows.append(words_this_window)
        # Manter últimas 600 janelas = ~10 minutos (1s * 600 = 600s)
        if len(self.word_windows) > 600:
            self.word_windows.pop(0)

        # Média de palavras por minuto nos últimos 10 minutos
        words_per_minute_10m = sum(self.word_windows) / max(1, len(self.word_windows)) * 60

        # Tema da sessão (simulado — a cada 10 min mudaria via análise semântica)
        minutes_elapsed = self.tick_count // 60
        themes = [
            "Exploração inicial e construção de vínculo terapêutico",
            "Conflitos de autovalidação e reconhecimento pessoal",
            "Padrões de autocrítica e busca por autoaceitação",
            "Raiva reprimida e dificuldade com mudanças",
            "Crenças limitantes e procrastinação comportamental",
            "Supressão emocional e necessidade de autoexpressão",
            "Relacionamentos e padrões de desconexão afetiva",
            "Revisão de ganhos e consolidação de compromissos"
        ]
        session_theme = themes[min(minutes_elapsed // 10, len(themes) - 1)]

        # Top 3 modelos de compromisso baseados nas zonas mais ativas (desvio absoluto)
        sorted_zones = sorted(perception_zones, key=lambda z: abs(z["deviation_score"]), reverse=True)
        top_zone_ids = [z["zone"] for z in sorted_zones[:5]]
        model_scores = {}
        for m_id, model in COMMITMENT_MODELS.items():
            score = sum(3 if z in model["zones"] else 0 for z in top_zone_ids)
            if score > 0:
                model_scores[m_id] = score
        top_commitments = sorted(model_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        commitment_output = []
        for m_id, _ in top_commitments:
            m = COMMITMENT_MODELS[m_id]
            # Selecionar frase-síntese do modelo
            commitment_output.append({
                "model_id": m_id,
                "title": m["title"],
                "zones": m["zones"],
                "theme": m["keywords"][0] if m["keywords"] else ""
            })

        alerts = []
        alert_sig = ""
        for z in perception_zones:
            if z["facial_dissonance_detected"] and z["dissonance_details"]:
                au_list = ", ".join(z["dissonance_details"]["active_aus"])
                alert_msg = f"Alerta: Dissonância crítica detectada na Zona {z['zone']}. O rosto contrasta a agressividade da voz. [{au_list}]"
                alerts.append(alert_msg)
                alert_sig += f"{z['zone']}-{au_list};"

        if alert_sig and alert_sig == self.last_alert_signature:
            alerts = []
        elif alert_sig:
            self.last_alert_signature = alert_sig

        # O TOM NAO E APURADO. Nao ha algoritmo para ele.
        #
        # Ate 02/09/2026 esta linha era um np.random.choice entre seis rotulos,
        # SEM CONDICAO NENHUMA — nao era o modo simulado, era sempre, inclusive
        # com audio real. O valor sorteado chegava ao painel do profissional, ao
        # relatorio, a AREA DO PROPRIO PACIENTE, ao acervo anonimizado do
        # Data-Froid e ao prompt da IA que redige os resumos.
        #
        # Um dado de seis faces apresentado como leitura clinica. O comentario
        # ao lado ja admitia "placeholder", mas placeholder que chega a tela sem
        # rotulo deixa de ser placeholder e vira afirmacao.
        #
        # Categorizar tom exigiria fundir ritmo de fala, semantica do que foi
        # dito e energia da voz sob um criterio definido e defensavel. Esse
        # criterio nao existe no FROID hoje, e inventa-lo aqui seria trocar um
        # numero aleatorio por um numero arbitrario — pior, porque o segundo
        # parece fundamentado.
        #
        # Vazio ate existir. Campo sem medida se declara vazio.
        emotional_tone = ""
        tom_para_amostra = "neutro"
        snippets = {
            "neutro": ["Estou pensando sobre isso...", "Não sei exatamente como me sinto.", "É complicado explicar."],
            "ansioso": ["Sinto que algo vai dar errado...", "Não consigo parar de pensar nisso.", "Meu peito aperta quando lembro."],
            "triste": ["Às vezes parece que não adianta...", "As coisas perderam a cor.", "Sinto falta de como era antes."],
            "irritado": ["Não aguento mais essa situação.", "Parece que ninguém me escuta.", "Isso me deixa furioso."],
            "alegre": ["Tive uma boa notícia essa semana.", "Estou me sentindo mais leve.", "Consegui resolver algo importante."],
            "suprimido": ["Está tudo bem.", "Não tem nada demais.", "Prefiro não falar sobre isso agora."],
        }
        # A frase de amostra e do gerador simulado e nunca foi leitura de nada;
        # segue com um tom neutro fixo, ja que o campo real agora e vazio.
        # Vazio: a frase de amostra existia para povoar a tela antes de haver
        # transcricao de verdade, e o painel ja a apaga ao receber. Sortear uma
        # fala de paciente que ninguem disse nao tem uso legitimo restante.
        transcription_snippet = ""
        # Sem o `+ np.random.randint(0, 20)` que somava ate 19 palavras
        # imaginarias por tick ao total da sessao.
        total_words = sum(self.word_windows)

        # DR = Dynamic Repouso = média das 12 baselines
        dr_value = round(float(np.mean(self.baseline_energy)), 3)
        baseline_mean = float(np.mean(self.baseline_energy))
        if real and "mfcc7" in real:
            # MFCC reais (coeficientes cepstrais medidos do PCM). Os deltas e o
            # alerta espástico passam a refletir a voz de fato.
            mfcc7 = round(float(real.get("mfcc7") or 0.0), 4)
            mfcc9 = round(float(real.get("mfcc9") or 0.0), 4)
            # Calibra as baselines de voz real nos primeiros REAL_VOICE_BASELINE
            # ticks COM voz medida — não importa se a baseline espectral já
            # travou (o microfone do paciente pode ter entrado mais tarde).
            REAL_VOICE_BASELINE = 30
            if self.real_voice_baseline_ticks < REAL_VOICE_BASELINE:
                a = 0.1
                self.baseline_mfcc7_real = (1 - a) * self.baseline_mfcc7_real + a * mfcc7 if self.baseline_mfcc7_real else mfcc7
                self.baseline_mfcc9_real = (1 - a) * self.baseline_mfcc9_real + a * mfcc9 if self.baseline_mfcc9_real else mfcc9
                # Baselines de repouso para as métricas base de dissonância.
                rf0 = float(real.get("f0_mean") or 0.0)
                if rf0 > 0.0:
                    self.baseline_f0_real = (1 - a) * self.baseline_f0_real + a * rf0 if self.baseline_f0_real else rf0
                rloud = real.get("loudness_dbfs")
                if rloud is not None:
                    rloud = float(rloud)
                    self.baseline_loudness_real = (1 - a) * self.baseline_loudness_real + a * rloud if self.baseline_loudness_real else rloud
                rzcr = float(real.get("zcr") or 0.0)
                if rzcr > 0.0:
                    self.baseline_zcr_real = (1 - a) * self.baseline_zcr_real + a * rzcr if self.baseline_zcr_real else rzcr
                # Bandas de modulacao medidas, em PERCENTUAL da energia total.
                for chave, campo in (
                    ("sub_5_12", "baseline_sub_5_12_real"),
                    ("sub_12_20", "baseline_sub_12_20_real"),
                    ("sub_20_40", "baseline_sub_20_40_real"),
                ):
                    bruto = real.get(chave)
                    if bruto is not None:
                        pct = float(bruto) * 100.0
                        atual = getattr(self, campo)
                        setattr(self, campo, (1 - a) * atual + a * pct if atual else pct)
                r85 = real.get("energy_85_165")
                if r85 is not None:
                    r85 = float(r85)
                    self.baseline_energy_85_165_real = (
                        (1 - a) * self.baseline_energy_85_165_real + a * r85
                        if self.baseline_energy_85_165_real
                        else r85
                    )
                self.real_voice_baseline_ticks += 1
        else:
            mfcc7 = round(float(np.clip(np.mean(voice_spectral_12[4:8]) - baseline_mean * 0.12, 0.0, 25.0)), 3)
            mfcc9 = round(float(np.clip(np.mean(voice_spectral_12[6:10]) - baseline_mean * 0.08, 0.0, 25.0)), 3)
        mfcc7_delta = round(float(mfcc7 - (self.previous_mfcc7 if self.previous_mfcc7 is not None else mfcc7)), 4)
        mfcc9_delta = round(float(mfcc9 - (self.previous_mfcc9 if self.previous_mfcc9 is not None else mfcc9)), 4)
        mfcc7_delta_delta = round(float(mfcc7_delta - self.previous_delta_mfcc7), 4)
        mfcc9_delta_delta = round(float(mfcc9_delta - self.previous_delta_mfcc9), 4)
        # As derivadas comparam a janela atual com a anterior — e so fazem
        # sentido se as duas vierem da MESMA fonte. Antes, `previous_*` era
        # atualizado sempre, entao o primeiro tick com voz real subtraia MFCC
        # medido de um proxy espectral GERADO: duas grandezas que nao se
        # comparam, e o pico resultante alimentava o alerta de contracao
        # espastica. Trocar de ramo agora zera a referencia em vez de produzir
        # uma diferenca falsa.
        _ramo = "real" if (real and "mfcc7" in real) else "proxy"
        if _ramo != self.previous_mfcc_source:
            self.previous_mfcc7 = None
            self.previous_mfcc9 = None
            # Nomes reais dos campos: `previous_delta_*`, e o padrao deles e
            # 0.0, nao None. Zerar assim faz a primeira delta-delta apos a
            # troca de ramo valer a propria delta, em vez de uma diferenca
            # contra a derivada de outra fonte.
            self.previous_delta_mfcc7 = 0.0
            self.previous_delta_mfcc9 = 0.0
        self.previous_mfcc_source = _ramo
        self.previous_mfcc7 = mfcc7
        self.previous_mfcc9 = mfcc9
        self.previous_delta_mfcc7 = mfcc7_delta
        self.previous_delta_mfcc9 = mfcc9_delta
        # Limiar da memória de cálculo: pico persistente na aceleração cepstral
        # (|ΔΔMFCC9| > 1.8) sinaliza contração espástica involuntária das cordas
        # vocais por ativação do sistema nervoso simpático.
        # Uma fonte so: ver LIMIAR_ESPASTICO_MFCC9 em froid_dissonance.
        mfcc9_spastic_threshold = froid_dissonance.LIMIAR_ESPASTICO_MFCC9
        mfcc9_spastic_alert = bool(abs(mfcc9_delta_delta) > mfcc9_spastic_threshold)
        # SUB-HARMONICOS MEDIDOS, nao mais derivados por formula propria.
        #
        # `froid_voice.extract_voice_features` sempre calculou estas tres bandas
        # de verdade — energia do espectro de MODULACAO do envelope nas faixas
        # 5-12, 12-20 e 20-40 Hz, normalizada pela energia total. Elas nunca
        # tiveram leitor: o motor preferia uma media ponderada de fatias do
        # vetor de 12 bandas, com pesos (0.7, 0.65, 0.55) e somas de desvio
        # padrao que nao vieram de lugar nenhum.
        #
        # Pior, a fatia da banda ALTA usava os indices mais BAIXOS
        # (`voice_spectral_12[1:4]`) — 20-40 Hz calculado a partir das bandas
        # mais graves do vetor.
        #
        # ESCALA: percentual da energia total de modulacao (0-100%). E de leitura
        # imediata — "8,3% da modulacao esta na faixa 5-12 Hz" — e dimensional-
        # mente honesta, ao contrario do 0-25 anterior, que nao tinha unidade.
        # Os indices DNA nao mudam de significado: sao desvio RELATIVO contra a
        # baseline, e ambas passam a viver na mesma regua nova.
        def _pct(chave: str) -> float:
            bruto = real.get(chave)
            return round(float(bruto) * 100.0, 3) if bruto is not None else 0.0

        subharmonic_5_12 = _pct("sub_5_12")
        subharmonic_12_20 = _pct("sub_12_20")
        subharmonic_20_40 = _pct("sub_20_40")
        energy_85_165 = round(float(real.get("energy_85_165") or 0.0), 6)
        if real and "mod_delta" in real:
            # Bandas neuroacústicas REAIS = espectro de MODULAÇÃO do envelope
            # (0.5-80 Hz), a interpretação física correta de "modulação vocal".
            spectral_delta = round(float(np.clip(real.get("mod_delta") or 0.0, 0.0, 1.0)), 3)
            spectral_theta = round(float(np.clip(real.get("mod_theta") or 0.0, 0.0, 1.0)), 3)
            spectral_alpha = round(float(np.clip(real.get("mod_alpha") or 0.0, 0.0, 1.0)), 3)
            spectral_beta = round(float(np.clip(real.get("mod_beta") or 0.0, 0.0, 1.0)), 3)
            spectral_gamma = round(float(np.clip(real.get("mod_gamma") or 0.0, 0.0, 1.0)), 3)
        else:
            spectral_delta = round(float(np.clip(np.mean(voice_spectral_12[0:2]) / 25.0, 0.0, 1.0)), 3)
            spectral_theta = round(float(np.clip(np.mean(voice_spectral_12[2:4]) / 25.0, 0.0, 1.0)), 3)
            spectral_alpha = round(float(np.clip(np.mean(voice_spectral_12[4:6]) / 25.0, 0.0, 1.0)), 3)
            spectral_beta = round(float(np.clip(np.mean(voice_spectral_12[6:9]) / 25.0, 0.0, 1.0)), 3)
            spectral_gamma = round(float(np.clip(np.mean(voice_spectral_12[9:12]) / 25.0, 0.0, 1.0)), 3)
        spectral_index = round(float(np.clip(np.mean([spectral_delta, spectral_theta, spectral_alpha, spectral_beta, spectral_gamma]), 0.0, 1.0)), 3)
        if real and "zcr" in real:
            # Jitter e shimmer REAIS (perturbação de período e de amplitude
            # ciclo-a-ciclo) e ZCR real, medidos da forma de onda.
            jitter = round(float(np.clip(real.get("jitter") or 0.0, 0.0, 2.0)), 4)
            shimmer = round(float(np.clip(real.get("shimmer") or 0.0, 0.0, 2.0)), 4)
            zcr_value = round(float(real.get("zcr") or 0.0), 5)
            # `x or -120.0` e armadilha aqui: em Python `0.0 or -120.0` da
            # -120.0, e 0 dBFS e o sinal MAIS ALTO possivel (fundo de escala).
            # A guarda transformava o extremo superior no extremo inferior —
            # silencio absoluto — exatamente no pico que mais interessa.
            _loud = real.get("loudness_dbfs")
            loudness_dbfs = round(float(_loud), 2) if _loud is not None else -120.0
        else:
            jitter = round(float(np.clip(np.std(voice_spectral_12) / max(1.0, np.mean(voice_spectral_12)), 0.0, 2.0)), 3)
            shimmer = round(float(np.clip(np.mean(np.abs(np.diff(voice_spectral_12))) / max(1.0, np.mean(voice_spectral_12)), 0.0, 2.0)), 3)
            zcr_value = None
            loudness_dbfs = None
        # As baselines acompanham a mesma regua das medidas. Enquanto a EMA nao
        # tiver o primeiro valor, ela vale o proprio valor atual — o que zera o
        # desvio em vez de inventar um. Desvio contra referencia inexistente
        # seria numero sem significado.
        base_subharmonic_5_12 = self.baseline_sub_5_12_real or subharmonic_5_12
        base_subharmonic_12_20 = self.baseline_sub_12_20_real or subharmonic_12_20
        base_subharmonic_20_40 = self.baseline_sub_20_40_real or subharmonic_20_40
        base_energy_85_165 = self.baseline_energy_85_165_real or energy_85_165
        eps = 1e-9
        dna_infrasound = float(np.clip((subharmonic_5_12 - base_subharmonic_5_12) / (base_subharmonic_5_12 + eps), 0.0, 1.0))
        current_limbic_ratio = subharmonic_12_20 / (subharmonic_5_12 + subharmonic_12_20 + eps)
        baseline_limbic_ratio = base_subharmonic_12_20 / (base_subharmonic_5_12 + base_subharmonic_12_20 + eps)
        dna_limbic = float(np.clip((current_limbic_ratio - baseline_limbic_ratio) / (baseline_limbic_ratio + eps), 0.0, 1.0))
        dna_neurogenic = float(np.clip((subharmonic_20_40 - base_subharmonic_20_40) / (base_subharmonic_20_40 + eps), 0.0, 1.0))
        dna_basal = float(np.clip((energy_85_165 - base_energy_85_165) / (base_energy_85_165 + eps), 0.0, 1.0))
        facial_multiplier = 2.5 if has_dissonance else 1.0
        au_suppression = any(
            details and any(str(au).upper().replace("AU", "") in {"23", "24"} for au in details.get("active_aus", []))
            for details in facs_details.values()
        )
        # O nome dizia ZCR e a formula usa JITTER — o ZCR real esta calculado
        # logo acima e nunca entrou aqui. Renomeado para o que de fato faz, sem
        # mudar o valor: trocar a formula mudaria a escala de
        # dna_dissociative_shutdown e a comparabilidade com o que ja foi
        # gravado, e essa e decisao clinica, nao de engenharia. Fica registrado
        # como pergunta aberta: o pretendido era queda de ZCR ou estabilidade
        # de jitter?
        estabilidade_de_jitter = float(np.clip(1.0 - (jitter / 2.0), 0.0, 1.0))
        dna_flooding = float(np.clip((dna_infrasound * 0.55 + dna_basal * 0.45) * (facial_multiplier / 2.5), 0.0, 1.0))
        dna_shutdown = float(
            np.clip(
                dna_infrasound * (1.0 - (ipm_score / 100.0)) * estabilidade_de_jitter,
                0.0,
                1.0,
            )
        )
        dna_somato = float(np.clip(((dna_infrasound + dna_basal) / 2.0) * (1.0 + (facial_multiplier - 1.0) * (1.0 if au_suppression else 0.0)) / 2.5, 0.0, 1.0))
        dna_index = float(np.clip(np.mean([dna_infrasound, dna_limbic, dna_neurogenic, dna_basal, dna_flooding, dna_shutdown, dna_somato]), 0.0, 1.0))
        # Fonte única de velocidade de fala: alinhado ao WPM consolidado da
        # janela de 10 min, em vez de uma terceira fórmula divergente.
        speech_rate_proxy = round(float(words_per_minute_10m), 1)
        clinical_insight = (
            "Coerência preservada" if coherence_status == "COERENTE" else
            "Ativação vocal/gestual com risco de dissonância" if has_dissonance else
            "Baseline em calibração"
        )

        # -----------------------------------------------------------------
        # Motor de DISSONÂNCIAS EVIDENTES: cada marcador real é confrontado
        # com sua métrica base (banda mín/máx). Quando DUAS OU MAIS ultrapassam
        # simultaneamente, o evento é sinalizado para a listagem detalhada.
        # -----------------------------------------------------------------
        voice_real = bool(real and "zcr" in real)
        dissonance_snapshot = {
            "voice_real": voice_real,
            "baseline_locked": self.baseline_locked,
            # Baseline de voz real concluída (>= 30 ticks com voz medida). Só
            # então os marcadores relativos à baseline do paciente avaliam.
            "voice_baseline_ready": self.real_voice_baseline_ticks >= 30,
            "jitter": jitter,
            "shimmer": shimmer,
            "f0_mean": float(self.latest_f0_mean),
            "f0_var": float(self.latest_f0_std),
            "f0_voiced_ratio": float(self.latest_f0_voiced_ratio),
            "baseline_f0": float(self.baseline_f0_real),
            "loudness_dbfs": loudness_dbfs,
            "baseline_loudness": self.baseline_loudness_real if self.baseline_loudness_real else None,
            "zcr": zcr_value,
            "baseline_zcr": float(self.baseline_zcr_real),
            "mfcc7_delta_delta": mfcc7_delta_delta,
            "mfcc9_delta_delta": mfcc9_delta_delta,
            "dna_autonomic_flooding": dna_flooding,
            "dna_dissociative_shutdown": dna_shutdown,
            "dna_somatoaffective_dissonance": dna_somato,
            # Desvio VOCAL puro (sem o multiplicador facial M_fac): impede que um
            # único evento facial dispare, ao mesmo tempo, o marcador facial e o
            # de zona extrema (dupla contagem correlacionada).
            "zone_deviations": [float(d) for d in raw_deviations],
            "ipm_score": float(ipm_score),
            # Contradição facial-vocal REAL (só conta quando vinda de blendshapes
            # medidos; o mock não alimenta a métrica base de dissonância facial).
            "facial_real": facs_source == "real_facs",
            "facial_dissonance_count": (
                sum(1 for f in facs_dissonance_flags.values() if f)
                if facs_source == "real_facs"
                else 0
            ),
        }
        dissonance_event = froid_dissonance.evaluate(dissonance_snapshot)
        # Confirmação temporal: só é "confirmada" a dissonância evidente (>= 1
        # marcador) que se sustenta em 2 dos últimos 3 ticks — is_multi_dissonance
        # (2+ marcadores em 2+ categorias) continua calculado à parte, como
        # destaque de maior confiança, não como critério de registro.
        self.dissonance_history.append(bool(dissonance_event["has_dissonance"]))
        if len(self.dissonance_history) > froid_dissonance.CONFIRM_WINDOW:
            self.dissonance_history.pop(0)
        dissonance_event["confirmed"] = bool(
            dissonance_event["has_dissonance"]
            and froid_dissonance.confirm(self.dissonance_history)
        )
        dissonance_event["sustained_ticks"] = int(sum(self.dissonance_history))
        # Zona de maior desvio, para rótulo do registro na listagem.
        peak_zone = max(perception_zones, key=lambda z: abs(z["deviation_score"]))
        dissonance_event["peak_zone"] = peak_zone["zone"]
        dissonance_event["peak_zone_tema"] = peak_zone["tema"]
        dissonance_event["coherence_status"] = coherence_status

        return {
            "session_id": self.session_id,
            "timestamp_ms": int(time.time() * 1000),
            "ipm_score": round(ipm_score, 1),
            "idm_score": round(idm_signed, 3),
            "coherence_status": coherence_status,
            "global_energy": {
                "cor_plot": global_color.value,
                "descricao": self.mapper.color_scale[global_color],
            },
            "perception_zones": perception_zones,
            "realtime_alerts": alerts,
            "dissonance_event": dissonance_event,
            "dr_value": dr_value,
            "audio_meta": {
                "words_per_window": words_this_window,
                "words_per_minute_10m": round(words_per_minute_10m, 1),
                "total_words_session": int(total_words),
                "emotional_tone": emotional_tone,
                "transcription_snippet": transcription_snippet,
                "session_theme": session_theme,
                "theme_minute_mark": (minutes_elapsed // 10) * 10,
                "bioacoustic_window_ms": 1000,
                "mfcc7": mfcc7,
                "mfcc9": mfcc9,
                "mfcc7_delta": mfcc7_delta,
                "mfcc9_delta": mfcc9_delta,
                "mfcc7_delta_delta": mfcc7_delta_delta,
                "mfcc9_delta_delta": mfcc9_delta_delta,
                "mfcc9_delta_delta_spastic_threshold": mfcc9_spastic_threshold,
                "mfcc9_delta_delta_spastic_alert": mfcc9_spastic_alert,
                # F0 real medida da voz do paciente (YIN sobre PCM do navegador).
                "f0_mean": round(self.latest_f0_mean, 2),
                "f0_var": round(self.latest_f0_std, 2),
                "f0_voiced_ratio": round(self.latest_f0_voiced_ratio, 3),
                "f0_source": "yin_pcm" if self.latest_f0_mean > 0 else "pending_audio",
                "baseline_mfcc7": round(self.baseline_mfcc7_real, 4)
                if (real and "mfcc7" in real and self.baseline_mfcc7_real)
                else round(float(np.clip(baseline_mean * 0.12, 0.0, 25.0)), 3),
                "baseline_mfcc9": round(self.baseline_mfcc9_real, 4)
                if (real and "mfcc7" in real and self.baseline_mfcc9_real)
                else round(float(np.clip(baseline_mean * 0.08, 0.0, 25.0)), 3),
                "spectral_delta_0_4hz": spectral_delta,
                "spectral_theta_4_8hz": spectral_theta,
                "spectral_alpha_8_12hz": spectral_alpha,
                "spectral_beta_12_30hz": spectral_beta,
                "spectral_gamma_30_80hz": spectral_gamma,
                "spectral_band_index": spectral_index,
                "subharmonic_energy_5_12hz": subharmonic_5_12,
                "subharmonic_energy_12_20hz": subharmonic_12_20,
                "subharmonic_energy_20_40hz": subharmonic_20_40,
                "energy_85_165hz": energy_85_165,
                "dna_infrasound_nuclear": round(dna_infrasound, 3),
                "dna_limbic_modulation": round(dna_limbic, 3),
                "dna_neurogenic_resonance": round(dna_neurogenic, 3),
                "dna_vocal_basal_tension": round(dna_basal, 3),
                "dna_autonomic_flooding": round(dna_flooding, 3),
                "dna_dissociative_shutdown": round(dna_shutdown, 3),
                "dna_somatoaffective_dissonance": round(dna_somato, 3),
                "dna_subharmonic_index": round(dna_index, 3),
                "dna_baseline_locked": self.baseline_locked,
                "dna_facial_multiplier": facial_multiplier,
                "jitter": jitter,
                "shimmer": shimmer,
                "jitter_proxy_index": jitter,
                "shimmer_proxy_index": shimmer,
                "zcr": zcr_value,
                "loudness_dbfs": loudness_dbfs,
                # "mock" nao existe mais como procedencia: o gerador foi
                # removido, e o que resta quando nao ha voz medida nao e
                # simulacao — e ausencia. Este era o ultimo ponto do motor que
                # ainda declarava a palavra antiga.
                "voice_features_source": (
                    "real_pcm" if (real and "zcr" in real) else "sem_apuracao"
                ),
                "facs_source": facs_source,
                "facial_action_units": self.latest_facial_aus if facs_source == "real_facs" else None,
                "jitter_unit": "internal_proxy_0_2_spectral_dispersion",
                "shimmer_unit": "internal_proxy_0_2_spectral_step_variation",
                # A unidade viaja com o numero: sem ela, 8.3 podia ser o proxy
                # antigo (escala 0-25 sem unidade) ou o percentual novo, e nada
                # na tela distinguiria os dois.
                "subharmonic_unit": "percent_of_modulation_energy",
                "energy_85_165_unit": "fraction_of_spectral_power",
                "spectral_band_context": "voice_modulation_not_eeg",
                "speech_rate_proxy": speech_rate_proxy,
                "clinical_insight": clinical_insight,
                "baseline_locked": self.baseline_locked,
                # Progresso real da calibração (0-60 ticks COM voz real). Torna
                # visível que a baseline avança só quando há voz medida — sem
                # isso, uma sessão sem áudio parecia "calibrando" para sempre.
                "baseline_progress": len(self.baseline_buffer),
                "baseline_target": 60,
            },
            "commitment_models": commitment_output,
        }

# O GERADOR SAIU DAQUI.
#
# `MockBiometricStream` produzia o vetor espectral de 12 bandas por ruido
# gaussiano com picos sorteados, e a dissonancia facial por moeda viciada de
# 10% e 8% — esta ultima com texto clinico ja escrito, que chegava a tela do
# profissional sem nenhuma marca de origem.
#
# Determinacao do dono do produto em 02/09/2026: proibido simular. Quando nao
# ha capacidade de apuracao, o sistema INFORMA que nao ha.
#
# A classe nao foi mantida nem sob bandeira: codigo que sabe inventar numero
# plausivel e uma arma carregada em cima da mesa. Ver `_payload_sem_apuracao`.
