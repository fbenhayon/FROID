# FROID Psique — RBAC V2

Estado em 29/09/2026: projeto para a próxima fase; nenhuma nova política clínica ou papel V2 implementado. A Fase 1 aplica RLS sem políticas/grants nas quatro tabelas novas, deixando o runtime sem acesso. Isso não equivale a RBAC V2 entregue.

Os papéis e verificações existentes da V1 e do NR-1 foram preservados. `tenant_access.py`, políticas clínicas antigas e rotas não foram alterados nesta entrega.

A futura implementação deve admitir papéis cumulativos e autorizar cada operação no backend. SECRETARY terá agenda sem conteúdo clínico; FINANCE terá billing sem conteúdo clínico; ORG_ADMIN terá gestão organizacional, exigindo papel clínico adicional para conteúdo clínico. CLINICIAN ficará limitado ao próprio escopo; CLINICAL_SUPERVISOR dependerá de vínculo explícito de supervisão.

Comprar créditos ou licença não concede acesso clínico. Trocar de organização não transfere autoria. Falha de infraestrutura não amplia permissões. O empregador não pode ler resposta individual de trabalhador.

Antes de implementar: autorização da fase seguinte, matriz de operações/escopos e testes negativos diretos no backend. Não criar papéis apenas na interface nem reaproveitar automaticamente papéis NR-1. [Relatório da Fase 1](psique-v2-fase1-relatorio.md).
