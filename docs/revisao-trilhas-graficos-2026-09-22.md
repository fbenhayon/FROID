# Revisão das trilhas e dos gráficos — 22/09/2026

Solicitação: somente áudio e vídeo do paciente alimentam os índices. A fala do profissional permanece separada para transcrição, resumo, relatórios e Data FROID.

## Evidência e correções

- O navegador do paciente inicia as capturas PCM e facial usando seu stream local. O stream remoto do profissional é usado para reprodução da chamada, sem entrada nesses capturadores.
- O painel recebe a trilha remota do paciente e cria capturas separadas para sua transcrição. O microfone local inicia a transcrição do profissional.
- Corrigida a condição que podia rotular a fala do profissional como PC quando o áudio remoto desaparecia. Em chamada remota, a origem profissional conserva DR, inclusive com atribuição local antiga PC.
- No modo presencial compartilhado, a ausência de identificação não atribui automaticamente o microfone ao paciente: exige identificação configurada ou seleção manual explícita. Atualizado o teste de contrato que exigia o comportamento antigo, conforme a instrução do dono de 22/09; mantidas as verificações de privacidade e os termos de falibilidade.
- Removida a atribuição textual PC como autorização isolada para alimentar métricas.
- Reproduzido com PCM de teste: uma emissão de 0,4 segundo em um pacote de 1 segundo era diluída por duas janelas silenciosas anteriores no contexto de 3 segundos. A análise de voz agora usa o pacote corrente; o contexto longo permanece apenas para modulação. O limiar de 30% não foi alterado. Isso demonstra um defeito do código, mas não prova sozinho a causa exata dos 13,4% informados pelo usuário.
- Quadros constantes não geram F0 por resíduo numérico da remoção de média.
- IPM usa amostras do servidor com seus tempos, sem misturar o IPM local, sem suavizar as medidas e sem ligar intervalos ausentes. O cabeçalho distingue ausência atual; estatísticas referem-se às amostras visíveis, sem qualidade inferida apenas pela quantidade.
- IDM ausente não desenha pontos neutros. O modo de tempo real usa as zonas atuais.

## Verificação

781 testes do painel passaram na primeira rodada, incluindo seis testes de separação. Depois das mudanças finais de gráfico, passaram 22 testes focados, incluindo três novos de renderização, além do build TypeScript/Vite. Passaram 72 testes locais selecionados de áudio e contrato. Na imagem Docker nova, passaram os 36 testes de áudio disponíveis sem dependências do restante do repositório.

Ativação concluída às 12:51 BRT de 22/09/2026, usando a autorização prévia do dono para interromper consultas. Frontend e backend saudáveis, endpoint público de saúde HTTP 200, hashes do backend ativo conferidos com o manifesto e bundle público igual ao do container: /assets/index-CwU9QVxS.js.

Backup de fontes, manifesto e imagens anteriores: /root/froid-deploy-backups/trilhas-20260922T154945Z. Alterações alheias preservadas por comparação de hashes antes da escrita. Sem commit e sem push.

A variável FROID_DATAMART_FALA_PROFISSIONAL foi consultada no backend ativo e está em 1. Isso confirma habilitação; não é prova de ingestão de uma consulta específica. Nenhuma transcrição clínica foi lida para essa verificação.

Não foi realizada uma chamada real com os dois participantes após a ativação. A confirmação do comportamento nos dispositivos usados pelo profissional e pelo paciente continua sendo uma verificação operacional distinta dos testes e da saúde do servidor.
