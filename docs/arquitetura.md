# Arquitetura

## Visão geral

```
Cliente do LoL (LCU)                         ntfy.sh ──push──▶ Celular (app ntfy)
   ▲  https/wss 127.0.0.1:<porta do lockfile>    ▲                 │ botão "Aceitar"
   │  certificado raiz da Riot                   │                 │ (POST com token de uso único)
plataforma/lcu.py ◀── websocket.py, lockfile.py  plataforma/ntfy.py│
   │ eventos                ▲ ações                ▲                 ▼
   ▼                        │                      │         Celular (navegador)
servicos/monitor.py ──▶ servicos/estado.py ──▶ servicos/notificacoes.py   │ http://<ip tailscale>:8766
   │                        │   │                  ▲ dominio/avisos.py    │ (VPN do Tailscale)
   │                        │   └──▶ api/sse.py ───┼──────────────────────┤ /api/eventos
   │                        │                      │                      ▼
   │                  servicos/acoes.py ◀──── api/rotas.py ◀── api/servidor.py + protecao.py
   ▼
dominio/fase.py, selecao.py, campeoes.py (regras puras)
```

O PC tem dois lados:
- **Lado do cliente LoL.** `monitor.py` lê o lockfile, conecta na LCU, assina três eventos (`gameflow-phase`, `champ-select/v1/session`, `matchmaking/v1/ready-check`) e mantém o `Estado`.
- **Lado do celular.** `servidor.py` serve a página e a API, e `notificacoes.py` manda push pelo ntfy.

O `Estado` é o ponto de encontro: o monitor escreve nele, e a API, o SSE e as notificações leem dele.

## Camadas

| Camada | Conhece | Não conhece |
|---|---|---|
| `dominio` | só Python | HTTP, LCU, ntfy, Windows |
| `plataforma` | LCU, ntfy, rede, Windows | HTTP do celular, regras de negócio |
| `servicos` | `dominio`, interfaces `Lcu` e `Notificador` | HTTP, implementações concretas |
| `api` | `servicos` | LCU, ntfy |
| `__main__` | tudo: é quem monta as peças (composição) | — |

`LcuHttp` ↔ `LcuFalsa` e `NotificadorNtfy` ↔ `NotificadorFalso` só são trocados em `__main__.py` (`--simular`) e nos testes. Por isso dá para testar tudo sem o cliente aberto e sem mandar notificações.

## Fases do cliente e o que o app faz

A fase vem de `/lol-gameflow/v1/gameflow-phase`:

| Fase | O app... |
|---|---|
| `None`, `Lobby` | só mostra o estado |
| `Matchmaking` | mostra "Na fila". Se veio de `ChampSelect`: **alguém deu dodge**, aviso. Se veio de uma partida encontrada: alguém recusou, aviso. |
| `ReadyCheck` | **aviso urgente** com Aceitar/Recusar, só se houver dados de ready check (a personalizada passa por esta fase em milissegundos, sem nada para aceitar); ações liberadas. Se voltar para `Lobby`: aviso "você saiu da fila" |
| `ChampSelect` | tela da seleção ao vivo; ações liberadas. Avisos: **planejamento** (declare a intenção), **sua vez** de banir/escolher e, no ARAM, **o campeão sorteado** |
| `GameStart` | **aviso "Partida carregando, volta pro PC!"**; desliga o modo ausente; **para de agir** |
| `InProgress`, `Reconnect`, `WaitingForStats`, `PreEndOfGame`, `EndOfGame`… | só mostra o estado; nenhuma ação é aceita |

As regras ficam em `dominio/fase.py` (pode agir?) e `dominio/avisos.py` (o que avisar em cada transição). As ações levantam `ForaDeFase` (HTTP 409) fora de `ReadyCheck`/`ChampSelect`.

### O que as gravações reais mostraram
- **Planejamento:** na escolha alternada, os primeiros ~24 s são de planejamento (`timer.phase = PLANNING`). O cliente já marca o primeiro ban como "em andamento", mas ainda não dá para banir. Por isso `Selecao.minha_vez` ignora o planejamento, e há um aviso próprio para ele.
- **A sessão chega antes da fase:** o evento de `/lol-champ-select/v1/session` costuma chegar antes do `ChampSelect`, às vezes ainda em `Matchmaking`. O monitor busca a sessão por GET ao entrar na seleção.
- **Personalizada:** às vezes vai de `Matchmaking` direto para `ChampSelect`; outras vezes passa por `ReadyCheck` em milissegundos, sem evento de ready check.
- **ARAM:** começa com uns 15 s de "pick em andamento" sem campeão; depois vem a finalização, com o campeão e o banco.

## Modo ausente

As notificações só saem com o **modo ausente** ligado. Você liga pela página (no celular ou em `localhost:8766`) antes de sair do PC. Ele desliga sozinho quando a partida carrega (`GameStart`) ou quando você desliga na página. A página funciona sempre, com o modo ligado ou não. Ver [ADR 0008](decisoes/0008-modo-ausente-manual.md).

## Fluxo: fila encontra partida, você aceita pela notificação

1. A LCU manda pelo WebSocket `[8, "OnJsonApiEvent_lol-gameflow_v1_gameflow-phase", {"data": "ReadyCheck", ...}]`.
2. `monitor.py` atualiza o `Estado`. `dominio/avisos.py` compara o estado anterior com o novo e gera o aviso `PARTIDA_ENCONTRADA`.
3. Com o modo ausente ligado, `notificacoes.py` pede a `servicos/tokens.py` um token aleatório (válido por ~15 s, uso único) e publica no ntfy, com prioridade máxima, dois botões `http`:
   `POST http://<ip tailscale>:8766/api/ready-check/aceitar` com corpo `{"token": "..."}`.
4. Você toca **Aceitar**. O app do ntfy faz o POST direto do celular, pela VPN do Tailscale.
5. `servidor.py` valida `Host`, `Origin` (o app não manda) e JSON. `rotas.py` aceita **ou** um cookie de sessão válido **ou** o token. O token é consumido na hora.
6. `acoes.py` confere que a fase ainda é `ReadyCheck` e chama `POST /lol-matchmaking/v1/ready-check/accept` na LCU.

O token não dá acesso a mais nada: não abre sessão nem serve para pick/ban. E deixa de valer quando a fase sai de `ReadyCheck`. Ver [ADR 0005](decisoes/0005-ntfy-com-topico-secreto-e-tokens.md).

## Fluxo: sua vez de escolher

1. Cada mudança na seleção chega como evento de `/lol-champ-select/v1/session`. `dominio/selecao.py` converte o JSON em `Selecao`:
   - times (com `cellId`, posição, campeão marcado/confirmado);
   - bans;
   - ação em andamento (quem e o quê);
   - timer: fase + segundos restantes, calculados no recebimento a partir de `adjustedTimeLeftInPhase`.
2. A página recebe o novo estado pelo SSE (`/api/eventos`) e redesenha.
3. Se a ação em andamento é sua (`actorCellId == localPlayerCellId`), `avisos.py` gera `SUA_VEZ_BANIR` ou `SUA_VEZ_ESCOLHER`, uma vez por ação.
4. Na página você busca o campeão (lista de `pickable`/`bannable-champion-ids`) e toca **Marcar**: `PATCH /lol-champ-select/v1/session/actions/{id}` com `{"championId": N}`. O time vê o seu hover.
5. **Confirmar** chama `POST /lol-champ-select/v1/session/actions/{id}/complete`.

No ARAM não há ação de pick. A tela mostra o seu campeão e o banco, com **Reroll** (`POST .../session/my-selection/reroll`) e **Pegar do banco** (`POST .../session/bench/swap/{id}`).

## Segurança

Herdada do desligador (ver o [ADR 0004 de lá](https://github.com/Felipefredbarros/desligador/blob/main/docs/decisoes/0004-pin-com-hash-e-protecao-csrf.md)), com o que muda aqui:

| Camada | O que faz |
|---|---|
| Rede | Escuta só em `127.0.0.1` e no IP do Tailscale; firewall libera 8766 só para `100.64.0.0/10` |
| `Host`/`Origin`/JSON | Bloqueiam DNS rebinding e CSRF (cópia de `api/protecao.py`) |
| Login | PIN (PBKDF2, bloqueio por IP) troca por um **cookie de sessão** `HttpOnly; SameSite=Strict`; só o SHA-256 do token fica salvo ([ADR 0006](decisoes/0006-sessao-com-cookie.md)) |
| Botões da notificação | Token de uso único, só para aceitar/recusar aquele ready check |
| ntfy | Tópico secreto aleatório; a mensagem não leva PIN nem token de sessão |
| LCU | TLS verificado contra o certificado raiz da Riot ([ADR 0004](decisoes/0004-tls-com-certificado-da-riot.md)); senha do lockfile só em memória |

Rotas que leem o estado (`/api/estado`, `/api/eventos`, ícones) também exigem sessão.

## Rede e inicialização

- O servidor escuta em `127.0.0.1` e no IP do Tailscale, **nunca em `0.0.0.0`**. Se o Tailscale ainda não estiver ativo, `__main__` tenta de novo a cada 15 s.
- O monitor procura o lockfile a cada 3 s. Quando o cliente fecha, a conexão cai e ele volta a procurar. Porta e senha mudam a cada abertura do cliente.
- `scripts/instalar.ps1` registra a tarefa "LoL Remoto" no Agendador (logon → `pythonw -m lol_remoto`), libera a porta no firewall só para o Tailscale, pede o PIN e mostra o tópico do ntfy para assinar no celular.

## Onde ficam os arquivos do usuário

| O quê | Onde |
|---|---|
| Configuração (hash do PIN, porta, servidor/tópico do ntfy, pasta do LoL) | `%APPDATA%\LolRemoto\config.json` |
| Sessões (SHA-256 dos tokens + validade) | `%APPDATA%\LolRemoto\sessoes.json` |
| Log (rotativo, 3 × 1 MB) | `%LOCALAPPDATA%\LolRemoto\lol-remoto.log` |

## Limitações conhecidas

- A LCU **não é uma API oficial**. Um patch do LoL pode mudar endpoints ou formatos. Os testes usam gravações reais anonimizadas, o que ajuda a perceber essas mudanças.
- Se o Tailscale do celular estiver desligado (economia de bateria), o botão da notificação não alcança o PC. A notificação diz para abrir a página.
- Nas ranqueadas o cliente pode esconder os nomes dos aliados; aí a tela mostra só a posição e o campeão.
- Swiftplay e Arena não são suportados na v1: a página mostra o estado, mas não as ações específicas desses modos.
