# FROID v3.0 - Contexto de Desenvolvimento
**Última Atualização:** 19/05/2026 - 01:30 AM

## 🎯 ESTADO ATUAL DO PROJETO

### ✅ IMPLEMENTADO E FUNCIONANDO:
1. **Affect Burst Detector** (commit a58dd81)
   - 286 linhas, 4 tipos de bursts
   - Localização: `packages/froid-voice/src/analyzers/affect_burst_detector.py`
   
2. **Rota GET /sessions/patient/:patientId** (commit 2165a22)
   - SessionController e SessionService atualizados
   - Sem JWT Auth (rota pública)

3. **Login Funcionando**
   - Email: `fabio.teste@froid.com.br`
   - Senha: `Fabio123@`
   - Professional ID criado manualmente

4. **Dashboard Corrigido**
   - URL da API: `http://204.168.229.32:8001`
   - Arquivo: `packages/froid-dashboard/src/api/client.ts`

### ⚠️ PROBLEMAS CONHECIDOS:
1. Dashboard cai quando há erro no backend
2. AuthService não cria `professional` automaticamente ao registrar
3. Porta 443 (HTTPS) não configurada
4. Firewall do Windows bloqueia porta 80 (só funciona via celular/4G)

### 📝 PRÓXIMAS TAREFAS (PRIORIDADE):
1. **Corrigir AuthService** - Criar user + professional juntos
2. **Timer de 55 minutos** - Aviso aos 50min, cobrança automática
3. **Sistema de convites** - Profissional convida pacientes por email

## 🏗️ ARQUITETURA ATUAL

### Serviços Rodando:
- Dashboard: porta 80 (HTTP)
- Identity Vault: porta 8001 (mapeada de 3001)
- Voice: porta 3002
- Face: porta 3003
- Payment: porta 3004
- PostgreSQL: porta 5432
- Redis: porta 6379

### Servidor:
- IP: 204.168.229.32
- Hetzner: K0514519526
- SSH: root@204.168.229.32

### Banco de Dados:
- PostgreSQL 16
- Database: froid_db
- User: froid
- 149 sessões registradas

## 🔑 CREDENCIAIS FUNCIONANDO:
- Email: fabio.teste@froid.com.br
- Senha: Fabio123@
- Professional ID: existe (criado manualmente)

## 📂 ESTRUTURA IMPORTANTE:


## 🐛 BUGS PARA NÃO ESQUECER:
1. `xargs` adiciona espaços invisíveis nos IDs
2. Foreign key `professionals_userId_fkey` precisa do professional existir
3. Dashboard usa `localhost:3001` por padrão (já corrigido para IP:8001)

## 💡 LIÇÕES APRENDIDAS:
- Sempre criar professional junto com user no registro
- Testar API direto com curl antes de culpar frontend
- Dashboard precisa rebuild após mudanças em src/
- Email como chave principal de identificação (decisão do cliente)
