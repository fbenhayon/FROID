/**
 * A sessão de trabalho vencida, e a frase que a nomeia — escrita uma vez só.
 *
 * Quando o token de login expira, o servidor recusa com 401 e o detalhe
 * `"não autenticado"`. Esse detalhe é correto para quem lê log e inútil para
 * quem está com paciente do outro lado: não diz o que aconteceu nem o que fazer,
 * e em particular não diz que a conta é a MESMA — mandar "entre de novo" sem
 * isso já fez profissional procurar outro login (padrão 2.11).
 *
 * A frase existia em `sessao-presencial.ts`, só no caminho da sessão presencial.
 * O caminho do convite remoto mostrava o detalhe do servidor cru. Duas telas
 * dizendo coisas diferentes sobre o mesmo 401 é o espelho de texto da seção 2.7:
 * a próxima pessoa corrige uma e não sabe da outra. Por isso a frase mora aqui,
 * e quem a exibe a importa.
 *
 * O que ela NÃO faz: não bloqueia nada por antecipação. O portão é o servidor;
 * isto é só o nome do que ele recusou.
 */
export const SESSAO_DE_TRABALHO_EXPIRADA =
  "Sua sessão de trabalho no FROID expirou. Entre de novo nesta mesma conta para abrir o atendimento.";
