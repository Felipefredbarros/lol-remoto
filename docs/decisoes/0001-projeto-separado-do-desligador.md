# 0001 — Projeto separado do desligador, com os mesmos padrões

**Status:** aceita · **Data:** 2026-10-10

## Contexto
O [desligador](https://github.com/Felipefredbarros/desligador) já resolve "controlar o PC pelo celular com segurança": servidor HTTP da stdlib, escuta só no Tailscale, PIN com hash PBKDF2, proteção de `Host`/`Origin`/JSON e tarefa no Agendador. O LoL Remoto precisa da mesma base, mas faz outra coisa e tem outro ciclo de vida.

## Decisão
- Repositório e pacote próprios (`lol_remoto`), porta **8766** (a 8765 é do desligador), pastas `%APPDATA%\LolRemoto` e `%LOCALAPPDATA%\LolRemoto`, tarefa "LoL Remoto".
- Os módulos genéricos do desligador são **copiados** e adaptados: `dominio/pin.py`, `api/protecao.py`, `plataforma/rede.py` e partes de `servicos/autenticacao.py`, `api/servidor.py` e `config.py`. Não há biblioteca compartilhada.
- Mesma organização: camadas `dominio`/`servicos`/`plataforma`/`api`, CLAUDE.md, ADRs, pytest, ruff, CI no GitHub Actions.
- O acesso externo segue o [ADR 0002 do desligador](https://github.com/Felipefredbarros/desligador/blob/main/docs/decisoes/0002-tailscale-para-acesso-externo.md): Tailscale, sem nada exposto na internet.

## Consequências
- Cada projeto evolui e é instalado sozinho; um bug em um não derruba o outro.
- Correções de segurança nos módulos copiados precisam ser replicadas à mão nos dois repositórios. São poucos arquivos e mudam pouco; se isso virar trabalho frequente, extrair um pacote comum (novo ADR).
- Os dois servidores rodam lado a lado no mesmo PC sem conflito de porta, pasta ou nome de cookie.
