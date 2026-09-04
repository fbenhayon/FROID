---
name: froid-smtp-envio
description: "Como o FROID envia e-mail transacional, qual conta Google funciona e quais NAO funcionam"
metadata: 
  node_type: memory
  type: project
  originSessionId: 463729fd-40b6-4b8a-b778-de8853f61217
  modified: 2026-08-19T00:01:54.644Z
---

Configurado em 18/08/2026, depois de varias tentativas erradas que vale nao repetir.

**O que funciona:** `smtp.gmail.com:587` com STARTTLS, autenticado como
**`froid@froid.com.br`** com senha de app. Variaveis `FROID_SMTP_*` no
`/root/froid-project/.env`; o modulo e `froid-server/froid_mailer.py`.

**O que NAO funciona, e custou tempo:**

- **`fbenhayon@froid.com.br` nao aceita login SMTP** — devolve 535
  BadCredentials. Nao e conta propria para autenticacao.
- **Senha de app gerada com o navegador logado na conta pessoal pertence a
  `fbenhayon@gmail.com`**, mesmo que voce pretendesse outra conta. A tela
  `myaccount.google.com/apppasswords` e por conta e nao avisa em qual voce
  esta. Sintoma: autentica como gmail.com e o Gmail **reescreve o From** para
  `@gmail.com`, ignorando `FROID_SMTP_FROM`.
- **Senha de app exige 2FA ligada na conta.** Sem 2FA a pagina responde "nao
  disponivel para a sua conta" sem explicar o motivo.

**Diagnostico rapido** quando der 535: rodar no contentor um `smtplib.login()`
com a mesma senha contra cada endereco candidato — a resposta diz de quem e a
senha em um comando, sem navegar no browser.

**`.env` so entra com `docker compose up -d froid-backend`.** `restart`
reaproveita o contentor com as variaveis antigas e parece que a mudanca nao
funcionou.

**Pendente:** migrar para o **SMTP relay do Workspace** autenticado pelo IP
`204.168.229.32` — nao depende de senha de app nem de conta individual, e sobe
o limite de 2.000 para 10.000/dia. Enquanto nao migrar, trocar a senha da conta
`froid@froid.com.br` derruba o cadastro de novos profissionais em silencio.

**DNS:** os nameservers de froid.com.br sao `b.sec.dns.br`/`c.sec.dns.br` — a
zona e editada no **Registro.br**, nao no Hetzner nem no Google. Em 18/08/2026
ficaram publicados DKIM (Google), SPF (`v=spf1 include:_spf.google.com ~all`)
e DMARC (`_dmarc`, `p=none`, relatorios para froid@froid.com.br).

Ao mexer nessa zona: o Registro.br publica **em ciclo**, nao na hora — levou
20 min. Consultar o autoritativo (`nslookup -type=txt froid.com.br
b.sec.dns.br`) distingue "ainda nao publicou" de "nao salvou"; o resolvedor
publico so mostra cache e nao serve para esse diagnostico. Ver
[[froid-deploy-topologia]].

**Why:** sem registrar isto, a proxima sessao repete a mesma sequencia de
tentativas — e o sintoma (535, ou remetente trocado) nao aponta para a causa.

**How to apply:** ao mexer em envio de e-mail, conferir primeiro QUAL conta
detem a senha antes de suspeitar do codigo ou do host.
