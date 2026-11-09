# Leitura facial: relatório por corte e referência individual — 08/11/2026

Decisões do Fábio nesta data: relatório facial por corte, retirar "Medidas
subjacentes" e "Leitura arquivada", limites em link, e criar uma referência
facial individual. O limiar foi deixado à "maneira mais correta": medir antes
de escolher.

## O que mudou

| Onde | O quê |
|---|---|
| `froid-dashboard/src/components/FacialAnalysisPanel.tsx` | Relatório: movimentos por corte (mm:ss, família, quadros, duração, fala no momento), qualidade da captura, estado da referência. AUs fora da tela; limites em link. Ao vivo: sete cartões mantidos, sem AUs. |
| `froid-dashboard/src/lib/facial-analysis.ts` | `groupFacialEventsByCut`, `speechAtSecond`, `contextoFacialParaOExplica`, tipo `FacialBaselineSummary`. |
| `froid-dashboard/src/pages/SessionReport.tsx` | Passa cortes, transcrição e procedência ao painel; envia `report_facial_by_cut` ao FROID Explica (antes nenhum evento facial chegava a ele). |
| `froid-server/froid_facs.py` | `FacialBaseline`: mediana e MAD por AU nos 60 s iniciais com rosto (mínimo 30 quadros); histograma do afastamento; `peak_baseline_delta` em cada evento; `facial_baseline` no snapshot. **Não filtra nada.** |
| `froid-server/knowledge/.../FROID_Leitura_Facial_Relatorio_Por_Corte.md` | Nota nova do Explica, liberada em `tools/liberar_notas_froid.py`. |
| `.../FROID_Ficha_Tecnica_Fluencia_e_Face.md` | Corrigida: dizia que a face media divergência com a voz. |
| Site | `profissionais`, `tecnologia`, `percepcao-clinica`, `froid-explica`. |

Testes: `froid-server/tests/test_facial_baseline.py` (inclui espelho nota ↔ motor)
e `froid-dashboard/src/lib/facial-analysis.test.tsx`.

## Como escolher o limiar (próxima etapa)

O relatório arquiva `facialAnalysis.facial_baseline` (referência, percentis
p50/p90/p95/p99 e máximo do afastamento por AU) e cada evento traz
`peak_baseline_delta`.

1. Juntar os relatórios de sessões reais gravados depois do deploy, só com
   `facial_baseline.status == "ready"` e captura facial ≥ 50% das amostras.
2. Por AU, olhar a distribuição dos percentis entre sessões: o p95 do
   afastamento é a oscilação comum de um rosto em conversa.
3. Propor o limiar acima dessa oscilação comum e conferir quantos eventos de
   cada família sobreviveriam (`peak_baseline_delta >= limiar`), com o
   profissional revendo alguns trechos da transcrição.
4. Gravar o limiar como constante em `froid_facs.py`, com a origem (sessões,
   datas, critério) no comentário, e só então o relatório passa a omitir o que
   ficar abaixo.

Quantas sessões bastam é parte da decisão do passo 3; não foi fixado aqui.

## Para publicar

1. `froid-site`: `git pull` (bind mount).
2. `docker compose build froid-frontend` e subir — não derruba sessão no servidor.
3. `docker compose build froid-backend` e subir — **derruba sessões em
   andamento**; fazer sem atendimento.
4. FROID Explica: `python tools/liberar_notas_froid.py --manifesto <manifesto>`
   e reindexar com `tools/ingest_approved_sources.py`. Sem isso a nota nova não
   chega às respostas.

## Pendências encontradas, fora deste trabalho

- `test_procedimentos_no_site_e_no_acervo.py` falha: `froid-explica.html`
  perdeu "todos os cortes da sessão", "tabela por corte" e "sob o mesmo acesso
  que a pessoa já tem no painel" no commit `a38982ee`. Restaurar ou atualizar o
  teste é decisão do dono.
- `agenda-garantias.test.ts` (painel) falha por um trecho de código esperado em
  `PapeisV2`.
