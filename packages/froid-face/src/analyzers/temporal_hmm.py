"""
FROID Face - HMM Temporal (v4.0 Científico)
4 estados (neutral→onset→apex→offset) + Viterbi + REGRA DO APEX

REGRA FUNDAMENTAL: Expressão presente SE E SOMENTE SE apex detectado.

Fonte: [3D FACTS.pdf, Sec II.D & Table I]
"""

import numpy as np
from typing import Dict, List
from src.config import HMMParams, ClinicalThresholds


class ExpressionHMM:
    """
    Modelagem temporal de expressões faciais via HMM 4 estados.
    
    Estados: neutral(0), onset(1), apex(2), offset(3)
    Decodificação: Algoritmo de Viterbi
    Emissões: Gaussianas calibradas por emoção
    """

    def __init__(self):
        self.params = HMMParams()
        self.T = np.array(self.params.TRANSITION_MATRIX)
        self.pi = np.array(self.params.INITIAL_PROBS)
        self.states = self.params.STATES
        self.n_states = len(self.states)
        self.onset_buffer = []
        self.offset_buffer = []

    def update(self, onset_score, offset_score, emotion="happy"):
        """Adiciona scores ao buffer e decodifica quando janela está cheia."""
        self.onset_buffer.append(onset_score)
        self.offset_buffer.append(offset_score)
        
        window_size = self.params.WINDOW_WIDTHS.get(emotion, 12)
        
        if len(self.onset_buffer) > window_size:
            self.onset_buffer = self.onset_buffer[-window_size:]
            self.offset_buffer = self.offset_buffer[-window_size:]
        
        if len(self.onset_buffer) >= 4:
            path = self.viterbi_decode(
                np.array(self.onset_buffer),
                np.array(self.offset_buffer)
            )
            result = self.classify_expression(path)
            result["current_phase"] = self.states[path[-1]]
            result["viterbi_sequence"] = [self.states[s] for s in path.tolist()]
            return result
        
        return {
            "detected": False,
            "current_phase": "neutral",
            "viterbi_sequence": [],
            "onset_frame": None,
            "apex_frame": None,
            "offset_frame": None,
            "duration_ms": 0,
            "is_microexpression": False,
            "apex_confidence": 0.0
        }

    def viterbi_decode(self, onset_scores, offset_scores):
        """Algoritmo de Viterbi para decodificação de estados."""
        T_len = len(onset_scores)
        N = self.n_states
        
        delta = np.zeros((T_len, N))
        psi = np.zeros((T_len, N), dtype=int)
        
        mu_on = {"neutral": 0.2, "onset": 0.75, "apex": 0.5, "offset": 0.2}
        mu_off = {"neutral": 0.2, "onset": 0.2, "apex": 0.3, "offset": 0.8}
        sigma = 0.15
        
        for s in range(N):
            state_name = self.states[s]
            p_on = self._gaussian_pdf(onset_scores[0], mu_on[state_name], sigma)
            p_off = self._gaussian_pdf(offset_scores[0], mu_off[state_name], sigma)
            delta[0, s] = np.log(self.pi[s] + 1e-9) + np.log(p_on * p_off + 1e-9)
        
        for t in range(1, T_len):
            for s in range(N):
                trans_probs = delta[t - 1, :] + np.log(self.T[:, s] + 1e-9)
                psi[t, s] = int(np.argmax(trans_probs))
                
                state_name = self.states[s]
                p_on = self._gaussian_pdf(onset_scores[t], mu_on[state_name], sigma)
                p_off = self._gaussian_pdf(offset_scores[t], mu_off[state_name], sigma)
                
                delta[t, s] = float(np.max(trans_probs)) + np.log(p_on * p_off + 1e-9)
        
        path = np.zeros(T_len, dtype=int)
        path[T_len - 1] = int(np.argmax(delta[T_len - 1, :]))
        
        for t in range(T_len - 2, -1, -1):
            path[t] = psi[t + 1, path[t + 1]]
        
        return path

    def classify_expression(self, path, fps=30):
        """Classifica expressão baseado na sequência Viterbi. REGRA: apex obrigatório."""
        apex_frames = np.where(path == 2)[0]
        
        if len(apex_frames) == 0:
            return {
                "detected": False,
                "onset_frame": None,
                "apex_frame": None,
                "offset_frame": None,
                "duration_ms": 0,
                "is_microexpression": False,
                "apex_confidence": 0.0
            }
        
        path_list = path.tolist()
        
        if 1 in path_list:
            onset_frame = path_list.index(1)
        else:
            onset_frame = int(apex_frames[0])
        
        if 3 in path_list:
            offset_frame = len(path_list) - 1 - path_list[::-1].index(3)
        else:
            offset_frame = int(apex_frames[-1])
        
        duration_frames = offset_frame - onset_frame + 1
        duration_ms = int(duration_frames * (1000 / fps))
        apex_confidence = len(apex_frames) / len(path)
        
        return {
            "detected": True,
            "onset_frame": onset_frame,
            "apex_frame": int(apex_frames[len(apex_frames) // 2]),
            "offset_frame": offset_frame,
            "duration_ms": duration_ms,
            "is_microexpression": duration_ms < ClinicalThresholds.MICROEXPRESSION_MS,
            "apex_confidence": round(float(apex_confidence), 3)
        }

    def _gaussian_pdf(self, x, mu, sigma):
        """Função densidade de probabilidade gaussiana."""
        return float(np.exp(-0.5 * ((x - mu) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi)))

    def reset(self):
        """Limpa buffers para nova expressão."""
        self.onset_buffer = []
        self.offset_buffer = []
