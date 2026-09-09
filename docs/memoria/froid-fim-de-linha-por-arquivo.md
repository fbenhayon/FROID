---
name: froid-fim-de-linha-por-arquivo
description: core.autocrlf=true faz o fim de linha variar por arquivo na árvore — script de edição que não normaliza casa zero ocorrência
metadata: 
  node_type: memory
  type: project
  originSessionId: 7fc396de-9614-41d8-b43b-e33971ddba3b
  modified: 2026-09-09T18:42:25.134Z
---

`core.autocrlf=true` neste clone. Os blobs no git são todos LF, mas a árvore de
trabalho tem **CRLF em uns arquivos e LF em outros**: qualquer arquivo que uma
sessão anterior reescreveu por Python em modo binário ficou LF, e os demais
seguem CRLF. Em 09/09/2026 `main.py` estava LF e `tenant_store.py`,
`docker-compose.yml` e vários `.tsx` estavam CRLF — no mesmo commit.

O efeito num script de edição: `s.count(padrao)` devolve **0** para um trecho
que está claramente no arquivo, e a mensagem de erro mostra o texto idêntico ao
que se procurou. Parece defeito de aspas ou de indentação, e é só o `\r`.

**Why:** custou duas rodadas de diagnóstico em edições que estavam corretas, e a
tentação em cada uma era reescrever o padrão em vez de olhar os bytes.

**How to apply:** todo script que edita arquivo do repo normaliza na leitura e
restaura na escrita —

```python
def ler(p):
    bruto = open(p, "rb").read().decode("utf-8")
    return bruto.replace("\r\n", "\n"), ("\r\n" in bruto)

def gravar(p, s, crlf):
    open(p, "wb").write((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
```

Ler com `open(p, encoding=...)` (modo texto) também resolve a leitura, mas grava
LF de volta e converte o arquivo inteiro — o commit fica igual (o git normaliza),
a árvore não. Preferir o par acima.

Antes de culpar o padrão: `python -c "d=open(F,'rb').read(); print(d.count(b'\r\n'))"`.

Ver [[froid-heredoc-barra-invertida]] — a outra armadilha de escrita de arquivo
desta máquina, e o mesmo remédio: escrever o script com a ferramenta Write em vez
de heredoc elimina as duas de uma vez.
