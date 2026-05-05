"""
FROID Face - Suite de Validação Clínica
Testes científicos cobrindo TODOS os thresholds e regras

Execução: pytest tests/clinical_validation.py -v -m clinical
"""

import pytest
import numpy as np
from src.analyzers.temporal_hmm import ExpressionHMM
from src.analyzers.asymmetry_analyzer import FacialAsymmetryAnalyzer
from src.analyzers.emotion_classifier import EmotionClassifier
from src.config import ClinicalThresholds, AU_TO_EMOTION_RULES


@pytest.mark.clinical
class TestClinicalThresholds:
    """Validação dos thresholds científicos [FACTS3.pdf]"""

    def setup_method(self):
        self.asym = FacialAsymmetryAnalyzer()

    def test_eyelid_threshold_2mm(self):
        """Eyelid ≥2mm deve gerar flag HIGH [FACTS3.pdf, Results]"""
        scores = {"eye_mm": 2.1, "mouth_mm": 1.0, "brow_mm": 1.0}
        flags = self.asym.evaluate_flags(scores, delay_ms=0.0)
        
        assert len(flags) > 0
        assert flags[0]["region"] == "eyelid"
        assert flags[0]["severity"] == "high"
        assert flags[0]["detection_probability"] == ">90%"

    def test_smile_threshold_3mm(self):
        """Smile ≥3mm deve gerar flag HIGH [FACTS3.pdf, Results]"""
        scores = {"eye_mm": 1.0, "mouth_mm": 3.2, "brow_mm": 1.0}
        flags = self.asym.evaluate_flags(scores, delay_ms=0.0)
        
        assert len(flags) > 0
        assert flags[0]["region"] == "smile"
        assert flags[0]["severity"] == "high"
        assert flags[0]["detection_probability"] == ">90%"

    def test_brow_threshold_3mm(self):
        """Brow ≥3mm deve gerar flag MEDIUM/HIGH [FACTS3.pdf, Results]"""
        scores = {"eye_mm": 1.0, "mouth_mm": 1.0, "brow_mm": 3.5}
        flags = self.asym.evaluate_flags(scores, delay_ms=0.0)
        
        assert len(flags) > 0
        assert flags[0]["region"] == "brow"
        assert flags[0]["severity"] in ["medium", "high"]

    def test_delay_threshold_99ms(self):
        """Delay ≥99ms deve gerar flag HIGH [FACTS3.pdf, Results]"""
        scores = {"eye_mm": 1.0, "mouth_mm": 1.0, "brow_mm": 1.0}
        flags = self.asym.evaluate_flags(scores, delay_ms=100.0)
        
        assert len(flags) == 1
        assert flags[0]["region"] == "hemifacial"
        assert flags[0]["severity"] == "high"
        assert flags[0]["detection_probability"] == ">50%"

    def test_no_flags_below_thresholds(self):
        """Abaixo dos thresholds não deve gerar flags"""
        scores = {"eye_mm": 1.5, "mouth_mm": 2.5, "brow_mm": 2.5}
        flags = self.asym.evaluate_flags(scores, delay_ms=50.0)
        
        assert len(flags) == 0


@pytest.mark.clinical
class TestHMMApexRule:
    """Validação da REGRA DO APEX [3D FACTS.pdf]"""

    def setup_method(self):
        self.hmm = ExpressionHMM()

    def test_apex_present_expression_detected(self):
        """Apex presente → Expressão DETECTADA"""
        path = np.array([0, 1, 2, 2, 3, 0])  # neutral→onset→apex→apex→offset→neutral
        result = self.hmm.classify_expression(path)
        
        assert result["detected"] is True
        assert result["apex_frame"] is not None
        assert result["onset_frame"] is not None
        assert result["offset_frame"] is not None

    def test_no_apex_no_expression(self):
        """Sem apex → Expressão NÃO DETECTADA"""
        path = np.array([0, 1, 1, 3, 0])  # neutral→onset→onset→offset→neutral (SEM APEX!)
        result = self.hmm.classify_expression(path)
        
        assert result["detected"] is False
        assert result["apex_frame"] is None

    def test_apex_only_is_valid(self):
        """Apenas apex sem onset/offset ainda é válido"""
        path = np.array([0, 2, 2, 0])  # neutral→apex→apex→neutral
        result = self.hmm.classify_expression(path)
        
        assert result["detected"] is True

    def test_microexpression_detection(self):
        """Expressão <500ms deve ser marcada como microexpressão"""
        path = np.array([0, 1, 2, 3, 0])  # Duração: 4 frames @ 30fps = 133ms
        result = self.hmm.classify_expression(path, fps=30)
        
        assert result["detected"] is True
        assert result["is_microexpression"] is True
        assert result["duration_ms"] < ClinicalThresholds.MICROEXPRESSION_MS


@pytest.mark.clinical
class TestAUMapping:
    """Validação da tabela AU→Emoção VERBATIM"""

    def setup_method(self):
        self.classifier = EmotionClassifier(min_coverage=0.70)

    def test_happy_simple_au12(self):
        """AU12 sozinho = Happy (regra mais simples)"""
        au_scores = {12: 0.9}
        result = self.classifier.classify(au_scores, hmm_confidence=0.9)
        
        assert result["emotion"] == "happy"
        assert 12 in result["matched_rule"]

    def test_happy_duchenne_au6_au12(self):
        """AU6+AU12 = Happy genuíno (sorriso de Duchenne)"""
        au_scores = {6: 0.8, 12: 0.9}
        result = self.classifier.classify(au_scores, hmm_confidence=0.9)
        
        assert result["emotion"] == "happy"
        assert set(result["matched_rule"]) == {6, 12}

    def test_sadness_full_combination(self):
        """AU1+AU4+AU15 = Sadness (regra completa)"""
        au_scores = {1: 0.7, 4: 0.8, 15: 0.75}
        result = self.classifier.classify(au_scores, hmm_confidence=0.9)
        
        assert result["emotion"] == "sadness"
        assert {1, 4, 15}.issubset(set(result["matched_rule"]))

    def test_fear_complex_combination(self):
        """AU1+AU2+AU4+AU5 = Fear (regra complexa)"""
        au_scores = {1: 0.8, 2: 0.75, 4: 0.7, 5: 0.85}
        result = self.classifier.classify(au_scores, hmm_confidence=0.9)
        
        assert result["emotion"] == "fear"

    def test_rules_verbatim_from_config(self):
        """Regras devem ser idênticas à tabela fornecida"""
        assert 12 in AU_TO_EMOTION_RULES["happy"][0]
        assert {6, 12} in AU_TO_EMOTION_RULES["happy"]
        assert {1, 2, 4, 5} in AU_TO_EMOTION_RULES["fear"]
        assert {9, 10, 17} in AU_TO_EMOTION_RULES["disgust"]

    def test_neutral_without_apex(self):
        """Sem apex confiante → Neutral"""
        au_scores = {12: 0.9}
        result = self.classifier.classify(au_scores, hmm_confidence=0.5, require_apex=True)
        
        assert result["emotion"] == "neutral"


@pytest.mark.clinical
class TestGenuineness:
    """Validação de genuinidade emocional"""

    def setup_method(self):
        self.classifier = EmotionClassifier()

    def test_duchenne_smile_high_genuineness(self):
        """Sorriso de Duchenne (AU6+AU12) deve ter alta genuinidade"""
        au_scores = {6: 0.9, 12: 0.85}  # AU6 é músculo confiável
        genuineness = self.classifier.get_genuineness_score(au_scores)
        
        assert genuineness >= 0.5  # Pelo menos 50% confiável

    def test_social_smile_low_genuineness(self):
        """Sorriso social (só AU12) deve ter baixa genuinidade"""
        au_scores = {12: 0.9}  # AU12 é músculo voluntário
        genuineness = self.classifier.get_genuineness_score(au_scores)
        
        assert genuineness <= 0.5  # Menos confiável


@pytest.mark.clinical
class TestDSFaceComputation:
    """Validação de D-face e S-face [FACTS4.pdf, Eq. 1-2]"""

    def setup_method(self):
        self.asym = FacialAsymmetryAnalyzer()

    def test_symmetric_face_low_asymmetry(self):
        """Face simétrica deve ter D-face próximo de zero"""
        # Criar imagem simétrica artificial
        img = np.random.randint(0, 255, (128, 128), dtype=np.uint8)
        img_symmetric = (img + np.fliplr(img)) // 2
        
        D_half, S_half = self.asym.compute_d_s_face(img_symmetric)
        
        assert np.mean(D_half) < 0.1  # Baixa assimetria

    def test_asymmetric_face_high_d_face(self):
        """Face assimétrica deve ter D-face alto"""
        # Criar assimetria artificial
        img = np.random.randint(0, 255, (128, 128), dtype=np.uint8)
        img[:, :64] = 50   # Lado esquerdo escuro
        img[:, 64:] = 200  # Lado direito claro
        
        D_half, S_half = self.asym.compute_d_s_face(img)
        
        assert np.mean(D_half) > 0.3  # Alta assimetria

    def test_output_dimensions(self):
        """D-face e S-face devem ter dimensão 128×64 (metade esquerda)"""
        img = np.random.randint(0, 255, (128, 128), dtype=np.uint8)
        D_half, S_half = self.asym.compute_d_s_face(img)
        
        assert D_half.shape == (128, 64)
        assert S_half.shape == (128, 64)


@pytest.mark.clinical
class TestIntegrationPipeline:
    """Testes de integração entre módulos"""

    def setup_method(self):
        self.hmm = ExpressionHMM()
        self.classifier = EmotionClassifier()
        self.asym = FacialAsymmetryAnalyzer()

    def test_full_pipeline_happy_expression(self):
        """Pipeline completo: onset→apex→offset + AU12 = Happy"""
        # Simular sequência HMM
        onset_scores = np.array([0.2, 0.8, 0.5, 0.5, 0.3, 0.2])
        offset_scores = np.array([0.2, 0.2, 0.3, 0.3, 0.8, 0.2])
        
        path = self.hmm.viterbi_decode(onset_scores, offset_scores)
        hmm_result = self.hmm.classify_expression(path)
        
        # Simular AU12 ativo
        au_scores = {12: 0.9}
        emotion_result = self.classifier.classify(au_scores, hmm_result["apex_confidence"])
        
        assert hmm_result["detected"] is True
        assert emotion_result["emotion"] == "happy"

    def test_full_pipeline_no_apex_neutral(self):
        """Sem apex → Neutral independente de AUs ativos"""
        # Sequência sem apex
        path = np.array([0, 1, 1, 3, 0])
        hmm_result = self.hmm.classify_expression(path)
        
        # Mesmo com AU12 ativo
        au_scores = {12: 0.9}
        emotion_result = self.classifier.classify(au_scores, hmm_result["apex_confidence"], require_apex=True)
        
        assert hmm_result["detected"] is False
        assert emotion_result["emotion"] == "neutral"


# =============================================================================
# FIXTURES E HELPERS
# =============================================================================

@pytest.fixture
def sample_symmetric_image():
    """Gera imagem facial simétrica para testes"""
    img = np.random.randint(0, 255, (128, 128), dtype=np.uint8)
    return (img + np.fliplr(img)) // 2


@pytest.fixture
def sample_au_scores():
    """Scores de AUs para testes"""
    return {
        1: 0.75,
        4: 0.80,
        12: 0.85,
        15: 0.70
    }


# =============================================================================
# EXECUÇÃO
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "clinical"])
