"""
FROID Voice - Mapeador de Colorimetria
7 níveis de cor por energia zonal (verde escuro → vermelho escuro)

Fonte: Plano 4B original - proprietário FROID
"""

from typing import List, Dict
from src.config import COLOR_MAP


class ColorMapper:
    """
    Mapeia energia normalizada de cada zona para uma cor do espectro FROID.
    Verde = ativação positiva, Vermelho = ativação negativa.
    """

    def map_zones(self, zones: List[Dict]) -> List[str]:
        """
        Mapeia energia normalizada de cada zona para cor hex.
        
        A lógica usa a posição relativa da energia em relação à média:
        - Energia muito acima da média → Verde (ativação positiva)
        - Energia na média → Amarelo (equilíbrio)
        - Energia muito abaixo → Vermelho (ativação negativa)
        
        Args:
            zones: Lista de dicionários com 'energy_normalized'
            
        Returns:
            Lista de 12 cores hex
        """
        if not zones:
            return [COLOR_MAP[4]["hex"]] * 12  # Amarelo neutro

        energies = [z.get("energy_normalized", 0.0) for z in zones]
        mean_energy = sum(energies) / len(energies) if energies else 0.0

        colors = []
        for energy in energies:
            level = self._energy_to_level(energy, mean_energy)
            colors.append(COLOR_MAP[level]["hex"])

        return colors

    def map_single(self, energy: float, mean_energy: float) -> Dict:
        """Mapeia uma única energia para cor com metadados completos."""
        level = self._energy_to_level(energy, mean_energy)
        return COLOR_MAP[level]

    def get_overall_color(self, zones: List[Dict]) -> str:
        """Retorna cor dominante geral da fatia de áudio."""
        if not zones:
            return COLOR_MAP[4]["hex"]

        # Usar a zona dominante (maior energia)
        dominant = max(zones, key=lambda z: z.get("total_energy", 0))
        energies = [z.get("energy_normalized", 0) for z in zones]
        mean_e = sum(energies) / len(energies)

        level = self._energy_to_level(dominant.get("energy_normalized", 0), mean_e)
        return COLOR_MAP[level]["hex"]

    def _energy_to_level(self, energy: float, mean_energy: float) -> int:
        """
        Converte energia normalizada em nível de cor (1-7).
        
        Mapeamento relativo à média:
        - >2x média → Nível 1 (verde escuro, muito positivo)
        - 1.5x-2x → Nível 2 (verde claro)
        - 1.1x-1.5x → Nível 3 (amarelo-verde)
        - 0.9x-1.1x → Nível 4 (amarelo, neutro)
        - 0.6x-0.9x → Nível 5 (laranja)
        - 0.3x-0.6x → Nível 6 (vermelho claro)
        - <0.3x → Nível 7 (vermelho escuro)
        """
        if mean_energy <= 0.001:
            return 4  # Neutro se sem dados

        ratio = energy / mean_energy if mean_energy > 0 else 1.0

        if ratio > 2.0:
            return 1
        elif ratio > 1.5:
            return 2
        elif ratio > 1.1:
            return 3
        elif ratio > 0.9:
            return 4
        elif ratio > 0.6:
            return 5
        elif ratio > 0.3:
            return 6
        else:
            return 7
