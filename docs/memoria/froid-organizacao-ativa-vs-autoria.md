---
name: froid-organizacao-ativa-vs-autoria
description: "A conta do Fábio tem duas organizações no PostgreSQL, e o recorte por organização já apagou o acervo clínico inteiro da tela — os ids reais e como reconhecer o padrão"
metadata: 
  node_type: memory
  type: project
  originSessionId: 1cf3155d-6637-4be1-a7a9-09ade8a937a4
  modified: 2026-09-14T11:23:32.649Z
---

Apurado em 13–14/09/2026, depois de o painel do Fábio mostrar **2 pacientes** com **65 relatórios e 16 pacientes** no disco.

**Os dois ids reais, calculáveis e verificados:**

```
uuid5(NAMESPACE, "organization|fbenhayon@gmail.com") = a3f6b308-8a62-5a9d-bdc8-94b4178ed43e
uuid5(NAMESPACE, "user|fbenhayon@gmail.com")         = e54098f1-a8b9-50eb-8ce7-f18599d74ae0
NAMESPACE = c173f252-e04f-4ca4-a337-39767764c79c   (tenant_store.py)
```

Todos os 62 relatórios dele resolvem para `a3f6b308` — 29 carimbados e 33 sem `organizationId`, que caem no fallback derivado do e-mail. **Mas a organização ativa da sessão dele é `f16bea6c-e373-54bc-9c1a-d004c9bfefd9`**, que não vem do perfil (é `individual`, sem CNPJ): vem do PostgreSQL, porque `FROID_DATABASE_URL` está definida e `_attach_tenant_contexts` pega `contexts[0]` quando o `active_organization_id` não está na lista. Ou seja, **há mais de uma organização vinculada a esse e-mail no banco** — a divergência continua aberta (unificar mexe em qual organização detém o pool de créditos).

**O log do backend é o diagnóstico, não o palpite.** `uvicorn` roda sem `--no-access-log` e cada requisição imprime `froid.http_audit` com `status_code`, `organization_id` e `actor_user_id`:

```
docker compose logs --tail=3000 froid-backend | grep "session-reports" | tail -20
```

`200` + `organization_id` ≠ `a3f6b308` = o servidor respondeu "sucesso" com uma lista que excluiu o acervo. `402`/`503` seria o portão de assinatura (`_require_active_subscription_for_context`), coisa diferente. **Distinguir isso antes de investigar qualquer outra hipótese** — perdi uma rodada inteira propondo o portão de assinatura como causa mais provável.

**O padrão, que é o que importa daqui em diante:** recorte por organização aplicado **antes** de autoria subtrai do profissional o próprio prontuário. Hoje existe `_report_within_context` em `main.py` e as quatro chamadas (listagem, `GET` do relatório, `GET` das métricas, `DELETE`) passam por ela; um teste conta as chamadas. **`_can_access_invite_finance` continua com o defeito** — Devido/Recebido/Pendente podem zerar do mesmo jeito silencioso, e a correção foi bloqueada pelo classificador de segurança por remover checagem de organização de função de controle de acesso. Precisa de autorização explícita do Fábio.

**Why:** o sintoma é sempre o mesmo e nunca se anuncia — HTTP 200, lista vazia, nada no log. E o painel piorava, exibindo cache do navegador no lugar da resposta. Ver [[froid-sinal-sem-leitor]]: existe, é correto, e ninguém consome.

**How to apply:** ao mexer em qualquer autorização sobre relatório, paciente ou recebível, perguntar "isto pode subtrair de alguém o que é dele?" antes de "isto protege de acesso alheio?". As duas perguntas têm respostas diferentes, e só a segunda costuma ser testada. Relacionado: [[froid-espelho-postgres-silencioso]] e [[froid-infra-producao]].
