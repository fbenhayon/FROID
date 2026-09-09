import React from "react";

import type { FroidUser } from "../../App";
import { nomeDoClienteAtivo } from "../../lib/contexto-organizacao";

/**
 * A linha de cima de toda tela do NR-1: a etapa e o CLIENTE.
 *
 * O nome da empresa não aparecia em tela nenhuma do módulo. Toda a navegação
 * — campanha, convites, inventário, plano de ação, AEP, eficácia — acontecia
 * sem que nada na tela dissesse SOBRE QUEM. Numa conta que atende mais de uma
 * empresa (o escritório de SST, a consultoria, e desde 09/09/2026 qualquer
 * conta que carregue dois produtos) o efeito é o pior possível: abrir campanha,
 * emitir convite ou gerar inventário no cliente errado é indistinguível, na
 * tela, de fazê-lo no certo. O erro só aparece no documento, depois.
 *
 * Fica ao lado da indicação da etapa, e não em lugar dela: a etapa diz onde a
 * pessoa está no ciclo, o cliente diz de quem é o ciclo. As duas informações
 * são lidas juntas ou nenhuma serve.
 */
export const EtapaNr1: React.FC<{
  user?: FroidUser | null;
  /** A indicação da etapa: "NR-1 · Coleta", "NR-1 · 1.5.7.3.2"... */
  etapa: React.ReactNode;
}> = ({ user, etapa }) => {
  const cliente = nomeDoClienteAtivo(user);
  return (
    <p className="flex flex-wrap items-baseline gap-x-2 text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
      <span>{etapa}</span>
      {/* Sem nome conhecido não se escreve nada — ver `nomeDoClienteAtivo`.
          E o nome sai fora do caixa-alta espaçado da etapa: razão social é
          longa, e 0.24em de tracking a torna ilegível justamente no dado que
          precisa ser conferido de relance. */}
      {cliente && (
        <span className="text-[11px] normal-case tracking-normal text-slate-300">
          · {cliente}
        </span>
      )}
    </p>
  );
};
