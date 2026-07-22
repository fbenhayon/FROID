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


LEGAL_DOCUMENT_VERSION = "2026-07-21.br-pf-v1"


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
    "fundamento de decisão clínica, jurídica, laboral, securitária ou emergencial."
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
        "title": "Contrato de Licença SaaS — Profissional",
        "audiences": ["professional"],
        "sections": [
            ["Partes e contratação", "O fornecedor é {supplier_identity}. O licenciado é o profissional identificado no cadastro. Pacote, quantidade de sessões, moeda e preço são os exibidos e confirmados na ordem eletrônica vinculada a este contrato."],
            ["Responsabilidade profissional", "O licenciado mantém responsabilidade técnica, ética e jurídica por atendimento, diagnóstico, documentos e conduta. Deve revisar transcrições, métricas, alertas e respostas de IA antes de utilizá-los no prontuário ou na tomada de decisão."],
            ["Pacientes e dados", "O profissional deve fornecer informação clara ao paciente, usar a plataforma dentro de sua habilitação e garantir base legal e autorizações adequadas. O FROID preservará a fala e o contexto registrados conforme as autorizações, a finalidade clínica e as regras de retenção aplicáveis."],
            ["Cobrança", "Cada compra corresponde à ordem apresentada antes do Stripe. A recarga automática somente existe quando escolhida separadamente; pode ser desativada para compras futuras, sem alterar recargas já processadas legitimamente."],
            ["Cancelamento e suporte", "Pedidos de cancelamento, cobrança e suporte serão tratados pelo contato informado. Reembolsos e direito de arrependimento observarão a legislação aplicável e a situação concreta da utilização do serviço."],
            ["Limites", COMMON_LIMITS],
        ],
    },
    "organization_contract": {
        "title": "Contrato de Licença SaaS — Clínica ou Organização",
        "audiences": ["organization"],
        "sections": [
            ["Partes e poderes", "O fornecedor é {supplier_identity}. A contratante é a pessoa jurídica identificada no cadastro, representada por pessoa que declara possuir poderes para contratar. As condições comerciais são as confirmadas na ordem eletrônica."],
            ["Governança", "A organização administra proprietários, administradores, supervisores, profissionais e auditores. Deve conceder acesso mínimo necessário, desligar usuários sem demora e definir formalmente responsabilidade técnica, custódia de prontuários e vínculo dos pacientes."],
            ["Dados e instruções", "A clínica define as finalidades clínicas e orienta o tratamento realizado em seu contexto. O FROID executa operações técnicas contratadas e atua como controlador apenas para finalidades próprias, como cadastro, segurança, faturamento, suporte e defesa de direitos."],
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
    contract = "organization_contract" if account_type == "organization" else "professional_contract"
    return ["terms", "privacy", contract]
