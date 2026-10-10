# 0002 — LCU API pelo lockfile e WebSocket; nada dentro da partida

**Status:** aceita · **Data:** 2026-10-10

## Contexto
O cliente do LoL expõe uma API local (LCU) em `https://127.0.0.1:<porta>`, com usuário `riot` e senha aleatória. A porta e a senha mudam a cada abertura do cliente e ficam no `lockfile` (`nome:pid:porta:senha:protocolo`) na pasta do jogo. A mesma porta aceita WebSocket (protocolo WAMP 1.0 simplificado) para receber eventos.

A API **não é oficial**: a Riot tolera aplicativos de terceiros que a usam, mas não garante estabilidade e veta automações que joguem ou decidam pelo jogador.

## Decisão
- Ler o `lockfile` (pasta configurável; padrão `C:\Riot Games\League of Legends`) a cada 3 s até ele existir; reconectar quando o cliente fecha.
- Usar o **WebSocket** para eventos (chegam como `[8, nome, {data, eventType, uri}]`) e **REST** para o estado inicial e as ações. Caminhos usados: `/lol-gameflow/v1/gameflow-phase`, `/lol-champ-select/v1/session`, `/lol-matchmaking/v1/ready-check`.
- Assinar o **canal geral** (`[5, "OnJsonApiEvent"]`) e filtrar pelo `uri` exato no app. *Atualização (10/2026):* a primeira versão assinava cada caminho (`OnJsonApiEvent_<caminho>`), mas numa gravação real feita logo depois de o cliente abrir os eventos do ready check nunca chegaram. Por garantia, o monitor também lê o ready check e a sessão da seleção por GET quando a fase muda.
- **Nada dentro da partida.** O app só executa ações nas fases `ReadyCheck` e `ChampSelect`, e toda ação parte de um toque seu no celular. Nada é escolhido ou aceito automaticamente. Ao entrar em `GameStart`, avisa e para.

## Consequências
- Funciona com o cliente oficial sem modificar nada nele e sem ler memória do jogo. Não interage com o Vanguard.
- Patches podem mudar endpoints e formatos. As gravações reais em `tests/fixtures/` (anonimizadas) servem de contrato e ajudam a detectar mudanças.
- A trava de fase fica no domínio (`dominio/fase.py`) e tem teste próprio, para não ser removida sem querer.
