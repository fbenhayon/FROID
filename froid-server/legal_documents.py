"""Versioned, truthful legal notices presented by the FROID application.

Supplier PII is deployment configuration, never source-controlled.  Document
hashes include the rendered supplier identity so an acceptance proves the exact
text and party displayed to the user.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any


# Mudança material: a versão sobe e todo profissional volta a aceitar. Alterar
# limites clínicos sem subir a versão deixaria aceites antigos provando um
# texto que não é mais o vigente — exatamente o que o hash existe para impedir.
LEGAL_DOCUMENT_VERSION = "2026-08-22.br-pf-v3"


def _supplier() -> dict[str, str | bool]:
    supplier = {
        "name": os.getenv("FROID_LEGAL_SUPPLIER_NAME", "").strip(),
        "tax_id": os.getenv("FROID_LEGAL_SUPPLIER_TAX_ID", "").strip(),
        "address": os.getenv("FROID_LEGAL_SUPPLIER_ADDRESS", "").strip(),
        "contact_email": os.getenv("FROID_LEGAL_CONTACT_EMAIL", "").strip(),
        "privacy_email": os.getenv("FROID_LEGAL_PRIVACY_EMAIL", "").strip(),
    }
    supplier["configured"] = all(supplier.values())
    return supplier


COMMON_LIMITS = (
    "O FROID oferece indicadores, transcrições e conteúdo de inteligência artificial "
    "como apoio à atividade de profissional habilitado. Não realiza diagnóstico autônomo, "
    "não prescreve tratamento, não substitui avaliação clínica e não deve ser o único "
    "fundamento de decisão clínica, jurídica, laboral, securitária ou emergencial. "
    "Os indicadores do FROID são medidas de sinal acústico e visual, lidas contra a "
    "linha de base do próprio paciente. Não constituem teste psicológico, não são "
    "instrumento psicométrico validado, não produzem escore normativo comparável a "
    "outras pessoas e não inferem, por si, estado mental, quadro clínico ou construto "
    "psicológico."
)


# A fronteira entre medir e interpretar, dita ao profissional no momento em que
# ele assina — e não escondida numa nota técnica que ele nunca vai ler.
#
# Duas coisas distintas moram nesta cláusula, e ambas são condição do acesso:
# a interpretação é dele (o que mantém o FROID como instrumentação e não como
# instrumento de avaliação psicológica), e o material aprofundado que ele
# recebe é confidencial (o que preserva o capital intelectual sem precisar
# sonegar ao clínico o que ele precisa para confiar na medida).
INTERPRETATION_BOUNDARY = (
    "O FROID entrega medida; a interpretação é do profissional. O licenciado reconhece "
    "que os índices, marcadores e gráficos do FROID descrevem propriedades medidas da voz "
    "e da expressão facial em relação à linha de base do próprio paciente, e que a "
    "atribuição de significado clínico a essas medidas é ato privativo seu, praticado sob "
    "sua responsabilidade técnica e seu registro profissional. O licenciado se obriga a "
    "não apresentar, transcrever ou citar saída do FROID como resultado de teste "
    "psicológico, laudo, parecer, triagem diagnóstica ou conclusão sobre estado mental, "
    "em prontuário, documento, perícia ou comunicação a terceiros. Documentação técnica "
    "aprofundada eventualmente disponibilizada ao licenciado — incluindo parâmetros, "
    "critérios de composição, limiares e resultados de validação — é confidencial, "
    "destina-se exclusivamente ao uso próprio do licenciado e não pode ser reproduzida, "
    "publicada ou transferida a terceiros sem autorização escrita, obrigação que subsiste "
    "ao término deste contrato."
)


# O objeto de cada serviço, dito no contrato dele.
#
# Os dois produtos do FROID tratam de coisas incompatíveis, e um contrato que não
# diz qual dos dois está sendo contratado deixa a fronteira depender de quem lê.
# O FROID Psique olha para UMA PESSOA, com o consentimento dela e sob
# responsabilidade de um profissional habilitado. O FROID NR-1 olha para o
# TRABALHO, de forma anônima e agregada, e não pode chegar perto de pessoa
# nenhuma. Escrever isso no objeto é o que impede que a contratação de um seja
# usada para justificar o uso do outro.
OBJETO_PSIQUE = (
    "Este contrato tem por objeto a licença de uso do FROID Psique, ferramenta de "
    "apoio à escuta clínica destinada a profissional habilitado em saúde mental. "
    "A finalidade do serviço é ampliar a percepção do profissional durante e depois "
    "da sessão, por meio de instrumentação da fala e da expressão facial, "
    "transcrição, organização longitudinal do acompanhamento e conteúdo explicativo, "
    "sempre lidos contra a linha de base do próprio paciente. "
    "O objeto do FROID Psique é a pessoa atendida, com o conhecimento e as "
    "autorizações dela, e sob responsabilidade técnica de quem a atende. "
    "Este contrato NÃO abrange avaliação de riscos psicossociais do trabalho, "
    "avaliação de trabalhador a pedido de empregador, triagem admissional, "
    "exame de aptidão, nem qualquer uso cujo destinatário do resultado seja o "
    "empregador do avaliado. A avaliação de condições de trabalho é objeto de "
    "contrato próprio, o do FROID NR-1, e os dois serviços não se comunicam."
)


# O objeto do serviço corporativo, e as duas frases que ele existe para sustentar:
# o objeto é a condição de trabalho, e a responsabilidade pelo GRO é da empresa.
#
# A segunda não é modéstia contratual: o Manual do GRO é explícito ("Mesmo com
# consultoria externa, a responsabilidade final pelo GRO é sempre da
# organização"), e um contrato que sugerisse o contrário venderia uma isenção que
# não existe — e que a fiscalização desmonta na primeira pergunta.
OBJETO_NR1 = (
    "Este contrato tem por objeto a prestação do serviço FROID NR-1: identificação "
    "de perigos e avaliação dos fatores de risco psicossociais relacionados ao "
    "trabalho, para integrar o Gerenciamento de Riscos Ocupacionais da contratante, "
    "nos termos do capítulo 1.5 da NR-1, na redação dada pela Portaria MTE nº "
    "1.419/2024, e das condições de trabalho previstas na NR-17. "
    "O objeto da avaliação é a CONDIÇÃO DE TRABALHO — a concepção, a organização e "
    "a gestão do trabalho —, nunca a pessoa do trabalhador. Não se verificam "
    "sintomas individuais, não se mede sinal biológico e não se avalia a saúde "
    "mental de quem quer que seja: verifica-se a que condições de trabalho o "
    "trabalhador está submetido. "
    "A responsabilidade pelo GRO, pelo PGR e por todas as suas etapas é da "
    "contratante, e não é transferida por este contrato. O FROID é o instrumento "
    "pelo qual a contratante executa parte desse processo; a decisão sobre medidas "
    "de prevenção, sua implementação e a assinatura dos documentos permanecem dela."
)


DOCUMENT_TEMPLATES: dict[str, dict[str, Any]] = {
    "privacy": {
        "title": "Política de Privacidade do FROID",
        "audiences": ["professional", "organization", "patient"],
        "sections": [
            ["Responsável pelo serviço", "{supplier_identity} é responsável pelas atividades próprias de cadastro, segurança, cobrança, suporte e operação do FROID. O profissional ou a clínica decide as finalidades clínicas e a composição do prontuário de seus pacientes. As funções de controlador e operador dependem de cada operação efetivamente realizada."],
            ["Dados tratados", "O serviço pode tratar cadastro, autenticação, agenda, pagamentos, registros de acesso e auditoria, voz, imagem, sinais faciais, métricas acústicas, transcrição, contexto da fala do paciente e do profissional, anotações, relatórios e histórico de sessões."],
            ["Como o processamento ocorre", "Parte das métricas é calculada no navegador. Em sessões remotas, áudio e vídeo são transmitidos pela internet e podem utilizar servidor TURN. Segmentos de áudio podem ser enviados ao backend e a provedor de transcrição. Transcrições, relatórios e registros autorizados podem ser armazenados na infraestrutura do FROID."],
            ["Fornecedores e transferência internacional", "O FROID pode utilizar infraestrutura de hospedagem na Estônia e fornecedores de pagamento, transcrição, inteligência artificial, e-mail e agenda. Isso pode envolver transferência internacional, protegida pelos mecanismos contratuais e técnicos aplicáveis."],
            ["Finalidades e bases", "Os dados são usados para executar o serviço contratado, proteger contas e sessões, processar pagamentos, atender obrigações legais, apoiar atividade de saúde por profissional habilitado e cumprir autorizações específicas. Pesquisa e Data-FROID exigem dados previamente aprovados pelo processo de anonimização e, quando aplicável, autorização opcional."],
            ["Retenção e eliminação", "A retenção considera finalidade, contrato, segurança e obrigações profissionais ou legais. Solicitações de eliminação serão analisadas e poderão resultar em exclusão, anonimização, bloqueio ou retenção restrita e fundamentada. Não se promete eliminação automática em prazo fixo quando existir obrigação legítima de guarda."],
            ["Direitos", "O titular pode solicitar confirmação, acesso, correção, informação sobre compartilhamentos, portabilidade quando aplicável, oposição, revogação de consentimento e anonimização, bloqueio ou eliminação nas hipóteses legais. Solicitações podem ser feitas pelo Portal do Paciente ou pelo contato de privacidade informado nesta página."],
            ["Segurança", "O FROID utiliza segregação por organização, controle de acesso, trilhas de auditoria, criptografia de registros clínicos e backups protegidos. Nenhum sistema elimina integralmente o risco; incidentes relevantes serão avaliados e comunicados conforme a legislação aplicável."],
        ],
    },
    "terms": {
        "title": "Termos Gerais de Uso do FROID",
        "audiences": ["professional", "organization", "patient"],
        "sections": [
            ["Objeto", "Estes termos regulam o acesso à plataforma FROID fornecida por {supplier_name}. O direito concedido é pessoal ou organizacional, limitado, não exclusivo, intransferível fora das permissões do plano e condicionado ao uso legítimo do serviço."],
            ["Limites clínicos", COMMON_LIMITS],
            ["Conduta e segurança", "O usuário deve proteger suas credenciais, manter dados corretos, respeitar permissões e comunicar suspeitas de acesso indevido. É vedado explorar vulnerabilidades, contornar controles, extrair dados em massa, copiar código ou tentar reconstruir algoritmos protegidos."],
            ["Disponibilidade", "A qualidade depende de navegador, dispositivo, microfone, câmera, rede e serviços externos. Manutenções, falhas e limitações podem ocorrer. Somente um SLA expressamente contratado cria garantia específica de disponibilidade ou tempo de resposta."],
            ["Propriedade intelectual", "Fábio de Assumpção Benhayon é o autor e titular do FROID. A contratação não transfere código, marca, textos, modelos, interfaces, pesos, fórmulas ou segredos comerciais. Permanecem assegurados os direitos legalmente reconhecidos ao usuário e a interoperabilidade permitida por lei."],
            ["Encerramento", "O acesso pode ser suspenso por violação de segurança, inadimplemento confirmado ou uso ilícito, preservados contraditório, direitos do titular, obrigações de guarda e meios de exportação aplicáveis."],
        ],
    },
    "professional_contract": {
        "title": "Contrato de Licença SaaS — FROID Psique, Profissional",
        "audiences": ["professional"],
        "sections": [
            ["Objeto e finalidade", OBJETO_PSIQUE],
            ["Partes e contratação", "O fornecedor é {supplier_identity}. O licenciado é o profissional identificado no cadastro. Pacote, quantidade de sessões, moeda e preço são os exibidos e confirmados na ordem eletrônica vinculada a este contrato."],
            ["Responsabilidade profissional", "O licenciado mantém responsabilidade técnica, ética e jurídica por atendimento, diagnóstico, documentos e conduta. Deve revisar transcrições, métricas, alertas e respostas de IA antes de utilizá-los no prontuário ou na tomada de decisão."],
            ["Natureza da medida e responsabilidade pela interpretação", INTERPRETATION_BOUNDARY],
            ["Pacientes e dados", "O profissional deve fornecer informação clara ao paciente, usar a plataforma dentro de sua habilitação e garantir base legal e autorizações adequadas. O FROID preservará a fala e o contexto registrados conforme as autorizações, a finalidade clínica e as regras de retenção aplicáveis."],
            ["Cobrança", "Cada compra corresponde à ordem apresentada antes do Stripe. A recarga automática somente existe quando escolhida separadamente; pode ser desativada para compras futuras, sem alterar recargas já processadas legitimamente."],
            ["Cancelamento e suporte", "Pedidos de cancelamento, cobrança e suporte serão tratados pelo contato informado. Reembolsos e direito de arrependimento observarão a legislação aplicável e a situação concreta da utilização do serviço."],
            ["Limites", COMMON_LIMITS],
        ],
    },
    "organization_contract": {
        "title": "Contrato de Licença SaaS — FROID Psique, Clínica ou Organização",
        "audiences": ["organization"],
        "sections": [
            ["Objeto e finalidade", OBJETO_PSIQUE],
            ["Partes e poderes", "O fornecedor é {supplier_identity}. A contratante é a pessoa jurídica identificada no cadastro, representada por pessoa que declara possuir poderes para contratar. As condições comerciais são as confirmadas na ordem eletrônica."],
            ["Governança", "A organização administra proprietários, administradores, supervisores, profissionais e auditores. Deve conceder acesso mínimo necessário, desligar usuários sem demora e definir formalmente responsabilidade técnica, custódia de prontuários e vínculo dos pacientes."],
            ["Dados e instruções", "A clínica define as finalidades clínicas e orienta o tratamento realizado em seu contexto. O FROID executa operações técnicas contratadas e atua como controlador apenas para finalidades próprias, como cadastro, segurança, faturamento, suporte e defesa de direitos."],
            ["Natureza da medida e responsabilidade pela interpretação", INTERPRETATION_BOUNDARY + " A contratante se obriga a vincular seus profissionais, colaboradores e prepostos a estas mesmas condições, respondendo por sua observância."],
            ["Isolamento e incidentes", "O FROID aplica segregação lógica, RLS, auditoria e controles de acesso. A clínica deve comunicar erros de permissão e cooperar na resposta a incidentes e solicitações de titulares."],
            ["Entrada, desligamento e exportação", "A organização responde pelo ciclo de vida de seus membros. O desligamento remove novos acessos sem apagar automaticamente prontuários sujeitos à custódia institucional, obrigações legais ou solicitações em análise."],
            ["Cobrança e limites", "Pacote, sessões, moeda, preço e recursos são os apresentados na ordem. Recarga automática é opcional. " + COMMON_LIMITS],
        ],
    },
    "patient_tcle": {
        "title": "TCLE — Uso do FROID pelo Paciente",
        "audiences": ["patient"],
        "sections": [
            ["O que é o FROID", "O FROID apoia o profissional por meio de métricas de voz, sinais faciais, transcrição e organização longitudinal. Seus resultados são estimativas sujeitas a ruído, contexto, iluminação, equipamento, idioma e qualidade da conexão."],
            ["O que acontece na sessão", "Conforme as autorizações escolhidas, a sessão pode transmitir e processar voz, vídeo, face, transcrição e conteúdo falado pelo paciente e pelo profissional. Parte do cálculo ocorre no navegador; outros dados podem trafegar e ser processados ou armazenados na infraestrutura e nos fornecedores descritos na Política de Privacidade."],
            ["Finalidade", "Os dados servem para apoiar o profissional responsável, produzir relatório, acompanhar evolução, proteger a sessão e manter registros autorizados. Pesquisa anonimizada e compartilhamento externo não são necessários para o atendimento e exigem escolha separada."],
            ["Escolha e revogação", "O paciente pode recusar autorizações opcionais e alterar autorizações futuras no Portal do Paciente. A recusa de processamento necessário pode impedir determinadas funcionalidades, sem retirar direitos sobre dados já tratados legitimamente ou registros cuja guarda seja obrigatória."],
            ["Limitações e emergência", COMMON_LIMITS + " O FROID não monitora continuamente crises e não substitui serviços de emergência. Em risco imediato, procure os serviços locais de urgência."],
            ["Direitos e contato", "O paciente pode consultar resultados, autorizações e solicitações no Portal do Paciente e contatar o profissional, a clínica ou o contato de privacidade do FROID."],
        ],
    },
}


DOCUMENT_TEMPLATES["research_tcle"] = {
    "title": "TCLE — Participação no Estudo de Validade dos Indicadores FROID",
    "audiences": ["patient"],
    "sections": [
        ["Convite e natureza da participação", "Você está sendo convidado a participar de um estudo que verifica se os indicadores do FROID guardam relação com questionários já validados na literatura, como o PHQ-9 e o GAD-7. Participar é opcional e é uma decisão separada do seu tratamento. Recusar não muda nada no seu atendimento, não altera o que o FROID faz na sua sessão e não é comunicado a ninguém além do registro desta recusa."],
        ["Por que este estudo existe", "Os indicadores do FROID descrevem propriedades medidas da voz e da expressão facial. Eles ainda não foram comparados formalmente com instrumentos validados. Enquanto essa comparação não existir, a resposta honesta sobre a validade deles é que ela ainda não foi estabelecida. Este estudo produz essa comparação."],
        ["O que acontece se você aceitar", "Em algumas sessões, o profissional aplicará um questionário breve, respondido por você, e registrará apenas a pontuação total. Essa pontuação será associada aos valores que o FROID mediu na mesma sessão. Não há procedimento adicional, exame, medicamento nem sessão extra. O questionário é aplicado e interpretado pelo profissional, não pelo FROID."],
        ["Que dados são usados e como", "São usados: a pontuação total do questionário, os valores dos indicadores daquela sessão e informações técnicas de qualidade da captação. A análise trabalha apenas com os pares de números, sem identificação. Não são usados o conteúdo da sua fala, a transcrição, a gravação nem o seu prontuário."],
        ["Riscos e benefícios", "O risco principal é o desconforto de responder perguntas sobre como você tem se sentido; você pode deixar qualquer pergunta em branco ou interromper. Não há benefício direto para você. O benefício esperado é coletivo: permitir que profissionais e pacientes saibam o que os indicadores do FROID de fato medem, ou que não medem o que se supunha."],
        ["Revogação", "Você pode retirar sua participação a qualquer momento, sem justificar e sem qualquer efeito sobre o atendimento. Ao pedir a retirada, os seus pares de dados são eliminados da base do estudo. Resultados já publicados a partir de análises anteriores não podem ser desfeitos, e por isso este documento informa isso antes e não depois."],
        ["Divulgação dos resultados", "Os resultados serão divulgados de forma agregada, sem qualquer identificação. Serão divulgados independentemente do que mostrarem, inclusive se contrariarem a hipótese do estudo. O tamanho da amostra e a direção esperada de cada relação foram definidos antes do início da coleta."],
        ["Responsável e contato", "O responsável pelo estudo é {supplier_identity}. Dúvidas sobre a pesquisa, sobre seus dados ou sobre a retirada da participação podem ser dirigidas a esse contato ou ao profissional que o atende."],
        ["Limites", COMMON_LIMITS],
    ],
}


DOCUMENT_TEMPLATES["nr1_company_contract"] = {
    "title": "Contrato de Prestação de Serviço — FROID NR-1, Riscos Psicossociais",
    "audiences": ["nr1_company"],
    "sections": [
        ["Objeto e finalidade", OBJETO_NR1],
        ["Partes e poderes", "O fornecedor é {supplier_identity}. A contratante é a pessoa jurídica empregadora identificada no cadastro pelo CNPJ, representada por pessoa que declara possuir poderes para contratar. As condições comerciais são as confirmadas na proposta vinculada a este contrato."],
        ["O que a contratante recebe", "Resultados agregados por unidade de avaliação e por dimensão do instrumento; inventário de riscos psicossociais com o conteúdo mínimo do subitem 1.5.7.3.2; plano de ação indicando as medidas a serem introduzidas, aprimoradas ou mantidas, com cronograma, responsáveis, formas de acompanhamento e de aferição de resultados, conforme 1.5.5.2.2; o documento de critérios de gradação, classificação e tomada de decisão exigido por 1.5.4.4.2.2; registro da Avaliação Ergonômica Preliminar com o método nomeado em cada evidência; e, no ciclo seguinte, a comparação de eficácia de cada recorte contra a própria linha de base dele."],
        ["O que a contratante NÃO recebe, e não pode obter por outro caminho", "A contratante não recebe resposta individual de trabalhador, prontuário, dado clínico, diagnóstico, avaliação psicológica de pessoa, escore individual, ranking de pessoas nem qualquer informação que permita identificar quem respondeu o quê. A separação é estrutural e não é uma configuração que se possa desligar: as tabelas de resposta não são legíveis pela aplicação, os papéis do lado do empregador não carregam permissão clínica, e o resultado só é liberado depois de encerrada a coleta e acima dos pisos de coorte. A contratante se obriga a não solicitar, por este ou por qualquer outro meio, informação individualizada de trabalhador obtida na avaliação."],
        ["Obrigações da contratante", "São condição para a execução do serviço, e algumas delas o sistema exige antes de permitir abrir a coleta: manter canal de apoio ao trabalhador real, acessível e sigiloso, com nome e forma de contato; declarar o efetivo de trabalhadores do período de referência; manter atualizada a estrutura de estabelecimentos e setores; definir os critérios de gradação de forma coerente com os demais riscos do seu PGR; assegurar a participação, a consulta e a comunicação aos trabalhadores nos termos de 1.5.3.3, mantendo os registros correspondentes; designar o responsável pelo programa e o encarregado pelo tratamento de dados; e implementar as medidas de prevenção decididas, que são ato dela."],
        ["Pisos de coorte e supressão de resultado", "Nenhum resultado é liberado antes de encerrada a coleta, porque quem observasse o painel a cada nova resposta poderia deduzir a resposta individual por diferença. Nenhum recorte é publicado abaixo dos pisos declarados no documento de critérios, que existem para impedir reidentificação e para sustentar a suficiência técnica da amostra. A contratante reconhece que, se a adesão não alcançar esses pisos, não haverá resultado a liberar naquele recorte, e que essa condição lhe foi informada antes da contratação. Os pisos são escolha metodológica do fornecedor, declarada e fundamentada no documento de critérios, e não exigência da NR-1 — a norma não prescreve taxa de resposta nem tamanho mínimo de coorte."],
        ["Base legal e papéis no tratamento de dados", "O tratamento de dados dos trabalhadores tem por base legal o cumprimento de obrigação legal e regulatória pelo controlador (LGPD, art. 7º, II, e art. 11, II, 'a'), e não o consentimento do trabalhador, que a relação de hierarquia comprometeria. A contratante é controladora quanto à finalidade de cumprir suas obrigações de saúde e segurança do trabalho. O fornecedor atua como operador quanto ao tratamento realizado por conta da contratante e como controlador apenas para finalidades próprias, como cadastro, segurança, faturamento, suporte e defesa de direitos. A participação do trabalhador na coleta é voluntária, e a recusa individual não é comunicada à contratante."],
        ["Ciclo, revisão e prova de eficácia", "A avaliação de riscos é processo contínuo e deve ser revista a cada dois anos, ou em até três anos quando a contratante possuir certificação em sistema de gestão de SST, nos termos de 1.5.4.4.6 e 1.5.4.4.6.1. O prazo é teto e não cadência: a revisão também é devida imediatamente após a implementação de medidas, para avaliação de risco residual; após inovações e modificações no trabalho; quando identificadas inadequação, insuficiência ou ineficácia das medidas; na ocorrência de acidente ou doença relacionada ao trabalho; quando mudarem os requisitos legais; e após solicitação justificada dos trabalhadores ou da CIPA. A comparação de eficácia é entregue independentemente do resultado, inclusive quando indicar que a medida adotada não produziu efeito mensurável."],
        ["Guarda dos documentos", "O histórico de atualizações do inventário de riscos é mantido por, no mínimo, vinte anos, conforme 1.5.7.3.3.1, e essa guarda é aplicada por restrição técnica que impede a exclusão dentro do prazo. Os documentos integrantes do PGR devem estar disponíveis aos trabalhadores interessados, aos sindicatos representantes das categorias profissionais e à Inspeção do Trabalho, nos termos de 1.5.7.2.1, e a contratante é responsável por essa disponibilização."],
        ["Condições comerciais", "O preço acompanha o efetivo declarado e a quantidade de estabelecimentos avaliados, nas condições apresentadas e confirmadas na proposta. Estabelecimento é o endereço que define a unidade de resultado; departamento no mesmo endereço é setor, e não estabelecimento. Alteração relevante de efetivo ou de estrutura pode alterar o valor do ciclo seguinte, sempre mediante nova proposta."],
        ["Limites do serviço", "O questionário caracteriza a exposição e não comprova, isoladamente, a gestão de riscos: seus resultados devem ser tecnicamente analisados e integrados à Avaliação Ergonômica Preliminar e ao inventário de riscos. O FROID não emite parecer jurídico, não substitui a assessoria jurídica da contratante, não realiza avaliação clínica de trabalhador e não gera eventos de eSocial — a exigência aplicável é que o inventário seja coerente com os eventos que a própria contratante envia. A adequação das medidas de prevenção às condições concretas de trabalho é decisão da contratante, assessorada por profissionais com o conhecimento técnico adequado."],
        ["Encerramento e exportação", "Encerrado o contrato, a contratante mantém acesso à exportação dos documentos gerados em seu período de vigência, e o fornecedor mantém os registros cuja guarda seja obrigatória. O encerramento não apaga inventário sujeito ao prazo de guarda, nem registros necessários ao cumprimento de obrigação legal ou à defesa de direitos."],
        ["Propriedade intelectual", "Fábio de Assumpção Benhayon é o autor e titular do FROID. A contratação não transfere código, marca, textos, instrumento, modelos, interfaces, parâmetros ou segredos comerciais. Os documentos produzidos para a contratante — inventário, plano de ação, documento de critérios e AEP — são dela, e podem ser exportados e usados livremente perante a fiscalização e o Judiciário."],
    ],
}


def public_legal_catalog() -> dict[str, Any]:
    supplier = _supplier()
    supplier_identity = (
        f"{supplier['name']}, CPF {supplier['tax_id']}, com endereço em "
        f"{supplier['address']} e contato {supplier['contact_email']}"
        if supplier["configured"] else "fornecedor do FROID (configuração jurídica pendente)"
    )
    documents: dict[str, Any] = {}
    for key, template in DOCUMENT_TEMPLATES.items():
        sections = [
            {
                "heading": heading,
                "body": body.format(
                    supplier_name=supplier["name"] or "fornecedor do FROID",
                    supplier_identity=supplier_identity,
                ),
            }
            for heading, body in template["sections"]
        ]
        rendered = {
            "key": key,
            "version": LEGAL_DOCUMENT_VERSION,
            "title": template["title"],
            "audiences": template["audiences"],
            "sections": sections,
        }
        canonical = json.dumps(rendered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        rendered["sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        documents[key] = rendered
    return {
        "version": LEGAL_DOCUMENT_VERSION,
        "supplier": supplier,
        "documents": documents,
    }


def required_document_keys(account_type: str) -> list[str]:
    # A empresa contratante do NR-1 nao assina contrato de profissional nem de
    # clinica: ela nao presta servico clinico e nao trata prontuario. Os dois
    # contratos do catalogo tem audiencia declarada ("professional" e
    # "organization"), e nenhuma delas e o empregador. Fazer o empregador
    # declarar aceite de um contrato profissional produziria registro juridico
    # falso — pior que nao coletar. Termos e privacidade valem para qualquer um
    # que use a plataforma, e esses continuam.
    #
    # O contrato empresarial de avaliacao NR-1 existe desde 22/08/2026 e diz, no
    # objeto, o que os outros dois nao podiam dizer: que a avaliacao olha para a
    # condicao de trabalho e nunca para a pessoa, e que a responsabilidade pelo
    # GRO continua sendo da empresa.
    if account_type == "nr1_company":
        return ["terms", "privacy", "nr1_company_contract"]
    contract = "organization_contract" if account_type == "organization" else "professional_contract"
    return ["terms", "privacy", contract]
