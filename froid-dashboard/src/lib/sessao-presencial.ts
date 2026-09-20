import { apiUrl } from "./api";

/**
 * Quem é o dono da sessão presencial — a pergunta que ninguém fazia.
 *
 * A sessão remota nasce em `POST /api/session-invites`, e é lá que o servidor
 * grava `SESSION_OWNERS[session_id]`. A presencial não passa por ali: o painel
 * gerava o id no próprio navegador e navegava direto para a sala.
 *
 * O servidor exige o dono para deixar abrir os dois WebSockets do profissional
 * — o de sinalização e, o que importa aqui, o de ANÁLISE (`/ws/fusion`), que é
 * por onde chegam F0, MFCC, sub-harmônicos e as AUs. Sem dono registrado ele
 * recusa, e a sessão presencial rodava sem apurar nada. O PCM enviado durante
 * ela era respondido com `session_inactive` e descartado, porque o estado da
 * sessão no servidor só existe depois que aquele socket conecta.
 *
 * `POST /session/create` sempre fez exatamente isto e estava declarado como
 * código morto em `test_rotas_sem_chamador.py` — morto desde que o painel
 * passou a gerar o id no cliente. Era a peça certa sem quem a consumisse
 * (padrão 2.1). Voltou a ter chamador.
 *
 * Falhar aqui INTERROMPE a abertura da sessão, de propósito: entrar numa sala
 * que não pode medir é pior do que não entrar, porque o que não for captado
 * naquele atendimento não se recupera depois.
 */
export async function criarSessaoPresencial(
  headers: Record<string, string>,
): Promise<string> {
  let resposta: Response;
  try {
    resposta = await fetch(apiUrl("/session/create"), {
      method: "POST",
      headers,
    });
  } catch {
    throw new Error(
      "Não foi possível falar com o servidor do FROID para abrir a sessão presencial. Confira a conexão e tente de novo.",
    );
  }
  const corpo = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    if (resposta.status === 401) {
      throw new Error(
        "Sua sessão de trabalho no FROID expirou. Entre de novo nesta mesma conta para abrir o atendimento.",
      );
    }
    throw new Error(
      String(
        corpo?.detail ||
          `Não foi possível abrir a sessão presencial (erro ${resposta.status}).`,
      ),
    );
  }
  const sessionId = String(corpo?.session_id || "");
  if (!sessionId) {
    throw new Error(
      "O servidor aceitou a abertura mas não devolveu o identificador da sessão. Não é seguro seguir: a apuração ficaria sem dono.",
    );
  }
  return sessionId;
}
