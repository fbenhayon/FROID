# Git Marker Cleaner

## Classification

This artifact is archived as a **workspace skill**, not a custom agent.

Reason: it is an on-demand workflow with a bundled executable script. It does not require an autonomous persona, context isolation, or delegation to a separate subagent.

## Version decision

- Version 1: superseded and retired from the active implementation.
- Version 2: retained as the active implementation and hardened with diff3 display, atomic writes, UTF-8 BOM and line-ending preservation, read-error reporting, and exit codes.
- The original downloaded files in `C:\Users\Fabio\Downloads` were not deleted. They remain external backups.

## Operational caution

The resolver is interactive and does not guarantee semantic correctness. Choices that concatenate both sides can still produce invalid code. Review the resulting diff and run the affected project's checks after every resolution.

## Uso real neste projeto — apurado em 04/09/2026

Uma varredura no repositorio inteiro nao encontrou **nenhum** marcador de
conflito, e o historico nao mostra o fluxo de trabalho que os produz: aqui se
commita direto na `main` e o deploy e por `git pull`, sem merges concorrentes.

A ferramenta esta correta e cuidadosa — preserva BOM e fim de linha, escreve de
forma atomica, exige confirmacao antes de tocar em arquivo. Ela so nao tem, hoje,
um problema para resolver.

Fica mantida para o caso de o projeto passar a trabalhar com ramos paralelos ou
mais de uma pessoa editando os mesmos arquivos. **Ela nao faz parte de nenhuma
rotina**, e ninguem deve executa-la esperando que ela ache algo — quem a invocar
sem um conflito real vai receber uma varredura limpa, que e o resultado correto.

## Current location

`.claude/skills/git-marker-cleaner/`
