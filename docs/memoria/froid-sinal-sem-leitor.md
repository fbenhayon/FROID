---
name: froid-sinal-sem-leitor
description: O padrão de defeito que custou um cliente — o sinal existe, ninguém lê — e as travas que agora o acusam
metadata:
  node_type: memory
  type: project
---

Em 26/08/2026 uma consulta real foi perdida: profissional e paciente ficaram esperando um ao outro, cada tela mostrando uma frase diferente e nenhuma dizendo a verdade. O cliente foi embora.

**Não houve regressão.** `LiveSession.tsx` não era tocado desde 11/08, `webrtc.ts` desde 03/08. Os defeitos eram de **16/06** e **22/07**, latentes: só se manifestam **depois de uma queda**. Toda sessão que correu limpa nunca tocou esse caminho.

**O padrão, que apareceu QUATRO vezes no mesmo dia:** um sinal existe, completo e correto, e nada do outro lado o consome.

- servidor emitia `peer-waiting` desde 22/07 — nenhum cliente lia
- servidor publicava `patient_joined` em `/api/session-events` — o Dashboard lia, a tela da sessão não
- três endpoints do NR-1 existiam sem tela (a coleta só começava operando o banco à mão)
- `test_runtime_grants.py` tinha um byte 0x08 no lugar de `\b` desde 05/08 — regex nunca casava, teste passava verde e inútil

**Why:** nenhum deles dá erro, aparece em log ou quebra build. O código está lá, bem escrito e testado; ele só não é alcançado. O sintoma nasce a três camadas de distância — num consultório, ou numa venda que "precisa de configuração conduzida pela equipe".

**O erro de método:** procurava-se quem **emite**. Grepar o emissor encontra o `peer-waiting` no servidor e dá a impressão de que a funcionalidade existe.

**How to apply — a pergunta que acha:** para cada coisa que atravessa a fronteira, **quem a lê, e o que acontece se ninguém ler?** Está em teste agora:

- `tests/test_contrato_da_sinalizacao.py` — toda mensagem de WebSocket precisa de leitor; todo código de fechamento precisa ser conhecido pelo cliente
- `tests/test_rotas_sem_chamador.py` — toda rota HTTP precisa de chamador, ou de linha declarando por quê (117 rotas: 9 por desenho, 9 dívida com data, 1 código morto)
- `tests/test_bytes_de_controle.py` — byte de controle no fonte, que é invisível por construção

**Não restaurar** a condição `destinoDoDashboard !== "/admin" && (` nem a guarda `signalingState !== "stable"` sem o `forcar`: as duas eram "corretas" e produziram os becos. Ver [[froid-infra-producao]] e [[froid-nr1-corporate-module]] para o parente "migration aplicada ≠ funcionando".

**Ainda aberto:** a causa da queda inicial. `connectionState === "failed"` significa ICE sem caminho, o que aponta para o TURN. `froid-turn` tem `profiles: ["webrtc"]` no compose e **não sobe** em `docker compose up` comum. `turn_configured: true` no `/health` só confere se as variáveis estão preenchidas — **não** se o coturn responde. Falta rodar `docker compose ps`.
