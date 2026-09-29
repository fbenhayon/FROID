# FROID Psique V2 — relatório de pré-implementação

> Registro histórico da auditoria V2 de 28/09/2026. O trabalho local posterior está nos relatórios da [Fase 1](psique-v2-fase1-relatorio.md) e da [Fase 2A](psique-v2-fase2a-relatorio.md), com [checklist de execução e aprovações](psique-v2-checklist-execucao.md). As pendências antigas sobre expiração de reservas Trial, ativação clínica e prorrata foram resolvidas pelo anexo V2.1; as regras vigentes estão em [billing V2](psique-billing-v2.md). As afirmações abaixo sobre implementação não iniciada descrevem a data desta auditoria, não o estado atual.

Data: 28/09/2026, America/Sao_Paulo. As consultas remotas ocorreram entre 01:36 e 01:39 UTC de 29/09/2026.

Referência: `C:/Users/Fabio/Downloads/FROID_Psique_Prompt_Final_VSCode_V2.md`, especialmente seções 0 e 59. Escopo exclusivo: FROID Psique.

**Situação:** auditoria e plano apresentados; implementação não iniciada. O inventário LIVE solicitado não pôde ser concluído: o processo do backend de produção carrega credencial de TESTE, e os objetos consultados retornaram `livemode=false`. Isso é uma divergência constatada, não uma inferência a partir do `.env` local. Nenhum objeto Stripe foi criado, editado, arquivado ou excluído.

Este relatório distingue: **constatado** no código/ambiente; **proposto** para implementação após aprovação; **pendente** quando falta evidência ou decisão. Nomes de arquivos/tabelas novos são propostas, não componentes já implementados. Não há migration executável anexada nem criada.

**1. Arquitetura confirmada e limites da auditoria**

- Backend: Python/FastAPI, rotas concentradas em `froid-server/main.py`; persistência organizacional por SQL explícito/psycopg em `tenant_store.py`. Não foi identificado ORM nesses caminhos.
- Painel: React 18, TypeScript, Vite, Tailwind e Vitest, conforme `froid-dashboard/package.json`.
- Bancos/estado: PostgreSQL para domínio organizacional; persistência legada de perfis em arquivos; DuckDB para dados analíticos. V1 possui modos `legacy` e `dual`.
- Autenticação: cadastro/login próprios e Google; verificação de e-mail existente. Não é necessário criar outro sistema de identidade para V2.
- Site: HTML estático com versões PT/EN/ES/FR. Preços atuais são copiados no HTML.
- Stripe: chamadas HTTP no servidor, catálogo V1 em `subscriptions.py`, webhook e reconciliação de Checkout em `main.py`.
- HEAD local examinado: `a82e962a1c9e73803a5f08cd19183af125e0ddd7`. A árvore já estava modificada por outra sessão; essas alterações foram preservadas. Esse HEAD não foi apresentado como versão implantada.
- Ambiente remoto: backend já em execução no projeto `/root/froid-project`. Confirmados `FROID_PERSISTENCE_MODE=dual`, `FROID_TENANT_AUTHORIZATION_MODE=observe`, `FROID_SHARED_CREDITS_MODE=observe`, `FROID_ALLOW_LOCAL_BILLING_FALLBACK=false` e moeda BRL. São fatos da observação, não garantia sobre todos os mecanismos de acesso do produto.
- Banco remoto: consulta direta com `default_transaction_read_only=on`, confirmado por `SHOW transaction_read_only`; apenas schema e registro de migrations. Não foram consultados prontuários, transcrições ou dados de pacientes.

**Atenção ao mecanismo atual de migrations:** `TenantStore.ensure_schema()` aplica arquivos SQL automaticamente (`tenant_store.py:388`). Alguns métodos de leitura o chamam. Por isso o inventário remoto não utilizou esses métodos. Uma futura entrega de migrations no servidor precisa ser tratada como potencial aplicação, mesmo antes de acionar uma flag de produto.

**2. Arquivos exatos envolvidos**

Modificar, com mudanças focadas e preservação dos ramos V1:

| Arquivo | Alteração proposta |
|---|---|
| `froid-server/main.py` | Registrar rotas V2; separar gates de histórico/nova análise; integrar trial, fonte, reserva e autorização também nos caminhos antigos e WebSockets |
| `froid-server/subscriptions.py` | Manter catálogo/semântica V1; delimitar despacho V1/V2 sem trocar valores dos objetos históricos |
| `froid-server/tenant_store.py` | Persistência V2, transações e reconciliação; impedir escrita V1 concorrente em carteira ativada V2 |
| `froid-server/tenant_access.py` | Despachar política pela versão persistida Psique; manter política NR-1 e V1 onde aplicável |
| `froid-server/legal_documents.py` | Novas versões/audiências documentais Psique e preservação dos aceites/hashes V1 |
| `docker-compose.yml` | Encaminhar explicitamente flags, allowlists e configurações V2 ao contêiner |
| `.env.example` e `froid-server/.env.multitenant.example` | Documentar configuração sem valores secretos |
| `froid-dashboard/src/App.tsx` | Separar autenticação/onboarding, autorização e habilitação de análise; histórico acessível sem saldo |
| `froid-dashboard/src/lib/product-choice.ts` | Impedir que trial esgotado signifique expulsão do acervo Psique |
| `froid-dashboard/src/pages/ProfessionalOnboarding.tsx` | Trial sem compra obrigatória; fluxo V2 separado da cortesia V1 |
| `froid-dashboard/src/pages/Settings.tsx` | Créditos, licença e retorno de compra confirmado pelo backend |
| `froid-dashboard/src/pages/ClinicManagement.tsx` | Papéis cumulativos, assentos, supervisão explícita e administrativos ilimitados |
| `froid-dashboard/src/components/AvisoSemSaldo.tsx` | Bloquear apenas análise nova e oferecer compra, sem promessa incompatível com o roteador |
| `froid-dashboard/src/pages/Dashboard.tsx` | Menu/capabilities e CTA de compra |
| `froid-dashboard/src/pages/ProfessionalDashboardSummary.tsx` | Mesmo contrato de capacidades e compra do restante do painel |
| `froid-dashboard/src/components/panels/AgendaDoProfissional.tsx` | Consumir Appointment interno para organizações V2 |
| `froid-dashboard/src/components/panels/AgendaReminderBanner.tsx` | Lembretes do domínio interno, com estado de sincronização separado |

Pontos de integração a revisar e alterar somente onde o fluxo exigir: `froid-dashboard/src/pages/LoginPage.tsx`, `AccountAccessPages.tsx`, `NewPatient.tsx`, `PatientDetail.tsx`, `History.tsx`, `SessionReport.tsx`, `LegalPages.tsx`; `froid-dashboard/src/lib/api.ts`, `contexto-organizacao.ts`, `session-report.ts`, `legal.ts`. São arquivos existentes, não autorização para reescrever telas inteiras.

`froid-dashboard/src/pages/LiveSession.tsx` contém trabalho de outra sessão. O futuro ponto de integração de identidade/reserva deve ser coordenado com esse trabalho. Os arquivos de gráficos e motores clínicos já modificados não fazem parte desta entrega.

Novos arquivos propostos no backend:

- `froid-server/psique_pricing.py`: catálogo, hash, vigência e cálculo em centavos.
- `froid-server/psique_billing.py`: compras, licença, assentos e reconciliação.
- `froid-server/psique_credits.py`: máquina de crédito, reserva, consumo, liberação e restauração.
- `froid-server/psique_trial.py`: elegibilidade, concessão e expiração.
- `froid-server/psique_sources.py`: identidade comercial e integridade da fonte.
- `froid-server/psique_access.py`: permissões/escopos V2.
- `froid-server/psique_scheduling.py`: agenda interna e adaptador Google.
- `froid-server/psique_api.py`: contratos e rotas V2, evitando concentrar toda regra nova em `main.py`.
- `froid-server/tools/backfill_psique_v2.py`: conferência e preenchimento mínimo, modo de diagnóstico sem escrita como padrão.

Novos arquivos propostos no painel:

- `froid-dashboard/src/lib/psique-v2-api.ts`, `psique-permissions.ts`, `psique-analytics.ts`.
- `froid-dashboard/src/hooks/usePsiqueWallet.ts`.
- `froid-dashboard/src/components/psique/PsiqueNavigation.tsx`, `CreditPurchaseDialog.tsx`.
- `froid-dashboard/src/pages/PsiqueCredits.tsx`, `PsiqueOrganizationBilling.tsx`, `PsiqueOrganizationScheduling.tsx`, `PsiqueOrganizationPermissions.tsx`, `PsiqueOrganizationAudit.tsx`.

Site: modificar `froid-site/precos.html`, `en/precos.html`, `es/precos.html`, `fr/precos.html`; `froid-site/faq.html`, `en/faq.html`, `es/faq.html`, `fr/faq.html`; `froid-site/profissionais.html`, `en/profissionais.html`, `es/profissionais.html`, `fr/profissionais.html`; `froid-site/demonstracao.html` e a configuração Psique em `froid-site/site-assets/script.js`. Criar `froid-site/site-assets/psique-pricing-v2.js` e `psique-pricing-v2.css`. O hero solicitado será aplicado à página de preços; não é necessário reescrever a home para cumprir esse requisito.

Os cards e calculadora buscarão catálogo/cotação no backend. Falha da API aparecerá como indisponibilidade, nunca como preço zero ou preço antigo silencioso. Traduções V2 apresentarão BRL, a única moeda definida no anexo; moedas V1 continuam reconhecidas nos contratos históricos. Links `#cortesia`, metadados e FAQ serão atualizados junto dos cards. Páginas comerciais NR-1 permanecem fora do escopo.

Documentação a criar após aprovação: `docs/psique-pricing-v2.md`, `docs/psique-billing-v2.md`, `docs/psique-rbac-v2.md`, `docs/psique-stripe-v2.md`, `docs/psique-migration-v1-v2.md`, `docs/psique-scheduling.md`. Este relatório é o único documento criado nesta etapa.

**3. Tabelas exatas a preservar, estender e criar**

Confirmadas no schema remoto: `organizations`, `users`, `organization_memberships`, `membership_roles`, `patients`, `patient_assignments`, `session_reports`, `organization_wallets`, `credit_ledger`, `organization_member_quotas`, `audit_events`, `subscription_plans`, `organization_subscriptions`, `automatic_recharges`, `stripe_webhook_events`.

Preservar identidades, saldos, lançamentos, papéis, contratos e direitos históricos. `organization_subscriptions` atualmente descreve pacote/recarga V1; não será reinterpretada como licença mensal V2.

| Estrutura | Mudança/garantia proposta |
|---|---|
| `organization_wallets` | Acrescentar `reserved_balance`, inicialmente 0; manter `balance`, `version`, `authority`; `0 <= reserved_balance <= balance` |
| `credit_ledger` | Acrescentar versão do modelo, `reserved_delta`, `analysis_source_id`, `purchase_id`, `trial_id`, `reservation_id`, `related_ledger_id`, código/versão/hash comercial e saldo reservado após evento; campos novos nulos nos históricos sem procedência |
| `stripe_webhook_events` | Acrescentar namespace/conta/modo, estado de processamento, hash e erro sanitizado; registros sintéticos V1 permanecem históricos |
| `audit_events` | Reutilizar com eventos tipados e metadata administrativa sanitizada |
| `patients`, `patient_assignments`, `session_reports` | Reutilizar dados; adaptar autorização/projeções para organizações V2, sem alterar conteúdo clínico |
| Nova `psique_organization_settings` | `organization_id`, versões de billing/RBAC, flags por organização e estado de migração; NR-1 não recebe registro V2 |
| Novas `psique_pricing_tables`, `psique_pricing_offers` | Campos da seção 30; versão/hash únicos, vigência, centavos e ofertas imutáveis após publicação |
| Nova `psique_stripe_price_mappings` | Oferta → account/mode/Product/Price; impede misturar TEST/LIVE e reutilizar Price com significado diferente |
| Nova `psique_purchases` | Snapshot comercial imutável, organização, total/créditos, status, Checkout/PaymentIntent/conta/modo; uma Purchase por Checkout |
| Nova `psique_billing_reviews` | Revisão administrativa de dispute/refund externo, sem débito automático na carteira |
| Nova `psique_trials` | Organização, beneficiário quando individual, `started_at`, `expires_at`, 10 concedidos, usados, reservados, expirados e estado |
| Nova `psique_trial_eligibility` | Evidência permanente de benefício anterior por e-mail verificado normalizado e por organização; unicidade e procedência V1/V2 |
| Nova `psique_analysis_sources` | Fonte imutável, organização/carteira proprietária, sessão/material, hash/algoritmo/estado e identidade original |
| Nova `psique_analysis_source_chunks` | Manifesto de blocos recebidos: canal, fluxo, sequência, tamanho e digest; permite recompor integridade após reinício sem armazenar mídia |
| Nova `psique_credit_reservations` | Reserva por fonte/carteira, financiamento trial ou saldo restante, worker/execução, estado e relação com eventos; não é lote de compra |
| Nova `psique_analysis_attempts` | Tentativa de processamento, versão do worker e comprovante de entrega durável; reconcilia relatório em arquivo e confirmação financeira no PostgreSQL |
| Nova `psique_organization_licenses` | Contrato separado, versão/hash, customer/subscription/item, estado, quantidade faturada, quantidade pendente e data de efeito |
| Nova `psique_seat_changes` | Histórico de capacidade clínica, preview, quantidade anterior/nova, versão, idempotência e resultado Stripe |
| Nova `psique_membership_role_grants` | Papéis V2 cumulativos, concedente, vigência/revogação; papéis V1 não são reescritos |
| Nova `psique_clinical_memberships` | Habilitação clínica por membership; um usuário conta uma vez por organização |
| Nova `psique_supervision_assignments` | Supervisor → clínico autorizado, vigência e revogação; vínculo na mesma organização |
| Novas `psique_organization_units`, `psique_unit_memberships` | Unidades Psique, sem reutilizar a estrutura empresarial NR-1 |
| Nova `psique_clinician_availability` | Disponibilidade operacional e exceções |
| Novas `psique_appointments`, `psique_appointment_events`, `psique_appointment_session_links` | Agenda interna, histórico e vínculo com sessão existente |
| Nova `psique_calendar_sync` | Correspondência appointment/evento externo, versão e erro de sincronização visível |
| Nova `psique_outbox` | Eventos pós-transação, sincronização e analytics idempotentes; conteúdo mínimo sem texto clínico |

FKs compostas por organização nas relações de paciente, membro, unidade, fonte e agendamento. Unicidade de consumo por `(organization_id, analysis_source_id)` para `CREDIT_CONSUMPTION`; unicidade de restauração por lançamento original; uma reserva ativa por fonte/carteira; compra única por Checkout no namespace de conta/modo. Unicidade de bloco por `(analysis_source_id, channel, stream_id, sequence)`; mesmo identificador com digest diferente é conflito explícito. Estender `organization_member_quotas` com `reserved_sessions` para honrar cotas administrativas já existentes nas organizações migradas: verificar `consumed_sessions + reserved_sessions` dentro do lock. Não criar nova franquia/limite de conta a partir do tamanho do pacote. Não criar `credit_grants`, `credit_lots`, FIFO ou outra wallet.

**4. Contratos de API propostos**

Prefixo uniforme: `/api/psique/v2`. Organização autenticada obrigatória nas operações privadas; quando o ID estiver na URL, conferir igualdade com o contexto autorizado. O corpo não define preço, quantidade de créditos, permissões ou identidade comercial já existente.

| Método e rota | Contrato |
|---|---|
| `GET /pricing` | Público: versão/hash/moeda/vigência e seis ofertas com `product_code`, `credits`, `total_cents`; FLEX explicitamente indisponível enquanto flag falsa |
| `GET /organization-license/quote?clinical_seat_count=n` | Simulação pública em centavos; decomposição por faixa; para 201+ retorna `enterprise_required=true`, sem preço self-service |
| `GET /wallet` | `balance`, `reserved_balance`, `available_balance`, versão, trial e motivo de impedimento de análise; erro não vira zero |
| `POST /checkout` | Corpo comercial somente `{product_code}`; header de idempotência; devolve `purchase_id` e URL Checkout |
| `GET /purchases/{purchase_id}` | Status da compra da organização autorizada; nunca credita pela consulta |
| `GET /capabilities` | Papéis/ações e escopos efetivos do membro; sem substituir verificação no servidor |
| `POST /analysis-sources` | Referência de sessão/material autorizado; servidor cria/reutiliza identidade e confere duplicidade |
| `POST /analysis-sources/{id}/analyses` | Solicita execução/reanálise com idempotência; reserva interna quando necessária; 402 se faltar crédito para fonte nova |
| `GET /organization-license` | Contrato, quantidade real/faturada/pendente, período e estado financeiro |
| `POST /organization-license/preview` | Operação pretendida sobre membership; contagem derivada do banco; devolve preview versionado |
| `POST /organization-license/changes` | Confirma `preview_id` e versão; reconfere estado; aborta preview desatualizado |
| `GET/POST /organizations/{org}/members/invitations` | Convites com papéis V2; convidado não recebe trial adicional |
| `PATCH /organizations/{org}/members/{id}/roles` | Papéis cumulativos com versão esperada, concessor e auditoria; não permite conceder SUPERADMIN organizacional |
| `POST/PATCH /organizations/{org}/members/{id}/clinical-activation` | Habilitação clínica integrada a preview/cobrança de assento |
| `GET/POST /organizations/{org}/supervision-assignments` | Vínculos explícitos; revogação por ação auditada |
| `GET/POST/PATCH /organizations/{org}/units` | Unidades Psique |
| `GET/POST/PATCH /organizations/{org}/patients` | Projeção administrativa estrita; exclui `legacy_payload` e conteúdo clínico |
| `GET/PUT /organizations/{org}/clinicians/{id}/availability` | Disponibilidade operacional autorizada |
| `GET/POST /organizations/{org}/appointments` | Listagem e criação administrativa; idempotência na criação |
| `GET/PATCH /organizations/{org}/appointments/{id}` | Leitura/edição com `expected_version`; conflito devolve 409 |
| `POST /organizations/{org}/appointments/{id}/cancel` | Cancelamento com histórico; não apaga registro |
| `GET /organizations/{org}/appointments/{id}/history` | Alterações administrativas sem conteúdo clínico |
| `POST /organizations/{org}/appointments/{id}/start-session` | Somente clínico autorizado; liga sessão/fonte, sem dar permissão clínica à secretaria |
| `GET /organizations/{org}/calendar-sync/status` | Estado de espelhamento; credenciais nunca retornam |
| `GET /organizations/{org}/audit-events` | Logs administrativos sanitizados por permissão |
| `POST /stripe/webhook` | Endpoint V2 assinado, distinto do endpoint V1 existente |

Códigos: 401 sem autenticação; 403 sem escopo; 402 somente para nova análise sem crédito; 409 para conflito/duplicidade a resolver/Enterprise; 428 para aceite documental pendente; 503 para dependência indisponível. A indisponibilidade fecha a operação com motivo visível.

Preservar os aceites jurídicos existentes: como o checkout V2 envia somente `product_code`, versão/hash e aceite do resumo deverão estar registrados antes, pelo fluxo de aceite no servidor. Se a oferta mudou, retornar 428/409 e mostrar novo resumo. Não remover a garantia apenas para simplificar o corpo HTTP.

Atualização do app após compra: polling autenticado de Purchase/wallet, encerrado ao confirmar ou desmontar a tela. O redirect mostra “aguardando confirmação” até o webhook ser processado. Timeout mantém compra pendente e possibilidade de retomar, sem induzir segunda cobrança.

**5. Máquina de estados de crédito**

Proposta contábil: `balance` permanece saldo total não consumido; `reserved_balance` é o total comprometido; `available = balance - reserved_balance`. Reserva não é um segundo débito.

| Evento | delta em balance | delta em reserved | Efeito |
|---|---:|---:|---|
| TRIAL_GRANT | +10 | 0 | Concessão única |
| CREDIT_PURCHASE | +N | 0 | Compra confirmada |
| CREDIT_RESERVATION | 0 | +1 | Fonte nova obtém exclusividade antes do processamento |
| CREDIT_CONSUMPTION | -1 | -1 | Entrega faturável durável confirmada |
| CREDIT_RELEASE | 0 | -1 | Falha sem entrega libera reserva |
| CREDIT_RESTORE | +1 | 0 | Devolve consumo indevido, no máximo uma vez por consumo |
| TRIAL_EXPIRATION | -saldo gratuito expirável | 0 | Nunca atinge saldo pago nem reserva sem política definida |
| MANUAL_ADJUSTMENT | +/-N | 0 | Motivo obrigatório, autorização e saldo disponível preservado |

Fonte nova: `AVAILABLE -> RESERVED -> CONSUMED`; falha: `RESERVED -> RELEASED`. Repetição após `CONSUMED` reutiliza o consumo, sem nova reserva ou cobrança. `RESTORED` preserva a evidência do consumo original; reanálise não recria débito para compensar a restauração.

Transações bloqueiam sempre na ordem carteira → trial → fonte/reserva → cota do membro; releem idempotência após lock. Consumo/liberação são transições mutuamente exclusivas. O worker usa identificação de execução e versão para que uma conclusão atrasada não consuma uma reserva já encerrada. Recuperação de worker interrompido precisa confirmar se houve entrega; um timeout sozinho não prova falha nem autoriza cobrança.

O salvamento clínico atual usa JSON criptografado, com espelhamento PostgreSQL que pode falhar separadamente (`main.py:2237,2266`). Portanto não existe atomicidade já pronta entre relatório e wallet. A tentativa V2 terá evidência durável de entrega e reconciliação: relatório preservado, consumo no máximo uma vez após confirmação; interrupção entre os dois passos mantém a reserva em reconciliação, sem descartar relatório nem iniciar segundo débito. Não declarar uma transação distribuída que o sistema não possui.

Reserva, contadores de trial, limites eventualmente existentes e ledger mudam atomicamente. Não manter duas autoridades de saldo em modo dual. Na ativação V2, todos os caminhos que ainda escrevem crédito nessa carteira devem passar pelo adaptador versionado ou ser recusados com motivo explícito.

**6. Implementação do Trial 10/14**

Concessão somente após confirmação de e-mail pelo fluxo próprio ou provedor validado. Normalizar `trim + lowercase`, sem remover pontos ou `+alias`. Convidados usam a carteira da organização e não disparam nova concessão.

Em uma transação: verificar elegibilidade histórica e organização; registrar evidência única; criar trial com `started_at=agora`, `expires_at=agora+14 dias`, `credits_granted=10`, `credits_used=0`; lançar TRIAL_GRANT e atualizar a wallet. Concorrência perde pela constraint, sem segunda concessão.

Proposta para evidência do e-mail: HMAC do valor normalizado, com versão da chave, sem persistir outra cópia aberta desnecessária. Rotação deve manter busca nas versões antigas, inclusive para contas encerradas. Não permitir workers concedendo benefícios simultaneamente com diferentes versões de identidade: suspender concessões durante a rotação e só reabrir após todos os workers consultarem o histórico de chaves e usarem a mesma versão ativa. Busca por hashes antigos, isoladamente, não resolve corrida entre versões. A chave precisa de configuração explícita no compose; sua ausência impede concessão, sem fallback. A evidência de benefício permanece após encerramento da conta, como determina o anexo; a finalidade e retenção devem constar nos documentos apropriados.

Reservas escolhem trial primeiro enquanto `agora < expires_at` e houver quantidade gratuita livre. `credits_reserved` acompanha reservas; `credits_used` só aumenta na conclusão faturável. Comprar PRO não encerra o trial. Expiração é verificada em cada operação relevante e por tarefa idempotente: não depender apenas de um job para impedir uso após o prazo.

Exemplo obrigatório sem reservas pendentes: +10, consome 4, compra +25, expira 6 = saldo 25. Nenhum lançamento de expiração pode alcançar os 25 pagos. Organização recebe 10 no total, independentemente de quantos membros convidar. Histórico de benefício V1 impede novo trial automático.

**Pendência explícita:** o anexo não define reservas de trial em processamento quando vencem os 14 dias. Foi solicitada decisão entre: (A) honrar a reserva iniciada antes do prazo, expirar somente créditos livres e expirar a parcela reservada se falhar; (B) cancelar/liberar essas reservas no prazo, sem debitar créditos pagos automaticamente. A alternativa A muda a fórmula literal `granted-used` durante a existência de reservas; por isso não será adotada silenciosamente. O plano de implementação do caso limítrofe depende dessa decisão.

Restauração de consumo de trial após o vencimento também exige tratamento coerente: proposta de CREDIT_RESTORE com expiração compensatória na mesma transação, sem ressuscitar benefício vencido e sem transformar crédito gratuito em pago. Essa regra integra a aprovação da política de reservas/expiração.

Conta sem saldo mantém login e acervo autorizado; bloqueia apenas nova análise faturável. Acervo não significa acesso a dados de outra pessoa nem dispensa obrigações legítimas de retenção/exclusão. O gate V1 de leitura por 90 dias não será herdado pelo fluxo V2.

**7. analysis_source_id e SHA-256**

`analysis_source_id` será UUID emitido pelo backend, ligado à fonte clínica e à carteira original. Uma sessão mantém essa identidade em todos os cortes, pipelines, modelos, relatórios e reanálises. Reupload idêntico é candidato a duplicidade, não nova cobrança automática. A conferência fica restrita à organização e ao escopo autorizado, sem revelar existência de material de outro cliente.

Para arquivo: SHA-256 incremental dos bytes originais recebidos, com metadados de formato fora do cálculo dos bytes. Para sessão ao vivo: persistir somente digests/tamanhos/ordem/canais dos blocos efetivamente recebidos; calcular SHA-256 de seu manifesto canônico versionado ao fechar a fonte. Retransmissão do mesmo bloco não entra novamente; lacunas ficam declaradas. Esse hash identifica a representação recebida, não uma gravação audiovisual integral inexistente. Não gravar áudio clínico bruto apenas para obter hash. O manifesto permite recuperação após reinício sem inventar bytes perdidos.

Fonte em andamento pode ter hash final ainda indisponível, com estado declarado. Fonte V1 sem bytes/representação confiável recebe procedência “hash não registrado”, nunca SHA de texto substituto apresentado como original. Usar `legacy_session_id` apenas quando sua relação com fonte/consumo foi comprovada. Histórico ambíguo não recebe cobrança automática por reanálise.

Não aceitar do navegador um UUID/hash como prova de propriedade. A relação fonte/sessão/material é conferida no servidor. Hash não será divulgado para analytics comercial. Uma fonte já consumida/restaurada continua reconhecida como já faturada, preservando o limite de uma cobrança.

**8. Matriz RBAC efetiva V2**

| Papel | Administração/agenda | Conteúdo clínico | Financeiro/governança |
|---|---|---|---|
| CLINICIAN | Própria agenda e pacientes autorizados | Próprias sessões e escopo explicitamente autorizado; Explica nesse escopo | Consumo próprio |
| SECRETARY | Agenda, disponibilidade, cadastro administrativo, confirmação/reagendamento/cancelamento | Negado | Sem financeiro sensível ou gestão de papéis |
| FINANCE | Sem agenda clínica por padrão | Negado | Compras, carteira, faturas, licença e consumo agregado |
| ORG_ADMIN | Membros, papéis, unidades, contratos/configuração | Negado automaticamente; papel clínico adicional ainda exige escopo | Billing organizacional |
| CLINICAL_SUPERVISOR | Dados necessários ao escopo concedido | Somente supervisionados autorizados; escrita não implícita | Sem financeiro global por padrão |
| AUDITOR_COMPLIANCE | Logs e alterações administrativas | Negado por padrão | Auditoria sanitizada |
| SUPERADMIN | Exceção explícita, com motivo e trilha | Sem leitura clínica cotidiana implícita | Gestão excepcional da plataforma |

Papéis são cumulativos. Assento clínico depende da habilitação clínica ativa, não do nome do papel isolado. Dono que atende pode ter ORG_ADMIN + CLINICIAN. Usuário apenas administrativo não é convertido em profissional durante onboarding.

Aplicação em API, queries, WebSockets, exportações e RLS; frontend só apresenta capacidades. Rotas V1 não podem ser bypass para organização V2. A configuração global atualmente `observe` não basta para V2: o ramo V2 precisa negar de fato, sem mudar o comportamento do NR-1.

Policies permissivas PostgreSQL se combinam por OR; simplesmente adicionar uma policy V2 deixa a V1 ampla funcionando. A migration terá de excluir explicitamente organizações Psique V2 do ramo V1 e aplicar o ramo V2, preservando demais organizações. SELECT amplo de `patients.legacy_payload` não será concedido à secretaria. Conexões privilegiadas também precisam de autorização na aplicação.

Documentos/aceites V2 devem descrever a nova matriz. Contratos V1 e testes que registram a regra histórica de gestor/supervisor vendo a clínica inteira não serão apagados nem enfraquecidos.

**9. Modelo Appointment**

`psique_appointments`: `id`, `organization_id`, `patient_id`, `clinician_id` (membership clínico), `unit_id nullable`, `start_at`, `end_at`, `timezone`, `status`, `source`, `created_by`, `updated_by`, `created_at`, `updated_at`, `version`, `idempotency_key`.

Datas em timestamptz e fuso IANA preservado; `end_at > start_at`; FKs compostas garantem mesma organização. Disponibilidade e conflito de horário do profissional são conferidos transacionalmente. Edição concorrente retorna 409, sem sobrescrever silenciosamente. Estado proposto: SCHEDULED, CONFIRMED, IN_PROGRESS, COMPLETED, CANCELLED, NO_SHOW. Reagendamento gera evento com horário anterior/novo.

Histórico de mudança de horário, profissional, unidade e cancelamento é preservado. Vínculo com sessão fica em tabela própria, sem carregar relatório na API administrativa. Google Calendar é espelho por outbox: falha não perde o agendamento, não abre acesso e aparece como pendência. OAuth existente é reaproveitado; secretaria não recebe token Google do clínico.

**10. Cálculo organizacional final**

Inteiros em centavos. Para organização com 1–200 clínicos, base 49900 até 2 e adicionais marginais 11900, 9900, 8900, 7900, 6900, 5900 nas faixas do anexo. Não multiplicar todos os clínicos pela última faixa. Individual sem licença permanece R$ 0 de mensalidade organizacional.

| Clínicos na organização | Mensalidade |
|---:|---:|
| 0 | R$ 0; setup, sem assinatura ativa |
| 1 / 2 | R$ 499 |
| 3 | R$ 618 |
| 5 | R$ 856 |
| 6 | R$ 955 |
| 10 | R$ 1.351 |
| 11 | R$ 1.440 |
| 20 | R$ 2.241 |
| 25 | R$ 2.686 |
| 26 | R$ 2.765 |
| 30 | R$ 3.081 |
| 50 | R$ 4.661 |
| 51 | R$ 4.730 |
| 100 | R$ 8.111 |
| 101 | R$ 8.170 |
| 200 | R$ 14.011 |
| 201+ | Enterprise; sem preço/Checkout self-service |

Contar membership clínico ativo habilitado; excluir convites, suspensos, arquivados e administrativos. Um profissional em duas unidades da mesma organização conta uma vez. Em organizações juridicamente distintas, conta em cada uma.

Manter separadas contagem real, faturada e pendente. Aumento exige preview e cobrança imediata; redução agenda próxima competência sem crédito no meio do ciclo. Uma volta de 10 para 8 clínicos e depois para 9 no mesmo ciclo não pode cobrar novamente o assento já coberto pela quantidade faturada 10: atualizar a quantidade pendente. A passagem de 200 para 201 interrompe self-service e encaminha proposta, sem converter `organization_type` para `enterprise` — esse valor já identifica o NR-1 no código atual.

**11. Inventário Stripe real: resultado e bloqueio LIVE**

Fonte: variáveis do contêiner do backend de produção; confirmado que a credencial do processo PID 1 coincide com a do processo de inspeção. Consultas Stripe exclusivamente GET. Nenhum secret foi impresso. A credencial foi usada apenas para autenticar chamadas ao próprio Stripe.

| Item | Resultado observado |
|---|---|
| Account ID | `acct_1TCUwiAYhukisMIH` |
| Secret key / webhook secret | Presentes; valores omitidos |
| Publishable key no backend | Variável consultada ausente; isso não prova ausência em outro componente |
| Modo da credencial carregada | TEST |
| Products / Prices | 5 / 5, todos ativos, todos `livemode=false`, BRL, `one_time` |
| Customers | 5, todos `livemode=false`; listagem completa, sem nomes/e-mails/IDs pessoais registrados |
| Subscriptions Stripe | 0 na listagem completa desse ambiente de TESTE |
| Webhook | `we_1TuINBAYhukisMIHt9yBg2bY`, `livemode=false`, **disabled** |
| Caminho do webhook | Corresponde a `/api/stripe/webhook` |
| Metadata comercial esperada | Não apareceu nos campos comerciais filtrados dos Products/Prices consultados |

Mapeamento efetivamente carregado:

| Variável V1 | Product ID | Price ID | Total BRL |
|---|---|---|---:|
| STRIPE_PRICE_PRO_10 | prod_UuB36nX9b5pp5r | price_1TuMhNAYhukisMIHXG36XgqJ | R$ 198 |
| STRIPE_PRICE_PRO_25 | prod_UuBBbzM13u5utE | price_1TuMolAYhukisMIHquQya7Gm | R$ 470 |
| STRIPE_PRICE_PLUS_50 | prod_UuBIdfxhMZPyab | price_1TuMwGAYhukisMIHuK2KWgwB | R$ 1.182 |
| STRIPE_PRICE_PLUS_100 | prod_UuBPnMpE9U3MFo | price_1TuN2sAYhukisMIH9LSRXlEu | R$ 2.202 |
| STRIPE_PRICE_MASTER_25 | prod_UuBWYvIG9h88iq | price_1TuN95AYhukisMIHGONXY4wv | R$ 20 |

O webhook desabilitado tem uma lista extensa de eventos, incluindo Checkout síncrono/assíncrono, PaymentIntent, subscriptions, invoices, charge.dispute e refunds, além de famílias alheias ao fluxo Psique. Estar na lista não significa entrega ativa. O handler atual, por sua vez, só trata três tipos: `checkout.session.completed`, `payment_intent.succeeded`, `payment_intent.payment_failed`.

Os totais desses cinco Prices coincidem com o catálogo V1 local examinado. O site anuncia MASTER 200 por R$ 4.888, ausente desse catálogo e dos cinco Prices mapeados; essa pendência já consta em `tests/test_precos_clinicos_espelhados.py:72`. O total PRO10 de R$198 diverge de seu unitário anunciado de R$19,84. Nada disso será corrigido apagando objetos V1.

**Inventário LIVE: não apurado.** A configuração real carregada contradiz a premissa de LIVE do anexo. Não é correto afirmar que há zero clientes/assinaturas LIVE ou que outra configuração não existe. Foi solicitada ao usuário a localização administrativa da configuração LIVE autorizada, sem pedir envio de secrets. Até essa informação e uma nova consulta, account/objetos LIVE permanecem sem confirmação.

**12. Objetos Stripe V2 a criar após aprovação**

Em Test Mode primeiro, isolados dos objetos V1; em LIVE somente após inventário e validação próprios:

| Código | Novo Product | Créditos | Price BRL em centavos |
|---|---|---:|---:|
| FROID_PRO_10 | FROID Psique — PRO 10 | 10 | 19900 |
| FROID_PRO_25 | FROID Psique — PRO 25 | 25 | 46900 |
| FROID_PRO_50 | FROID Psique — PRO 50 | 50 | 91500 |
| FROID_PRO_100 | FROID Psique — PRO 100 | 100 | 169000 |
| FROID_PRO_200 | FROID Psique — PRO 200 | 200 | 318000 |
| FROID_PRO_500 | FROID Psique — PRO 500 | 500 | 745000 |

Todos `one_time`, Checkout `mode=payment`, quantidade 1. Product e Price recebem metadata comercial da seção 34, com `froid_product=psique`, `family=psique_credits`, código, créditos, versão/hash. Os IDs serão obtidos das respostas reais; nenhum ID V2 foi inventado neste plano.

Criar Product separado `FROID Psique — Licença Organizacional`, código FROID_ORG_LICENSE, com Price mensal validado. Customer somente quando houver cobrança; nada Stripe para Trial. FLEX permanece desativado e não cria cobrança por sessão.

Criar endpoint V2 específico após aprovação, com assinatura/conta/modo próprios e apenas eventos necessários. Preservar endpoint/Prices V1 para objetos históricos ainda válidos. Configuração não pode compartilhar equivocadamente secret TEST/LIVE.

**13. Tiered pricing e prorrata**

Preferência: um Price BRL mensal, `licensed`, `tiered`, `graduated`: até 2, flat 49900 e unit 0; até 5, unit 11900; até 10, 9900; até 25, 8900; até 50, 7900; até 100, 6900; faixa final, 5900. A aplicação impede quantity >200; nunca cria/mantém quantity=0.

**Ainda não homologado no Stripe.** A conferência aritmética local não prova preview, arredondamento ou comportamento real das faixas. A próxima fase autorizada deve criar objetos de teste e comparar todos os limites da seção 54, incluidas mudanças de ciclo, fatura pendente e quantidade zero.

Preview e atualização devem usar o mesmo instante de prorrata. Comparar as linhas da licença/prorrata correspondentes, e não o total de uma fatura que possa conter outras cobranças, impostos ou descontos. A documentação oficial recomenda reutilizar `subscription_details.proration_date` para obter o mesmo cálculo: [Stripe — invoice preview](https://docs.stripe.com/api/invoices/create_preview).

Aumento: backend deriva quantidade, calcula esperado, pede preview, confere, registra proposta; confirmação valida versão e atualiza com `proration_behavior=always_invoice`. Divergência aborta antes de cobrar. Falha/ação adicional do pagamento deve aparecer como estado financeiro pendente, sem declarar sucesso.

Redução: `pending_clinical_seat_count` e `effective_at=current_period_end`; aplicar no próximo ciclo sem gerar crédito intermediário. Proposta técnica: programar a mudança futura no Stripe com reconciliação local, evitando depender de um job que execute depois que a fatura já foi emitida. A ida a zero cancela ao término do período, sem assinatura de quantidade zero. Nenhuma redução produz refund automático.

Se um Price graduado falhar nos testes, alternativa: base 49900 mais item de assentos adicionais com faixas deslocadas (3 a 11900, próximos 5 a 9900, próximos 15 a 8900, próximos 25 a 7900, próximos 50 a 6900, próximos 100 a 5900). Essa alternativa também exige testes de preview. Não será escolhida apenas por conveniência.

**14. Fluxo final de webhook**

1. Checkout resolve oferta/snapshot no servidor; browser informa apenas código.
2. Recepção valida assinatura sobre corpo original, account/mode e versão suportada.
3. Persistir inbox/evento único com estado de processamento; resposta 2xx somente após recebimento durável. Falha de persistência retorna erro para nova entrega.
4. `checkout.session.completed` provisiona somente com `payment_status=paid`; meios assíncronos usam `checkout.session.async_payment_succeeded`.
5. Conferir Checkout, Price, moeda, quantidade, total e snapshot da Purchase, sem comparar compra antiga à oferta vigente hoje.
6. Em transação, Purchase única por Checkout, lock na wallet, CREDIT_PURCHASE +N e outbox. Falha reverte tudo; evento recebido não é confundido com evento aplicado.
7. `payment_intent.succeeded` pode ser auditado, mas não concede novamente.
8. App apenas consulta status/saldo confirmado.

Eventos financeiros externos ficam em revisão administrativa, sem remover/conceder créditos: `charge.dispute.*`, `charge.refunded`, `refund.created/updated/failed` quando aplicáveis à versão escolhida. Invoice/subscription atualizam estado da licença, não créditos. Eventos fora de ordem exigem reconciliação com o objeto atual e idempotência por efeito, não só por timestamp. [Stripe — webhooks](https://docs.stripe.com/webhooks)

O endpoint V1 `/api/subscriptions/confirm-checkout` permanece compatível com V1. V2 não usa o retorno do browser como caminho paralelo de concessão.

**15. Migrations em ordem — somente plano**

Último prefixo local/remoto confirmado: 034. Existem pares históricos 010/011; não renumerar. Os nomes abaixo ficam reservados apenas no plano e devem ser reconferidos antes de criar arquivos, pois outras sessões podem avançar a sequência.

| Ordem proposta | Arquivo futuro em `froid-server/migrations/` | Conteúdo |
|---|---|---|
| 1 | `035_psique_v2_pricing.sql` | Settings versionadas, tabelas/ofertas e mapeamento Stripe |
| 2 | `036_psique_v2_purchases.sql` | Compras, revisão financeira e evolução do registro de eventos |
| 3 | `037_psique_v2_trial.sql` | Trial/elegibilidade e constraints de concessão única |
| 4 | `038_psique_v2_credit_state.sql` | Fonte/manifesto, tentativa/entrega, reserva, campos aditivos da wallet/ledger/cotas e índices de unicidade |
| 5 | `039_psique_v2_outbox.sql` | Outbox/auditabilidade antes de funções que a utilizem |
| 6 | `040_psique_v2_credit_functions.sql` | Funções transacionais V2, grants restritos e invariantes; funções V1 preservadas |
| 7 | `041_psique_v2_licenses.sql` | Licença, assentos clínicos e histórico de mudanças |
| 8 | `042_psique_v2_roles_supervision.sql` | Concessões V2, supervisão e políticas condicionadas à versão |
| 9 | `043_psique_v2_scheduling.sql` | Unidades, disponibilidade, Appointment, eventos/vínculos e sincronização |

Alterar CHECKs somente para aceitar os eventos novos, mantendo intacta a interpretação dos antigos. Índices parciais V2 não passam a exigir informação que históricos não possuem. Permissões/RLS integram cada tabela, sem janela de publicação com acesso amplo. Validar migrations em PostgreSQL descartável antes de qualquer entrega no servidor. O mecanismo de autoaplicação atual precisa de barreira de operação documentada, sem disparar migrations por consulta inocente.

**16. Backfill V1 → V2**

Primeiro diagnóstico sem escrita: identificar por fonte comprovável wallet authority, compras, concessões, pendências de consumo, recargas automáticas e papéis. Conferência de saldo deve respeitar reconciliação histórica, não somar contadores de perfis que já alimentaram a wallet.

Não copiar saldo, recriar concessões ou reetiquetar `purchase/refund/consumption` V1 como eventos V2. Elegibilidade histórica pode receber evidência derivada de concessão V1 comprovada, com origem registrada, sem novo TRIAL_GRANT. Fonte sem procedência suficiente recebe pendência de reconciliação, não crédito ou cobrança inventados.

Não inferir que não existem créditos pagos históricos a partir de zero Subscriptions Stripe: compras V1 usam `mode=payment`, e o inventário realizado era TEST. A afirmação do anexo sobre ausência de lotes pagos não dispensa a reconciliação. A solução continua sem lotes.

Opt-in por organização com snapshot de referências/versionamento, recargas V1 e pendências resolvidas explicitamente. Não encerrar recarga autorizada nem introduzir recarga V2 silenciosamente. Não cobrar novamente relatório/material V1 já consumido. Nenhum backfill de dados clínicos é necessário para iniciar o catálogo V2.

**17. Feature flags e configuração**

Flags do anexo: `ENABLE_NEW_PRICING_V2`, `ENABLE_TRIAL_10_V2`, `ENABLE_ORG_LICENSE_V2`, `ENABLE_RBAC_V2`, `ENABLE_ORG_SCHEDULING`, `ENABLE_FLEX_BILLING`, `ENABLE_PRICING_RECOMMENDER`. Todas desligadas por padrão nesta preparação; FLEX permanece falso até projeto de billing próprio.

Complementos propostos: allowlist de organizações Psique V2, seleção explícita account/mode Stripe, referência de webhook V2 e chave de elegibilidade HMAC. Variáveis novas precisam constar em `docker-compose.yml`, não apenas no `.env`.

Flags governam ingresso de novos fluxos, não apagam obrigações existentes. Organização com lançamentos V2 não volta a usar escritor V1 ao desligar pricing. RBAC V2 ativado não pode ser revertido a acesso amplo por uma flag global. Falta de configuração fecha a ação e declara o motivo.

**18. Rollout**

Fase 0: concluir localização/inventário LIVE e decisões remanescentes; aprovar este plano. Fase 1: schema/catálogo e testes locais, sem oferta pública. Fase 2: wallet/trial/fontes em homologação e teste de concorrência. Fase 3: Stripe TEST + compras/licenças/prorrata. Fase 4: RBAC/agenda/aceites V2 com todos os caminhos de acesso protegidos. Fase 5: organizações piloto expressamente selecionadas, com reconciliação. Fase 6: publicação coordenada app/site e objetos LIVE aprovados, seguida de monitoramento.

Pode-se lançar pacotes individuais antes do FLEX. Não anunciar agenda, separação clínica ou licença como disponíveis antes das garantias correspondentes. Não ativar produto V2 por volume global. Não incluir organizações NR-1 no rollout.

Eventos financeiros/ledger/trial são emitidos depois do commit, por outbox. Analytics de UI não confirma compra. Rejeitar nomes, e-mails de pacientes, texto de sessão, URLs com tokens e hash clínico em analytics comercial. Falhas de job, sincronização, cobrança e concessão são observáveis, sem degradação silenciosa.

Contrato mínimo de eventos da seção 50, com idempotência e produtor responsável: `pricing_page_viewed`, `trial_started`, `trial_first_analysis`, `trial_exhausted`, `trial_expired`, `trial_converted`, `pricing_offer_viewed`, `checkout_started`, `checkout_completed`, `checkout_failed`, `credits_purchased`, `credit_reserved`, `credit_consumed`, `credit_released`, `credit_restored`, `credits_balance_low`, `org_license_started`, `org_clinical_seat_added`, `org_clinical_seat_removed`, `org_role_changed`, `org_permission_changed`, `appointment_created`, `appointment_rescheduled`, `appointment_canceled`, `subscription_updated`, `subscription_canceled`. Views/início de Checkout são eventos de UI; confirmações de domínio são eventos do servidor após commit. O limiar de `credits_balance_low` precisa de regra explícita, não de número arbitrário introduzido pelo código.

**19. Rollback**

Antes de transações V2, desativar ingresso e manter schema aditivo é reversível. Depois de compras/reservas V2, o rollback é interromper novas ativações/compras conforme necessário, mantendo leitores/escritores compatíveis para concluir eventos, reservas, histórico e cobranças já assumidas.

Não restaurar backup antigo sobre saldo atual, excluir tabelas/Prices, apagar ledger ou desativar webhook com pagamentos pendentes. Manter processamento dos objetos V2 existentes mesmo com novos checkouts desligados. Se necessário, compensações administrativas explícitas/auditadas, nunca edição de lançamento original.

Rollback de RBAC não pode ampliar leitura clínica; manter a política restritiva vigente. Rollback da sincronização Google mantém agenda interna. Rollback do site não pode reofertar preços antigos para Checkout V2; deve apontar fluxo comercial compatível ou indisponibilidade explícita.

Deploy/rebuild não faz parte desta etapa. Qualquer janela futura considera atendimentos em andamento; dados clínicos não são alvo de rollback comercial.

**20. Testes por fase e resultado desta revalidação**

Executados localmente: **60 testes aprovados, 0 falhas, 0 erros, 0 skips**, em `test_phase3_wallet`, `test_trial_sessions`, `test_credit_exhaustion_preserves_report`, `test_phase4_billing`, `test_tenant_store`, `test_migration_ordering`. Execução com `python -B`, variáveis de banco removidas apenas do processo dos testes; sem importar `main.py` ou carregar `.env`. Esses testes validam garantias V1 existentes; não são evidência de que V2 ou Stripe LIVE funcionam.

Testes futuros propostos:

- `froid-server/tests/test_psique_v2_pricing.py`: seis totais/créditos, hash canônico, vigência, todos os limites 0/1/2/3/5/6/10/11/20/25/26/30/50/51/100/101/200/201.
- `test_psique_v2_trial.py`: verificação de e-mail, concorrência, benefício V1, convidado, 10 por organização, expiração, compra antes de vencer, trial primeiro e reserva atravessando vencimento após decisão.
- `test_psique_v2_credits_postgres.py`: último crédito concorrente, sucesso/liberação concorrentes, worker interrompido, restauração única, reserva sem débito duplo, saldo pago preservado e migração de autoridade.
- `test_psique_v2_sources.py`: cortes/relatórios/reprocessamento/modelo novo sem nova cobrança, upload repetido e hash ausente declarado.
- `test_psique_v2_stripe.py`: assinatura/conta/modo, duplicate event e duplicate Checkout, assíncronos, transação abortada, evento fora de ordem, refund/dispute só revisão, V1 ainda reconhecida.
- `test_psique_v2_licenses.py`: não clínicos, unidades duplicadas, clínica com 1, zero sem subscription, 201+, aumento, redução pendente, preview/prorrata e pagamento que exige ação.
- `test_psique_v2_access.py` e `test_psique_v2_access_postgres.py`: matriz papel/recurso em API e RLS; cross-org; escopo de supervisão; caminhos V1/WS não contornam V2; secretaria sem legacy_payload.
- `test_psique_v2_scheduling.py`: concorrência, disponibilidade, reagendamento, versão, cancelamento, fonte interna e falha/retry de Google.
- `test_psique_v2_migration.py`: backfill repetido sem saldo/concessão duplicados; schema aditivo; V1/NR-1 preservados; rollback operacional.
- `test_psique_v2_site.py`: quatro idiomas, catálogo da API, CTAs, unitários derivados e nenhuma oferta antiga no ramo V2.
- Vitest em contratos/componentes V2: zero/erro não confundidos, histórico sem saldo, checkout envia código, confirmação só após webhook e menu coerente com capabilities.
- E2E A/B/C/D do anexo em ambiente descartável, com navegador real; adicionar configuração de ferramenta E2E na fase autorizada (o painel hoje usa Vitest).

Preservar testes V1, de contrato e de fronteira clínica. Testes PostgreSQL que fazem INSERT/DELETE só podem rodar em banco descartável explicitamente conferido. Regressão NR-1 é validação de não alteração, não autorização para mudar suas regras.

**21. Riscos e pendências remanescentes**

1. **LIVE não apurado:** falta configuração autorizada que permita confirmar `livemode=true`; não publicar pricing pago LIVE com essa lacuna.
2. **Reserva no vencimento do trial:** decisão solicitada ao usuário; nenhuma alternativa aplicada por omissão.
3. **Falha de pagamento de aumento da licença:** V2 determina cobrança imediata, mas não especifica se a nova capacidade aguarda pagamento/SCA nem política de inadimplência. Proposta: estado pendente explícito, sem declarar ativação paga; preservar histórico. Fechar essa política antes de ativar cobrança de assentos.
4. **Sucesso faturável:** fixar garantia técnica de entrega durável de análise/relatório; resultado com ausência de apuração declarada não pode ser automaticamente equiparado a falha ou sucesso comercial sem critério. Falha conhecida sem entrega libera reserva; relatórios já produzidos são preservados.
5. **Prorrata:** faturas/assinaturas teste ainda precisam de prova de equivalência e arredondamento; não homologado apenas pela leitura da documentação.
6. **Contratos e V1:** revisar a política comercial e novos documentos/aceites antes da oferta. O anexo comercial não é validação jurídica da ausência de reembolso padrão.
7. **Ampliação funcional:** “financeiro/repasses” não especifica mecanismo de repasse nem cálculo de remuneração; não criar Stripe Connect ou pagamento a profissionais por inferência.
8. **Recommender:** existe flag, mas não há regra de recomendação definida; permanecer desligado, sem inventar sugestão de produto.
9. **Operação paralela:** LiveSession e motores têm trabalho alheio; integração futura exige conciliação, sem sobrescrever alterações.
10. **Migrations automáticas:** planejar janela/barreira antes de entregar SQL no servidor; flag de negócio sozinha não impede autoaplicação.

**22. Conflitos com o código atual e compatibilidade proposta**

| Conflito constatado | Compatibilidade proposta |
|---|---|
| V1 pacote muda plano/capacidades (`subscriptions.py`, `tenant_store.py:2022`) | Catálogo/Purchase V2 separados; licença mensal própria; V1 continua legível |
| V1 `refund` adiciona crédito | Preservar significado antigo; V2 usa CREDIT_RESTORE |
| V1 cobra ao salvar relatório (`main.py:15277`) e permite pendências | Reserva prévia só para novas fontes V2; preservar relatórios e tratar pendências V1 explicitamente |
| V1 compra encerra trial | Trial V2 independente da compra; manter funções/testes V1 |
| Cortesia V1 por posição de cadastro | Nova elegibilidade 10/14 sem reconcessão histórica |
| Gate comercial/onboarding impede acesso amplo a telas sem saldo (`App.tsx:265`) | Separar direito ao acervo e capacidade de nova análise |
| Leitura V1 pós-assinatura limitada a 90 dias (`main.py:5991`) | V2 não herda expiração de leitura por falta de créditos |
| Owner/admin/supervisor têm acesso amplo em Python e RLS | Política V2 por organização, novos escopos e documentos/aceites; sem ampliar NR-1 |
| Convites contam todos os membros no plano (`tenant_store.py:1249,1342`) | Administrativos ilimitados V2; contar só clínicos habilitados |
| Onboarding atribui owner+professional automaticamente (`tenant_store.py:4646`) | Papel administrativo e habilitação clínica explícitos em V2 |
| `enterprise` organizacional significa NR-1 | Enterprise Psique em atributo comercial separado |
| Agenda depende do Google | Appointment interno como autoridade e Google como espelho |
| Checkout V1 admite reconciliação pelo retorno | V2 provisiona por webhook; retorno apenas consulta |
| Runtime Stripe TEST e webhook disabled | Registrar fato; localizar LIVE e validar antes de qualquer publicação paga |
| Modos atuais de autorização/carteira são observe | Ativação V2 exige enforcement efetivo e única autoridade de saldo |

**Encerramento desta etapa:** relatório e evidências entregues. Implementação, migrations, criação de objetos Stripe e publicação não foram iniciadas. A seção 59 do anexo determina: “PARE após esse relatório” e “Aguarde aprovação explícita para iniciar a implementação”. A próxima execução depende dessa aprovação e da resolução das pendências aplicáveis; a mensagem “continuar” recebida durante a auditoria foi atendida como continuidade deste relatório.
