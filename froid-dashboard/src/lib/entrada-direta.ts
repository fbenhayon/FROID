// Quem chega por um endereço bonito precisa chegar antes de o roteador existir.
//
// O painel usa HashRouter: quem decide a tela é o que vem depois do `#`, e o
// caminho antes dele é ignorado. Mas os links que saem daqui para o mundo —
// convite do trabalhador, portal do paciente, login — são endereços limpos
// (`/avaliacao?token=…`), porque um link com `#` no meio parece armadilha para
// quem o recebe por WhatsApp. Alguém tem de traduzir um no outro.
//
// A tradução existia e rodava DENTRO de um `useEffect` do App. Chegava tarde:
//
//   1. render — o HashRouter é construído; sem `#` na URL ele assume "/"
//   2. a rota "/" não serve para quem não está autenticado e redireciona
//      para o login, escrevendo `#/login` na URL
//   3. só então o efeito rodava — e a primeira linha da função era
//      `if (window.location.hash) return`, guarda escrita para respeitar um
//      `#` que o usuário tivesse digitado. O `#/login` do passo 2 satisfaz
//      essa guarda. A função voltava sem fazer nada.
//
// O trabalhador recebia a tela de login com o token pendurado na URL, e o
// convite morria com ele — sem erro, sem mensagem, sem nada para relatar. Só
// existe uma janela em que essa reescrita é segura, e é ANTES de o React
// montar: ali o `#` ausente ainda significa "ninguém pediu tela nenhuma".
//
// Por isso este módulo é chamado de `main.tsx`, antes do `createRoot`, e não
// de dentro de componente nenhum.

/**
 * Caminhos publicos que existem fora do `#` e precisam virar rota do painel.
 *
 * A chave e o que o Caddy entrega (ver o matcher @app no Caddyfile); o valor e
 * a rota do HashRouter. As duas listas precisam concordar: caminho servido
 * aqui e ausente la vira 404 do site institucional, e o contrario vira esta
 * tela de login com o token na URL.
 */
export const ENTRADAS_DIRETAS: Record<string, string> = {
  "/login": "/login",
  "/entrar": "/login",
  "/cadastro": "/access/register",
  "/access/register": "/access/register",
  "/privacidade": "/privacidade",
  "/politica-de-privacidade": "/privacidade",
  "/termos": "/termos",
  "/termos-de-uso": "/termos",
  "/paciente": "/paciente",
  "/paciente/login": "/paciente",
  "/paciente/portal": "/paciente",
  "/avaliacao": "/avaliacao",
  "/app/login": "/login",
  "/app/entrar": "/login",
  "/app/cadastro": "/access/register",
  "/app/paciente": "/paciente",
  "/app/paciente/login": "/paciente",
  "/app/paciente/portal": "/paciente",
  "/app/avaliacao": "/avaliacao",
};

/**
 * A URL para a qual esta entrada deve ser reescrita, ou `null` para não mexer.
 *
 * Pura de proposito: e a unica forma de testar a ordem sem navegador. Recebe
 * as tres partes da URL em vez de ler `window`, para que o teste possa simular
 * exatamente o estado em que a funcao roda — inclusive o estado errado, com o
 * `#/login` que o roteador escreve quando ela roda tarde demais.
 */
export function alvoDaEntradaDireta(
  pathname: string,
  search: string,
  hash: string,
): string | null {
  // Hash presente significa que alguem — usuario ou roteador — ja escolheu uma
  // tela. Respeitar isso e correto; o defeito nunca foi esta guarda, foi o
  // momento em que ela era consultada.
  if (hash) return null;
  const alvo = ENTRADAS_DIRETAS[(pathname || "").toLowerCase()];
  if (!alvo) return null;
  // A query string viaja junto: o convite do NR-1 carrega ali o token de uso
  // unico, e perde-lo transforma um convite valido num link morto.
  return `/app/#${alvo}${search || ""}`;
}

/**
 * Reescreve a URL do navegador, se for o caso. Chamar ANTES de montar o React.
 */
export function normalizarEntradaDireta(): void {
  if (typeof window === "undefined") return;
  const destino = alvoDaEntradaDireta(
    window.location.pathname,
    window.location.search,
    window.location.hash,
  );
  if (!destino) return;
  window.history.replaceState(null, "", destino);
}
