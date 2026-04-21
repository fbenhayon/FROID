"""
FROID Face - Modelagem Temporal HMM
4 estados (neutral→onset→apex→offset) + decodificação Viterbi

REGRA FUNDAMENTAL: Expressão presente SE E SOMENTE SE apex detectado.

Fonte: API Facial Parte 4 (temporal_hmm.py) + [3D FACTS.pdf, Sec II.D]
"""

import numpy as np
from scipy.stats import norm
from typing import Dict, List, Optional
from src.config import (
    HMM_STATES,
    HMM_INITIAL_PROBS,
    HMM_TRANSITION_MATRIX,
    HMM_EMISSION_PARAMS,
)


class ExpressionHMM:
    """
    Modelagem temporal de expressões via HMM 4 estados.
    
    Estados: neutral(0), onset(1), apex(2), offset(3)
    Decodificação: Algoritmo de Viterbi
    Emissões: Gaussianas calibradas por [3D FACTS.pdf, Table I]
    """

    def __init__(self):
        self.states = HMM_STATES
        self.n_states = len(self.states)
        self.T = np.array(HMM_TRANSITION_MATRIX)
        self.pi = np.array(HMM_INITIAL_PROBS)
        self.emission_params = HMM_EMISSION_PARAMS

        # Buffer para janela deslizante
        self.onset_buffer: List[float] = []
        self.offset_buffer: List[float] = []
        self.window_size = 16  # [3D FACTS.pdf]: window width ótima 4-16 frames

    def update(self, onset_score: float, offset_score: float) -> Dict:
        """
        Adiciona scores ao buffer e decodifica quando janela está cheia.
        
        Args:
            onset_score: Score do classificador onset (0-1)
            offset_score: Score do classificador offset (0-1)
            
        Returns:
            Dict com fase atual, expressão detectada e métricas
        """
        self.onset_buffer.append(onset_score)
        self.offset_buffer.append(offset_score)

        # Manter janela deslizante
        if len(self.onset_buffer) > self.window_size:
            self.onset_buffer = self.onset_buffer[-self.window_size:]
            self.offset_buffer = self.offset_buffer[-self.window_size:]

        # Decodificar quando temos frames suficientes
        if len(self.onset_buffer) >= 4:  # Mínimo 4 frames
            path = self.viterbi_decode(
                np.array(self.onset_buffer),
                np.array(self.offset_buffer),
            )
            result = self.classify_expression(path)
            result["current_phase"] = self.states[path[-1]]
            result["viterbi_sequence"] = path.tolist()
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
        }

    def viterbi_decode(self, onset_scores: np.ndarray, offset_scores: np.ndarray) -> np.ndarray:
        """
        Decodificação de Viterbi para sequência de estados mais provável.
        [3D FACTS.pdf, Sec II.D, Eq. 1-2]
        """
        T_len = len(onset_scores)
        N = self.n_states
        delta = np.zeros((T_len, N))
        psi = np.zeros((T_len, N), dtype=int)

        # Inicialização
        for s in range(N):
            p_on = norm.pdf(
                onset_scores[0],
                self.emission_params["onset"][self.states[s]][0],
                self.emission_params["onset"][self.states[s]][1],
            )
            p_off = norm.pdf(
                offset_scores[0],
                self.emission_params["offset"][self.states[s]][0],
                self.emission_params["offset"][self.states[s]][1],
            )
            delta[0, s] = np.log(self.pi[s] + 1e-10) + np.log(p_on * p_off + 1e-10)

        # Recursão
        for t in range(1, T_len):
            for s in range(N):
                trans_probs = delta[t - 1, :] + np.log(self.T[:, s] + 1e-10)
                psi[t, s] = int(np.argmax(trans_probs))

                p_on = norm.pdf(
                    onset_scores[t],
                    self.emission_params["onset"][self.states[s]][0],
                    self.emission_params["onset"][self.states[s]][1],
                )
                p_off = norm.pdf(
                    offset_scores[t],
                    self.emission_params["offset"][self.states[s]][0],
                    self.emission_params["offset"][self.states[s]][1],
                )
                delta[t, s] = float(np.max(trans_probs)) + np.log(p_on * p_off + 1e-10)

        # Backtracking
        path = np.zeros(T_len, dtype=int)
        path[T_len - 1] = int(np.argmax(delta[T_len - 1, :]))
        for t in range(T_len - 2, -1, -1):
            path[t] = psi[t + 1, path[t + 1]]

        return path

    def classify_expression(self, path: np.ndarray, fps: int = 30) -> Dict:
        """
        Classifica expressão baseado na sequência Viterbi.
        REGRA: Expressão presente SE E SOMENTE SE 'apex' ∈ sequência.
        """
        apex_frames = np.where(path == 2)[0]

        if len(apex_frames) == 0:
            return {
                "detected": False,
                "onset_frame": None,
                "apex_frame": None,
                "offset_frame": None,
                "duration_ms": 0,
                "is_microexpression": False,
            }

        # Encontrar onset e offset
        onset_frame = None
        offset_frame = None
        path_list = path.tolist()

        if 1 in path_list:
            onset_frame = path_list.index(1)
        else:
            onset_frame = int(apex_frames[0])

        if 3 in path_list:
            offset_frame = len(path_list) - 1 - path_list[::-1].index(3)
        else:
            offset_frame = int(apex_frames[-1])

        # Duração
        duration_frames = offset_frame - onset_frame
        duration_ms = int(duration_frames * (1000 / fps))

        return {
            "detected": True,
            "onset_frame": onset_frame,
            "apex_frame": int(apex_frames[len(apex_frames) // 2]),
            "offset_frame": offset_frame,
            "duration_ms": duration_ms,
            "is_microexpression": duration_ms < 500,
        }

    def reset(self):
        """Limpa buffers para nova expressão."""
        self.onset_buffer = []
        self.offset_buffer = []
