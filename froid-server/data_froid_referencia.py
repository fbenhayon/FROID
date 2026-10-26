"""Referencia populacional do Data-FROID para o FROID Explica (fase 5).

Uma medida, uma distribuicao: quantas sessoes distintas, quantos registros
apurados, media, mediana e quartis — e, quando o profissional tem um valor
na frente, em que ponto dessa distribuicao ele cai. Tudo calculado AQUI, em
SQL parametrizado sobre colunas de uma lista fechada: o modelo escolhe a
medida e os filtros, nunca escreve SQL (o caminho de SQL escrito pelo modelo
continua existindo na rota de analytics, com a arvore do DuckDB o vigiando;
este caminho nao precisa dele).

Tres regras que vieram do acervo (docs/data-froid-fase1-desenho.md):

- piso de coorte POR RESPOSTA: abaixo de `piso` sessoes distintas, nada sai —
  nem a media, nem o n parcial; so a declaracao de que a coorte nao fechou;
- zero falso: ate a v3 do acervo ausencia de medida era gravada como 0.0;
  medida acustica so entra a partir das versoes em `versoes_sem_zero_falso`,
  e NULL (nao apurado) fica fora da conta, com `n_apurado` ao lado do n de
  sessoes para o leitor ver sobre quanto a media foi feita;
- texto nenhum: a lista de medidas so tem numero; tema, resumo e qualquer
  coluna de texto do acervo nao passam por aqui.

A distribuicao e de SESSOES DO FROID, nao uma norma clinica: a frase de
saida diz isso, e a instrucao do Explica repete.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Medida:
    nome: str          # como o modelo pede
    tabela: str        # anonymous_sessions | anonymous_session_cuts
    coluna: str
    rotulo: str        # o rotulo do painel, quando existe
    casas: int
    acustica: bool     # sujeita ao zero falso da v3
    nivel: str         # "sessao" | "corte"


# Lista fechada. Nome novo aqui exige coluna numerica no acervo e um teste.
MEDIDAS: Tuple[Medida, ...] = (
    Medida("ipm_sessao", "anonymous_sessions", "ipm_score", "IPM", 1, True, "sessao"),
    Medida("idm_sessao", "anonymous_sessions", "average_idm", "IDM", 2, True, "sessao"),
    Medida("palavras_por_minuto_sessao", "anonymous_sessions", "average_words_per_minute", "P/MIN", 1, False, "sessao"),
    Medida("dissonancias_sessao", "anonymous_sessions", "dissonance_count", "DISSO.", 0, False, "sessao"),
    Medida("tensao_vocal_sessao", "anonymous_sessions", "vocal_tension", "DNA VOCAL", 3, True, "sessao"),
    Medida("indice_espectral_sessao", "anonymous_sessions", "average_spectral_band_index", "IND. ESPECTRAL", 3, True, "sessao"),
    Medida("duracao_sessao_s", "anonymous_sessions", "session_duration", "duracao (s)", 0, False, "sessao"),
    Medida("ipm_corte", "anonymous_session_cuts", "ipm_avg", "IPM", 1, True, "corte"),
    Medida("idm_corte", "anonymous_session_cuts", "idm_avg", "IDM", 2, True, "corte"),
    Medida("palavras_por_minuto_corte", "anonymous_session_cuts", "words_per_minute", "P/MIN", 1, False, "corte"),
    Medida("dissonancias_corte", "anonymous_session_cuts", "dissonance_count", "DISSO.", 0, False, "corte"),
    Medida("f0_corte", "anonymous_session_cuts", "f0_mean", "F0 MED.", 2, True, "corte"),
    Medida("jitter_corte", "anonymous_session_cuts", "jitter", "JITTER", 3, True, "corte"),
    Medida("shimmer_corte", "anonymous_session_cuts", "shimmer", "SHIMMER", 3, True, "corte"),
    Medida("zcr_corte", "anonymous_session_cuts", "zcr", "ZCR", 3, True, "corte"),
    Medida("mfcc7_corte", "anonymous_session_cuts", "mfcc7", "MFCC7", 3, True, "corte"),
    Medida("mfcc9_corte", "anonymous_session_cuts", "mfcc9", "MFCC9", 3, True, "corte"),
    Medida("indice_espectral_corte", "anonymous_session_cuts", "spectral_band_index", "IND. ESPECTRAL", 3, True, "corte"),
    Medida("delta_corte", "anonymous_session_cuts", "spectral_delta_0_4", "DELTA", 3, True, "corte"),
    Medida("theta_corte", "anonymous_session_cuts", "spectral_theta_4_8", "THETA", 3, True, "corte"),
    Medida("alpha_corte", "anonymous_session_cuts", "spectral_alpha_8_12", "ALPHA", 3, True, "corte"),
    Medida("beta_corte", "anonymous_session_cuts", "spectral_beta_12_30", "BETA", 3, True, "corte"),
    Medida("gama_corte", "anonymous_session_cuts", "spectral_gamma_30_80", "GAMA", 3, True, "corte"),
    Medida("subharmonico_5_12_corte", "anonymous_session_cuts", "subharmonic_5_12", "SUB-H 5-12", 3, True, "corte"),
    Medida("subharmonico_12_20_corte", "anonymous_session_cuts", "subharmonic_12_20", "SUB-H 12-20", 3, True, "corte"),
    Medida("subharmonico_20_40_corte", "anonymous_session_cuts", "subharmonic_20_40", "SUB-H 20-40", 3, True, "corte"),
    Medida("vocal_basal_85_165_corte", "anonymous_session_cuts", "vocal_basal_85_165", "VOCAL 85-165", 3, True, "corte"),
)
MEDIDAS_POR_NOME: Dict[str, Medida] = {m.nome: m for m in MEDIDAS}
NOMES_DAS_MEDIDAS: Tuple[str, ...] = tuple(m.nome for m in MEDIDAS)

# Filtros de coorte: colunas de categoria de anonymous_sessions, nunca texto
# livre. Nos cortes, o filtro entra por juncao com a sessao.
FILTROS: Tuple[str, ...] = ("age_bucket", "gender", "session_modality")


class CoorteInsuficiente(Exception):
    """Abaixo do piso: a mensagem nao traz numero parcial algum."""


class MedidaDesconhecida(Exception):
    pass


def _fmt(valor: Any, casas: int) -> str:
    if valor is None:
        return "--"
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return "--"
    if numero != numero:  # NaN
        return "--"
    return f"{numero:.{casas}f}"


def consultar(
    conn: Any,
    medida_nome: str,
    *,
    piso: int,
    versoes_sem_zero_falso: Sequence[str],
    valor: Optional[float] = None,
    filtros: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """A distribuicao da medida na coorte filtrada. Levanta CoorteInsuficiente
    abaixo do piso e MedidaDesconhecida fora da lista."""
    medida = MEDIDAS_POR_NOME.get(str(medida_nome or "").strip())
    if medida is None:
        raise MedidaDesconhecida(str(medida_nome))
    piso = max(1, int(piso))
    condicoes = [f"t.{medida.coluna} IS NOT NULL"]
    parametros: list = []
    versoes_aplicadas: Tuple[str, ...] = ()
    if medida.acustica:
        versoes_aplicadas = tuple(str(v) for v in versoes_sem_zero_falso)
        if versoes_aplicadas:
            marcadores = ", ".join("?" for _ in versoes_aplicadas)
            condicoes.append(f"s.schema_version IN ({marcadores})")
            parametros.extend(versoes_aplicadas)
    filtros_aplicados: Dict[str, str] = {}
    for chave, bruto in (filtros or {}).items():
        texto = str(bruto or "").strip()
        if chave in FILTROS and texto:
            condicoes.append(f"s.{chave} = ?")
            parametros.append(texto)
            filtros_aplicados[chave] = texto
    if medida.tabela == "anonymous_sessions":
        origem = "anonymous_sessions AS t JOIN anonymous_sessions AS s ON s.session_hash = t.session_hash"
    else:
        origem = "anonymous_session_cuts AS t JOIN anonymous_sessions AS s ON s.session_hash = t.session_hash"
    onde = " AND ".join(condicoes)
    col = f"t.{medida.coluna}"
    sql = (
        f"SELECT COUNT(DISTINCT t.session_hash), COUNT({col}), AVG({col}), "
        f"quantile_cont({col}, 0.25), quantile_cont({col}, 0.5), quantile_cont({col}, 0.75) "
        f"FROM {origem} WHERE {onde}"
    )
    linha = conn.execute(sql, parametros).fetchone() or (0, 0, None, None, None, None)
    sessoes = int(linha[0] or 0)
    if sessoes < piso:
        raise CoorteInsuficiente(
            f"coorte insuficiente para {medida.nome}: menos de {piso} sessoes distintas "
            "com a medida apurada nos filtros pedidos; nenhum numero e devolvido abaixo do piso"
        )
    resultado: Dict[str, Any] = {
        "medida": medida.nome,
        "rotulo": medida.rotulo,
        "nivel": medida.nivel,
        "sessoes": sessoes,
        "n_apurado": int(linha[1] or 0),
        "media": linha[2],
        "p25": linha[3],
        "mediana": linha[4],
        "p75": linha[5],
        "casas": medida.casas,
        "versoes": versoes_aplicadas,
        "filtros": filtros_aplicados,
        "piso": piso,
        "posicao_do_valor": None,
    }
    if valor is not None:
        abaixo = conn.execute(
            f"SELECT AVG(CASE WHEN {col} < ? THEN 1.0 ELSE 0.0 END) FROM {origem} WHERE {onde}",
            [float(valor), *parametros],
        ).fetchone()
        fracao = abaixo[0] if abaixo else None
        resultado["posicao_do_valor"] = None if fracao is None else float(fracao)
        resultado["valor"] = float(valor)
    return resultado


def formatar(resultado: Mapping[str, Any]) -> str:
    """O texto que vai ao modelo: numeros com o n ao lado e a natureza da
    referencia declarada."""
    casas = int(resultado.get("casas", 2))
    nivel = "por sessao" if resultado.get("nivel") == "sessao" else "por corte"
    linhas = [
        f"REFERENCIA POPULACIONAL (Data-FROID anonimo) — {resultado['rotulo']} {nivel} "
        f"[{resultado['medida']}]: distribuicao de sessoes do FROID, nao uma norma clinica.",
        f"- sessoes distintas: {resultado['sessoes']} (piso de coorte {resultado['piso']}); "
        f"registros apurados: {resultado['n_apurado']}",
        f"- media {_fmt(resultado['media'], casas)} | quartil 25 {_fmt(resultado['p25'], casas)} | "
        f"mediana {_fmt(resultado['mediana'], casas)} | quartil 75 {_fmt(resultado['p75'], casas)}",
    ]
    filtros = resultado.get("filtros") or {}
    linhas.append(
        "- filtros: " + (", ".join(f"{k}={v}" for k, v in filtros.items()) if filtros else "nenhum (acervo inteiro)")
    )
    versoes = resultado.get("versoes") or ()
    if versoes:
        linhas.append(
            "- versoes do acervo consideradas: " + ", ".join(versoes)
            + " (as anteriores gravavam zero por ausencia e ficaram fora)"
        )
    posicao = resultado.get("posicao_do_valor")
    if posicao is not None:
        linhas.append(
            f"- o valor informado {_fmt(resultado.get('valor'), casas)} fica acima de "
            f"{posicao * 100:.0f}% dos registros apurados (calculado pelo servidor)"
        )
    return "\n".join(linhas)
