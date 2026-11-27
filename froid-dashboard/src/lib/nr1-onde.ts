/**
 * "Onde" vale uma linha do inventário ou do plano de ação (NR-1 1.5.3.1.1.1).
 *
 * Setor: "Estabelecimento / Setor", como sempre foi.
 *
 * Grupo por função (Leitura de Governança, migration 059): o grupo atravessa
 * os endereços, e a linha vale em cada estabelecimento da cobertura. Um só
 * estabelecimento é nomeado; vários são contados, porque listar quarenta lojas
 * numa linha esconde o risco atrás do endereço.
 *
 * Grupo por função SEM cobertura diz isso com todas as letras. É a linha sem
 * "onde" que a fiscalização aponta, e apresentá-la como se estivesse completa
 * seria esconder a pendência de quem precisa resolvê-la.
 */

export type EstabelecimentoDaLinha = {
  id: string;
  name: string;
  headcount: number | null;
};

export type LinhaComLocal = {
  unit_name: string | null;
  site_name?: string | null;
  unit_type?: string | null;
  establishments?: EstabelecimentoDaLinha[] | null;
};

export const SEM_ESTABELECIMENTO = "sem estabelecimento vinculado";

export function ondeDaLinha(linha: LinhaComLocal): string | null {
  if (!linha.unit_name) return null;
  if (linha.site_name) return `${linha.site_name} / ${linha.unit_name}`;
  if (linha.unit_type !== "exposure_group") return linha.unit_name;
  const enderecos = linha.establishments ?? [];
  if (enderecos.length === 0) {
    return `${linha.unit_name} · ${SEM_ESTABELECIMENTO}`;
  }
  if (enderecos.length === 1) {
    return `${enderecos[0].name} / ${linha.unit_name}`;
  }
  return `${linha.unit_name} · lançado em ${enderecos.length} estabelecimentos`;
}
