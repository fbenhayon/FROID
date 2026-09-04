---
name: froid-aceite-juridico-precondicoes
description: "O aceite de contrato só é gravado se uma chave de 32 bytes existir no servidor — e /ready, que avisa, não é público"
metadata: 
  node_type: memory
  type: project
  originSessionId: 859c6a95-1d7f-4250-b82d-325c6509e3de
  modified: 2026-08-26T02:30:49.996Z
---

Apurado em 25/08/2026, construindo o comprovante de aceite.

**`FROID_LEGAL_AUDIT_HMAC_KEY` precisa ter ao menos 32 bytes.** Abaixo disso `_legal_hmac` devolve string vazia, e até este commit `_record_legal_documents` simplesmente retornava: o cadastro respondia **200**, a caixa de aceite marcada, e **nenhuma prova de aceite existia**. **Produção está OK: 64 bytes, conferido em 25/08/2026.** O `.env` LOCAL tem 13 — não confundir os dois, e não concluir do local que produção está quebrada (quase fiz isso). Como produção sempre teve chave válida, os aceites de cadastro **estão** gravados no livro.

A partir do commit `6a9b511` a gravação recusa com **503** nomeando a variável. É melhor: falha na hora de testar, e não meses depois quando alguém pede o comprovante. Chave curta passaria a quebrar o cadastro, então a checagem vem ANTES de qualquer deploy que toque isso — mas hoje ela passa.

**`/ready` publica `legal_audit_hmac_configured`, e `/ready` NÃO é rota pública.** O Caddyfile encaminha `/api/*`, `/ws/*` e `/health` — `/ready` cai no site estático. Só de dentro:

```
cd /root/froid-project && docker compose exec froid-backend python -c "import os;k=os.getenv('FROID_LEGAL_AUDIT_HMAC_KEY','');print(len(k.encode()),'bytes')"
```

**Segunda pré-condição, e é a que estava desligada: `FROID_LEGAL_ACCEPTANCE_REQUIRED` vale `false` por padrão, e ninguém a ligou em produção** (conferido 26/08/2026 em `/api/legal/documents?jurisdiction=BR`). Com ela desligada as telas não pedem aceite — e foi por isso que o primeiro cadastro real de empresa respondeu 200 com o livro vazio. O servidor **grava** o aceite válido de qualquer jeito (`_validated_legal_acceptances` registra o que é válido mesmo com `required=False`); quem não pedia era a tela.

Não ligar essa variável às pressas: ela é global e governa também `ProfessionalOnboarding`, `Settings` e o TCLE do paciente, onde a dispensa pode ser legítima. A correção certa foi local — `Nr1CompanyOnboarding` passou a exigir o aceite sempre, porque aquela tela **contrata serviço pago**, e catálogo que não carrega passou a bloquear em vez de deixar seguir. Se algum dia ligar a global, testar antes os três fluxos clínicos contra produção.

`supplier.configured` é `true` — sem isso a página do contrato mostra "Configuração jurídica do fornecedor pendente" **na frente do cliente**.

**Why:** é a mesma família de [[froid-espelho-postgres-silencioso]] — caminho que falha em silêncio e cujo sintoma aparece a três camadas de distância. Aqui o sintoma nem aparece: aparece só quando a prova é pedida, que é sempre do lado errado de uma discussão.

**Segundo achado, do mesmo dia:** a aceitação era arquivada na organização derivada do **e-mail**, enquanto empresa NR-1 e clínica vivem na organização derivada do **CNPJ**. Corrigido, mas `legal_acceptance_events` é append-only por gatilho — as linhas antigas guardam o id errado para sempre. Por isso o comprovante procura pelo **sujeito** (HMAC do e-mail), nunca pela organização. Não mudar isso achando que é preferência de estilo.

**Este deploy exige rebuild do backend.** O Dockerfile faz `COPY . .` — não há volume de código. É a exceção à regra de [[froid-deploy-topologia]], que diz que o backend quase nunca precisa entrar.
