import numpy as np
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

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
    last_alert_signature: str = ""
    tick_count: int = 0
    word_windows: List[int] = field(default_factory=list)  # palavras por janela de ~500ms

    def process_tick(self, voice_spectral_12, facs_dissonance_flags, facs_details):
        self.tick_count += 1
        if not self.baseline_locked:
            self.baseline_buffer.append(voice_spectral_12.copy())
            if len(self.baseline_buffer) >= 60:
                stacked = np.stack(self.baseline_buffer)
                self.baseline_energy = np.mean(stacked, axis=0)
                self.baseline_locked = True
            else:
                partial = np.mean(np.stack(self.baseline_buffer), axis=0) if self.baseline_buffer else np.ones(12) * 5.0
                self.baseline_energy = partial

        if self.baseline_energy is None:
            self.baseline_energy = np.ones(12) * 5.0

        perception_zones = []
        global_deviations = []
        has_critical_dissonance = False
        has_dissonance = False

        for zone_idx in range(1, 13):
            v_energy = float(voice_spectral_12[zone_idx - 1])
            b_energy = float(self.baseline_energy[zone_idx - 1])
            d_flag = facs_dissonance_flags.get(zone_idx, False)
            d_details = facs_details.get(zone_idx, None)

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
        ipm_score = float(np.clip(50.0 + (mean_abs_dev * 15.0), 0.0, 100.0))

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
        if mean_vocal > mean_baseline * 1.3 and not any_facs_active:
            coherence_status = "EMBOTAMENTO"
        elif has_critical_dissonance:
            coherence_status = "DISSONANCIA ALTA"
        elif has_dissonance:
            coherence_status = "DISSONANCIA"
        elif not self.baseline_locked:
            coherence_status = "NEUTRO"
        else:
            coherence_status = "COERENTE"

        # Simulação: palavras por janela (~12 palavras/min em média = 6 por 500ms com variação)
        words_this_window = int(np.random.poisson(8))
        self.word_windows.append(words_this_window)
        # Manter últimas 1200 janelas = ~10 minutos (500ms * 1200 = 600s)
        if len(self.word_windows) > 1200:
            self.word_windows.pop(0)

        # Média de palavras por minuto nos últimos 10 minutos
        words_per_minute_10m = sum(self.word_windows) / max(1, len(self.word_windows)) * 2 * 60  # *2 (janelas/segundo) *60 (segundos/min)

        # Tema da sessão (simulado — a cada 10 min mudaria via análise semântica)
        minutes_elapsed = self.tick_count // 120  # 120 ticks = 60s
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

        # Transcrição simulada (placeholder para gpt-realtime-whisper)
        emotional_tone = np.random.choice(["neutro", "ansioso", "triste", "irritado", "alegre", "suprimido"])
        snippets = {
            "neutro": ["Estou pensando sobre isso...", "Não sei exatamente como me sinto.", "É complicado explicar."],
            "ansioso": ["Sinto que algo vai dar errado...", "Não consigo parar de pensar nisso.", "Meu peito aperta quando lembro."],
            "triste": ["Às vezes parece que não adianta...", "As coisas perderam a cor.", "Sinto falta de como era antes."],
            "irritado": ["Não aguento mais essa situação.", "Parece que ninguém me escuta.", "Isso me deixa furioso."],
            "alegre": ["Tive uma boa notícia essa semana.", "Estou me sentindo mais leve.", "Consegui resolver algo importante."],
            "suprimido": ["Está tudo bem.", "Não tem nada demais.", "Prefiro não falar sobre isso agora."],
        }
        transcription_snippet = np.random.choice(snippets.get(emotional_tone, snippets["neutro"]))
        total_words = sum(self.word_windows) + np.random.randint(0, 20)

        # DR = Dynamic Repouso = média das 12 baselines
        dr_value = round(float(np.mean(self.baseline_energy)), 3)
        baseline_mean = float(np.mean(self.baseline_energy))
        mfcc7 = round(float(np.clip(np.mean(voice_spectral_12[4:8]) - baseline_mean * 0.12, 0.0, 25.0)), 3)
        mfcc9 = round(float(np.clip(np.mean(voice_spectral_12[6:10]) - baseline_mean * 0.08, 0.0, 25.0)), 3)
        subharmonic_5_12 = round(float(np.clip((np.mean(voice_spectral_12[4:8]) * 0.7) + (np.std(voice_spectral_12) * 0.2), 0.0, 25.0)), 3)
        subharmonic_12_20 = round(float(np.clip((np.mean(voice_spectral_12[8:12]) * 0.65) + (np.std(voice_spectral_12) * 0.15), 0.0, 25.0)), 3)
        jitter = round(float(np.clip(np.std(voice_spectral_12) / max(1.0, np.mean(voice_spectral_12)), 0.0, 2.0)), 3)
        shimmer = round(float(np.clip(np.mean(np.abs(np.diff(voice_spectral_12))) / max(1.0, np.mean(voice_spectral_12)), 0.0, 2.0)), 3)
        speech_rate_proxy = round(float(np.clip(95.0 + (words_this_window * 4.5) + (mfcc7 * 1.1), 70.0, 180.0)), 1)
        clinical_insight = (
            "Coerência preservada" if coherence_status == "COERENTE" else
            "Ativação vocal/gestual com risco de dissonância" if has_dissonance else
            "Baseline em calibração"
        )

        return {
            "session_id": self.session_id,
            "timestamp_ms": int(time.time() * 1000),
            "ipm_score": round(ipm_score, 1),
            "coherence_status": coherence_status,
            "global_energy": {
                "cor_plot": global_color.value,
                "descricao": self.mapper.color_scale[global_color],
            },
            "perception_zones": perception_zones,
            "realtime_alerts": alerts,
            "dr_value": dr_value,
            "audio_meta": {
                "words_per_window": words_this_window,
                "words_per_minute_10m": round(words_per_minute_10m, 1),
                "total_words_session": int(total_words),
                "emotional_tone": emotional_tone,
                "transcription_snippet": transcription_snippet,
                "session_theme": session_theme,
                "theme_minute_mark": (minutes_elapsed // 10) * 10,
                "mfcc7": mfcc7,
                "mfcc9": mfcc9,
                "baseline_mfcc7": round(float(np.clip(baseline_mean * 0.12, 0.0, 25.0)), 3),
                "baseline_mfcc9": round(float(np.clip(baseline_mean * 0.08, 0.0, 25.0)), 3),
                "subharmonic_energy_5_12hz": subharmonic_5_12,
                "subharmonic_energy_12_20hz": subharmonic_12_20,
                "jitter": jitter,
                "shimmer": shimmer,
                "speech_rate_proxy": speech_rate_proxy,
                "clinical_insight": clinical_insight,
                "baseline_locked": self.baseline_locked,
            },
            "commitment_models": commitment_output,
        }

class MockBiometricStream:
    @staticmethod
    def generate_voice_spectral():
        base = np.array([4.2, 5.1, 4.8, 5.5, 4.0, 6.2, 5.0, 4.5, 5.8, 4.3, 5.2, 4.9])
        noise = np.random.normal(0, 1.2, 12)
        spike = np.zeros(12)
        if np.random.random() < 0.15:
            target = np.random.choice([6, 7, 11, 12])
            spike[target - 1] = np.random.uniform(4.0, 10.0)
        return np.clip(base + noise + spike, 0.5, 25.0)

    @staticmethod
    def generate_facs_dissonance():
        flags = {i: False for i in range(1, 13)}
        details = {i: None for i in range(1, 13)}
        if np.random.random() < 0.10:
            flags[7] = True
            details[7] = {
                "active_aus": ["AU12", "AU23", "AU24"],
                "report": "Supressão de Aversão: Compressão labial severa cruzada com sorriso social falso."
            }
        elif np.random.random() < 0.08:
            flags[12] = True
            details[12] = {
                "active_aus": ["AU4", "AU7"],
                "report": "Conflito interno: Sobrancelhas contraídas com olhos semicerrados durante fala neutra."
            }
        return flags, details
