"""Cadastro das operações de tratamento, em código e não em planilha.

O parecer jurídico apontou o que faltava: cada operação precisa ter base legal
declarada, papéis definidos e retenção conhecida — e isso normalmente vira uma
planilha que envelhece na primeira sprint depois de escrita.

Aqui o cadastro mora ao lado do código que executa a operação. Não porque seja
mais bonito, mas porque é a única versão que alguém atualiza: quando um
endpoint muda de finalidade, o arquivo que descreve a finalidade está no mesmo
diff e no mesmo code review.

A correção central do parecer, e a que muda mais coisa: **no fluxo NR-1 a base
legal não é consentimento.** É cumprimento de obrigação legal — art. 7º, II
para dado comum e art. 11, II, "a" para dado sensível — porque a NR-1 obriga
a empresa a levantar riscos psicossociais. Consentimento na relação de emprego
é viciado pela hierarquia: o empregado não recusa livremente o pedido do
empregador, e consentimento não livre não vale.

O trabalhador continua sendo informado. Ele apenas não está autorizando, e sim
sendo avisado — que é o que a transparência exige quando a base é outra.

Ressalva que o parecer faz e que vale repetir: o estudo de validade convergente
NÃO segue essa regra. Lá o consentimento é a base certa, porque é pesquisa,
é voluntária, é separável do atendimento, e quem consente é paciente de
clínica e não empregado. Aplicar "consentimento não serve" por analogia
quebraria o estudo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


# Bases legais da LGPD usadas pelo FROID, com o artigo citado por extenso para
# que o RIPD saia do próprio cadastro.
OBRIGACAO_LEGAL_COMUM = "art. 7º, II — cumprimento de obrigação legal ou regulatória"
OBRIGACAO_LEGAL_SENSIVEL = "art. 11, II, 'a' — cumprimento de obrigação legal ou regulatória"
TUTELA_SAUDE = "art. 11, II, 'f' — tutela da saúde, por profissional de saúde"
EXECUCAO_CONTRATO = "art. 7º, V — execução de contrato"
CONSENTIMENTO_PESQUISA = "art. 7º, I e art. 11, I — consentimento específico e destacado"
LEGITIMO_INTERESSE = "art. 7º, IX — legítimo interesse do controlador"


@dataclass(frozen=True)
class Operacao:
    chave: str
    descricao: str
    base_legal: str
    controlador: str
    operador: str
    classe_dado: str  # comum | sensivel | anonimizado
    retencao: str
    observacao: str = ""


# Cada operação que toca dado pessoal. Ausência daqui é um achado, não um
# silêncio: se um endpoint trata dado e não aparece nesta lista, ninguém
# declarou sua finalidade.
OPERACOES: Tuple[Operacao, ...] = (
    Operacao(
        "cadastro_organizacao",
        "Cadastro da empresa ou clínica contratante",
        EXECUCAO_CONTRATO, "FROID", "—", "comum",
        "Enquanto vigente o contrato, mais prazos legais de guarda fiscal",
    ),
    Operacao(
        "cadastro_profissional",
        "Cadastro e autenticação do profissional habilitado",
        EXECUCAO_CONTRATO, "FROID", "—", "comum",
        "Enquanto vigente o contrato",
    ),
    Operacao(
        "sessao_clinica",
        "Voz, face, transcrição e métricas durante o atendimento",
        TUTELA_SAUDE, "Profissional ou clínica", "FROID", "sensivel",
        "Conforme obrigação de guarda de prontuário do conselho profissional",
        "O FROID executa o processamento técnico; a finalidade clínica é do "
        "profissional, que responde pelo prontuário.",
    ),
    Operacao(
        "nr1_convite_colaborador",
        "Envio do convite anônimo para o questionário psicossocial",
        OBRIGACAO_LEGAL_COMUM, "Empresa empregadora", "FROID", "comum",
        "Até o encerramento da campanha; o token é descartado ao ser usado",
        "O convite carrega token de uso único. A resposta nunca conhece o "
        "colaborador — apenas o pseudônimo da campanha.",
    ),
    Operacao(
        "nr1_resposta_questionario",
        "Respostas individuais ao instrumento psicossocial",
        OBRIGACAO_LEGAL_SENSIVEL, "Empresa empregadora", "FROID", "sensivel",
        "Até a consolidação do inventário da campanha (ver purga)",
        "NÃO há consentimento: a NR-1 obriga o levantamento, e consentimento "
        "na relação de emprego é viciado pela hierarquia. O colaborador é "
        "informado pelo aviso de finalidade, não consultado.",
    ),
    Operacao(
        "nr1_painel_agregado",
        "Resultado agregado por recorte, com piso de coorte",
        OBRIGACAO_LEGAL_COMUM, "Empresa empregadora", "FROID", "anonimizado",
        "Histórico do inventário por 20 anos (subitem 1.5.7.3.3.1)",
        "Piso de 50 por campanha e 10 por recorte, aplicado em SQL. Nenhum "
        "resultado sai enquanto a coleta está aberta, para fechar o ataque "
        "por diferenciação.",
    ),
    Operacao(
        "estudo_validade",
        "Pontuação do PHQ-9 pareada com os padrões medidos",
        CONSENTIMENTO_PESQUISA, "FROID", "—", "sensivel",
        "Até a conclusão do estudo ou a retirada do participante",
        "Aqui o consentimento É a base correta: pesquisa voluntária, separável "
        "do atendimento, com retirada que apaga os pares. Exige parecer de CEP "
        "antes da coleta.",
    ),
    Operacao(
        "datamart_anonimo",
        "Métricas anonimizadas para pesquisa e melhoria do produto",
        LEGITIMO_INTERESSE, "FROID", "—", "anonimizado",
        "Indeterminada, por não conter dado pessoal",
        "Identificador derivado por hash com sal; sem PII, sem transcrição "
        "literal, sem áudio bruto.",
    ),
    Operacao(
        "auditoria_acesso",
        "Trilha de quem acessou o quê, quando e de onde",
        OBRIGACAO_LEGAL_COMUM, "FROID", "—", "comum",
        "Pelo prazo necessário à demonstração de conformidade e à defesa",
        "A trilha é a evidência de que os controles funcionaram; apagá-la "
        "destrói justamente a prova da conformidade.",
    ),
)


# O aviso que o colaborador precisa ver, com a base legal dita e não sugerida.
#
# O parecer é explícito: o trabalhador não deve ver "aceito fornecer meus
# dados", e sim ser informado de que o tratamento decorre de obrigação legal.
# A diferença não é de redação — é de natureza do ato.
AVISO_BASE_LEGAL_NR1 = (
    "Os dados desta avaliação são tratados para cumprimento das obrigações "
    "legais do empregador quanto ao Gerenciamento de Riscos Ocupacionais "
    "(GRO), conforme a NR-1 e a Portaria MTE nº 1.419/2024, nos termos da "
    "LGPD, art. 7º, II e art. 11, II, 'a'. Você está sendo informado, e não "
    "consultado: a empresa tem obrigação legal de levantar estes riscos. "
    "Suas respostas individuais não são acessíveis ao empregador."
)


def compose_purpose_notice(texto_da_empresa: str) -> str:
    """Junta o aviso da empresa com a base legal, nessa ordem.

    A base legal é anexada estruturalmente em vez de confiada ao texto livre
    porque o campo é preenchido por campanha, por gente diferente, sob pressa.
    Um aviso sem base legal declarada não é ilegal por si — mas é a primeira
    coisa que falta quando alguém pergunta com que direito a empresa perguntou.
    """
    corpo = (texto_da_empresa or "").strip()
    if AVISO_BASE_LEGAL_NR1 in corpo:
        return corpo
    return f"{corpo}\n\n{AVISO_BASE_LEGAL_NR1}".strip()


def registry_as_document() -> dict:
    """O cadastro em forma citável, para anexar ao RIPD."""
    return {
        "versao": "2026-08-05",
        "operacoes": [
            {
                "chave": op.chave,
                "descricao": op.descricao,
                "base_legal": op.base_legal,
                "controlador": op.controlador,
                "operador": op.operador,
                "classe_dado": op.classe_dado,
                "retencao": op.retencao,
                "observacao": op.observacao,
            }
            for op in OPERACOES
        ],
    }
