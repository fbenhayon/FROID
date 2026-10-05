# Cadastro de profissional em clínica — alinhar ao fluxo de paciente (desenho)

Escrito em 02/10/2026 a partir de leitura do código (duas varreduras). **Nada
implementado.** Para o seu gate, e para você decidir os pontos marcados **DECISÃO**.
Ordem sua (02/10/2026): "ajustar o procedimento de cadastramento de profissionais
a clínicas" usando a mesma ideia do cadastro de paciente — começar o desenho já
(opção B), mantendo a segurança.

## 1. O problema, hoje
- **Convite** (clínica): `/clinica` → `ClinicManagement.tsx` gera
  `POST /api/organizations/{org}/members/invitations {email, roles}`
  ([main.py:10318](../froid-server/main.py#L10318)) → grava `membership_invitations`
  ([002_access_control.sql:3-19](../froid-server/migrations/002_access_control.sql#L3))
  com `invited_email` + `token_hash`; o token aparece uma vez + link de WhatsApp
  para `/entrar-clinica?token=` ([ClinicManagement.tsx:83-93](../froid-dashboard/src/pages/ClinicManagement.tsx#L83)).
- **Resgate**: `/entrar-clinica` é rota **protegida** (exige login ANTES —
  [App.tsx:518-521](../froid-dashboard/src/App.tsx#L518)). `POST
  /api/organization-invitations/accept` exige `_require_current_user`
  ([main.py:10363-10365](../froid-server/main.py#L10363)) e compara o e-mail **da
  sessão** com o `invited_email` (403 se difere —
  [tenant_store.py:1341-1342](../froid-server/tenant_store.py#L1341)).
- **A fricção:** o profissional precisa **já ter conta** (Google, ou senha
  verificada) no **e-mail exato** ANTES de resgatar. O paciente não precisa — ele
  cria a credencial no próprio aceite (`PatientInvitePage` em `/convite/:token`,
  público; `POST /api/session-invites/{token}/accept`,
  [main.py:8800](../froid-server/main.py#L8800)).

## 2. Fronteira (o que entra e o que NÃO entra)
- **ENTRA:** tirar a pré-condição "ter conta antes", guiando o profissional, a
  partir do link do convite, a **entrar/criar conta no e-mail convidado e então
  aceitar**, numa experiência de uma tela — como o paciente.
- **NÃO ENTRA, de propósito:** remover a trava de e-mail
  ([tenant_store.py:1341-1342](../froid-server/tenant_store.py#L1341)); enfraquecer
  a verificação de e-mail; aceitar o e-mail por campo livre do corpo. A guarda de
  acesso clínico fica **intacta**.

## 3. Invariantes de segurança (inegociáveis)
1. **A trava de e-mail fica.** Quem aceita tem de ser, comprovadamente, o
   `invited_email`.
2. **A prova é controle da caixa, não posse do token.** O token viaja no WhatsApp
   — possuí-lo NÃO prova a caixa. Para **acesso clínico** (alto impacto, diferente
   do paciente, que só vê o próprio dado), a prova é a **verificação de e-mail**
   (caminho senha) ou o **`email_verified` do Google** (caminho Google). É a mesma
   âncora do paciente, elevada ao risco do profissional.
3. **`user_id` deriva do e-mail** (`stable_uuid`,
   [tenant_store.py:1353](../froid-server/tenant_store.py#L1353)): conta Google e
   conta senha no mesmo e-mail são a **mesma** identidade de tenant. Por isso a
   verificação é a única barreira entre o portador do token e uma conta só-Google
   existente — ela nunca sai.
4. **Takeover já coberto no backend:** `register` recusa trocar senha de credencial
   **verificada** e manda reset ([main.py:9999-10020](../froid-server/main.py#L9999));
   credencial nova não loga até verificar (login 403,
   [main.py:10140-10149](../froid-server/main.py#L10140)).

## 4. Desenho recomendado — o frontend guia, o backend de segurança fica intocado
Em vez de mexer no endpoint de aceite (que mantém **sessão + trava + verificação**),
muda-se o **caminho** quando um profissional deslogado abre o link:

- Uma **página de aceite sob medida** (evoluir a `EntrarNaClinica` para pública, ou
  uma nova `/aceitar-clinica?token=`) que, para quem não está logado, mostra
  *"Você foi convidado para <clínica> como profissional; entre com o e-mail que
  recebeu o convite para aceitar"* e oferece:
  - **Entrar com Google** (promovido) — o Google prova o e-mail; após o login a
    sessão É o `invited_email` → **auto-aceita**. Serve inclusive para profissional
    novo (o Google cria o usuário no 1º login). Reusa `POST /api/auth/google`
    ([main.py:9881](../froid-server/main.py#L9881)) + o accept atual.
  - **Criar conta / entrar com senha** (fallback) — `register`
    ([main.py:9964](../froid-server/main.py#L9964)) com o e-mail já preenchido →
    verificação de e-mail → ao abrir o link de verificação, o `verify-email` **já
    emite a sessão** ([main.py:10076-10116](../froid-server/main.py#L10076)) → volta
    e **auto-aceita**. Reusa register/login/verify + o accept atual.
- Um **`GET /api/organization-invitations/{token}`** (espelho do GET de paciente,
  [main.py:8760](../froid-server/main.py#L8760)) devolvendo
  `{clinic_name, invited_email, roles, expired?}` para a página preencher o e-mail e
  dizer com qual endereço entrar.
- O **backend de aceite não muda** (main.py:10363, tenant_store.py:1322) — continua
  exigindo sessão, trava e verificação. A página só garante que a sessão correta
  exista antes de chamar o aceite.

Assim a experiência vira de uma tela (como o paciente), a segurança fica **igual ou
melhor**, e o risco da mudança é de **UI**, não de identidade.

## 5. Decisões que são suas (DECISÃO)

> **DECIDIDO pelo proprietário em 02/10/2026:**
> - **D1 = Google + senha**, com "Entrar com Google" em destaque e "Criar conta /
>   entrar com senha" como alternativa.
> - **D2 = e-mail convidado mostrado por inteiro** na página de aceite.
> - **D3 (02/10/2026) = o caminho "criar conta com senha" EXIGE confirmar o
>   e-mail** antes de entrar na clínica (prova de caixa, acesso clínico); o
>   "Entrar com Google" resolve em 1 clique (o Google prova o e-mail).
>
> **EXECUÇÃO (02/10/2026):** a primeira entrega foi a versão *contida* (página
> protegida + "trocar de conta") — NÃO era a similaridade com o paciente que o
> dono pediu. Refeita como **página PÚBLICA** (rota `/entrar-clinica` agora
> pública, espelho de `PatientInvitePage`): cara da clínica, "Entrar com Google"
> em destaque + "Criar conta / entrar com senha" na própria tela, com o e-mail
> fixado no do convite, auto-aceite após a sessão existir. Backend de aceite +
> trava de e-mail intocados; reusa register/google/login + o GET do convite.
>
> **PIVÔ (05/10/2026), depois da 5ª falha.** O modelo "entre logado com o
> e-mail convidado" é estruturalmente incompatível com o uso real: a dona da
> clínica está sempre logada no mesmo navegador, e qualquer tela que consulte a
> sessão a derruba no 403. Ordem do dono: **exatamente o procedimento do
> paciente** (`/convite/:token`). Implementado: novo endpoint público
> `POST /api/organization-invitations/{token}/accept` que cria a conta **no
> e-mail do convite** (ou confere a senha já existente — nunca a redefine) e o
> vínculo com a clínica numa chamada só, devolvendo a sessão; a página deixa de
> olhar a sessão do navegador; o GET informa `has_password` para a tela pedir só
> a senha quando o e-mail já tem acesso (espelho do `password_only` do paciente).
> **Consequência de segurança, assumida como no paciente:** a entrega do link
> pela clínica é a prova — não há confirmação de caixa; a credencial nasce com
> `verified_via: clinic_invitation` para ficar auditável. O D3 anterior
> ("confirmar o e-mail") fica substituído por esta decisão. Google segue em 1
> clique pelo caminho autenticado. O `continue_to`/`seguir` do verify-email
> permanece disponível, mas esta tela não depende mais dele.

- **D1 — Caminhos de autenticação na página de aceite:** Google + senha (Google
  promovido) · só Google · só senha. Depende de como seus profissionais entram.
  *Recomendo Google + senha.*
- **D2 — Mostrar o e-mail convidado na página:** inteiro (mais claro) vs **mascarado**
  (`f***@dominio.com`) + "entre com o e-mail que recebeu o convite". Inteiro revela
  o endereço a quem tiver o token; mascarado é mais discreto. *Recomendo mascarado.*
- **Não é decisão (constraint):** no caminho senha, a **verificação de e-mail é
  obrigatória** — é a prova de caixa que protege o acesso clínico. Não se pula.

## 6. Plano de implementação (após D1/D2)
1. `GET /api/organization-invitations/{token}` (read, espelho do de paciente) + teste.
2. Página de aceite **pública** (evoluir `EntrarNaClinica` ou nova), com os caminhos
   de D1, prefill do e-mail, auto-aceite após a sessão existir; ajustar o roteamento
   (App.tsx) para a rota ser pública preservando o `?token=` no retorno do login.
3. Garantir o encadeamento `verify-email → sessão → accept` (a sessão já nasce no
   verify; a página retorna ao accept).
4. Testes do painel (vitest/`renderToStaticMarkup`) + teste do GET; regressão.
5. **Nada em produção sem você colar**; commit só com "commit"; janela própria
   (rebuild do **frontend** — desloga; backend só se o GET novo exigir).

## 7. Âncoras
- Convite/resgate profissional: `ClinicManagement.tsx:177-214`/`83-93`;
  `main.py:10318` (criar), `10363` (aceitar), `tenant_store.py:1322-1426`
  (`accept_member_invitation`, trava em `1341-1342`); `membership_invitations` em
  `002_access_control.sql:3-19`; rota `App.tsx:518-521`; `EntrarNaClinica.tsx`.
- Modelo paciente: `main.py:8760` (GET), `8800` (accept público, senha no aceite);
  `PatientInvitePage.tsx`, rota pública `App.tsx:317`.
- Auth: `register` `main.py:9964`; `google` `9881`; `login` `10119`;
  `verify-email` `10076` (emite sessão); sessão `_issue_session` `7062`;
  `_current_user_from_request` `5750`. Identidade por e-mail: `stable_uuid`
  `tenant_store.py:34`, uso `1353`.
