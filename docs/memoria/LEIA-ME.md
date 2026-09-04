# A memória do projeto

Esta pasta guarda o que o Claude aprendeu sobre o FROID e precisa lembrar entre
sessões: como o deploy funciona de verdade, quais números têm fonte única, quais
suposições já custaram caro, e as regras de conduta que o dono determinou.

`MEMORY.md` é o índice — uma linha por memória. É ele que é carregado no começo
de cada sessão; os arquivos individuais são lidos quando o assunto aparece.

## Por que está no repositório

Até 04/09/2026 estas memórias viviam apenas em
`C:\Users\Fabio\.claude\projects\<projeto>\memory\`, na máquina de quem
trabalhou. Trocar de computador significava começar do zero — e o que se perde
não é código, é o motivo pelo qual o código é como é.

Agora os arquivos moram aqui, versionados, e o caminho que o Claude Code lê é uma
**junção** (link de diretório do Windows) apontando para cá. Os dois caminhos são
o mesmo lugar: escrever por um aparece no outro, e o `git status` mostra a
memória nova como qualquer outra mudança.

## Como preparar outro computador

Depois de clonar o repositório, uma vez por máquina, no PowerShell:

```powershell
$projeto = "c--Users-Fabio-Desktop-FROID-FROID-GITHUB-V5-FROID"   # ver observação abaixo
$vivo = "$env:USERPROFILE\.claude\projects\$projeto\memory"
$alvo = "<caminho do repositório>\docs\memoria"

# Se já existir uma pasta memory com conteúdo, guarde-a antes de substituir:
if (Test-Path $vivo) { Rename-Item $vivo "memory.bak" }

New-Item -ItemType Directory -Force -Path (Split-Path $vivo) | Out-Null
New-Item -ItemType Junction -Path $vivo -Target $alvo
```

Junção não exige privilégio de administrador.

**Observação sobre o nome do projeto:** ele é derivado do caminho onde o
repositório está. Se você clonar em outra pasta, o nome muda. Para descobrir o
correto, abra `%USERPROFILE%\.claude\projects\` e veja qual pasta corresponde ao
caminho novo — ou rode uma sessão do Claude Code na pasta clonada, que ele a cria
sozinho.

## Como conferir que ficou ligado

```powershell
Get-Item "$env:USERPROFILE\.claude\projects\<projeto>\memory" |
  Select-Object Name, LinkType, Target
```

`LinkType` tem de dizer `Junction`, e `Target` tem de apontar para `docs\memoria`.

Confira, porque a falha aqui é silenciosa: sem a junção, o Claude Code cria uma
pasta `memory` vazia e trabalha sem memória nenhuma — sem erro, sem aviso, e a
única manifestação é ele não saber o que já sabia.

## O que NÃO entra aqui

Credencial, chave, token, dado de paciente. Memória é conhecimento sobre o
projeto — decisões, armadilhas, arquitetura, determinações. Se um arquivo daqui
não puder ser lido por qualquer pessoa com acesso ao repositório, ele está no
lugar errado.
