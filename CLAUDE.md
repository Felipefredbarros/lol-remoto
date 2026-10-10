# CLAUDE.md

Guia para assistentes de IA (e humanos) trabalharem neste repositório.

## O que é
Servidor Python que roda no PC com Windows, conversa com o **cliente do League of Legends** (LCU API) e deixa você **aceitar a fila e fazer pick/ban pelo celular**, por uma página web acessada pela VPN do **Tailscale** e por notificações do **ntfy**. O app **nunca age dentro da partida**: para de agir quando a partida começa a carregar. Detalhes em [docs/arquitetura.md](docs/arquitetura.md); o “porquê” de cada escolha está em [docs/decisoes/](docs/decisoes/).

Projeto irmão do [desligador](https://github.com/Felipefredbarros/desligador), de onde vêm os padrões de segurança (PIN com hash, `Host`/`Origin`, escuta só no Tailscale).

## Mapa do código (`src/lol_remoto/`)
| Camada | Módulo | Responsabilidade |
|---|---|---|
| entrada | `__main__.py` | Argumentos, log e escolha do comando |
| entrada | `app.py` | Composição: monta estado, monitor, notificações e servidores, e os executa |
| entrada | `trocar_pin.py` | Comando `--trocar-pin` (console, `getpass`) |
| entrada | `comandos.py` | Comandos avulsos: `--gravar`, `--anonimizar`, `--testar-notificacao` |
| entrada | `gravacao.py` | Comando `--gravar`: grava eventos reais da LCU em JSONL (só escuta) |
| entrada | `anonimizador.py` | Comando `--anonimizar`: tira nomes, ids e segredos de uma gravação |
| config | `config.py` | Lê/cria `%APPDATA%\LolRemoto\config.json` (`pin_hash`, porta, ntfy, pasta do LoL) |
| api | `api/rotas.py` | Registro das rotas (`ROTAS`) e mapeamento exceção → status HTTP |
| api | `api/rotas_painel.py` | Login, estado, modo ausente, lista de campeões, teste de notificação |
| api | `api/rotas_cliente.py` | Rotas que agem no cliente: aceitar/recusar, marcar/confirmar, ARAM |
| api | `api/tipos.py` | `Pedido`, `Resposta`, `Dependencias`, erros comuns, exigência de sessão |
| api | `api/visao.py` | Estado → JSON da página (nomes, posições, tempos restantes) |
| api | `api/servidor.py` | Transporte HTTP (stdlib), estáticos, cookie de sessão, timeout, cabeçalhos |
| api | `api/sse.py` | Stream `text/event-stream` do estado (`/api/eventos`) |
| api | `api/protecao.py` | Validação de `Host`/`Origin` (CSRF e DNS rebinding) |
| serviços | `servicos/monitor.py` | Espera o lockfile, conecta na LCU, assina eventos, reconecta |
| serviços | `servicos/estado.py` | Estado atual (fase, seleção, ready check, modo ausente) + assinantes |
| serviços | `servicos/notificacoes.py` | Transforma avisos em notificações (só com o modo ausente ligado) |
| serviços | `servicos/mensagens.py` | Título, texto, prioridade e emoji de cada aviso |
| serviços | `servicos/acoes.py` | Aceitar/recusar, marcar/confirmar campeão, reroll/troca no ARAM |
| serviços | `servicos/autenticacao.py` | PIN × hash + bloqueio por IP |
| serviços | `servicos/sessoes.py` | Tokens de sessão do cookie (só o SHA-256 fica salvo) |
| serviços | `servicos/tokens.py` | Tokens de uso único dos botões da notificação |
| serviços | `servicos/runas.py` | Runas recomendadas: grava na página "LoL Remoto" e põe os feitiços |
| serviços | `servicos/icones.py` | Ícones dos campeões via LCU, com cache em memória |
| domínio | `dominio/fase.py` | Fases do gameflow, transições e “pode agir?” |
| domínio | `dominio/selecao.py` | JSON da sessão de seleção → `Selecao` (times, bans, ação atual, timer) |
| domínio | `dominio/avisos.py` | Regras de quando avisar (ready check, sua vez, dodge, carregando) |
| domínio | `dominio/ready_check.py` | Partida encontrada: estado e a sua resposta |
| domínio | `dominio/runas.py` | Recomendações de runas, Flash no D, corpo da página de runas |
| domínio | `dominio/campeoes.py` | Catálogo de campeões (id → nome) e filtros |
| domínio | `dominio/pin.py` | Formato do PIN, geração e hash PBKDF2-SHA256 |
| plataforma | `plataforma/lockfile.py` | Lê o lockfile do cliente (porta e senha, que mudam a cada abertura) |
| plataforma | `plataforma/websocket.py` | Cliente WebSocket mínimo (RFC 6455) sobre `ssl` |
| plataforma | `plataforma/lcu.py` | `Lcu` (Protocol), `LcuHttp` (HTTPS + eventos), TLS com `riotgames.pem` |
| plataforma | `plataforma/lcu_falsa.py` | `LcuFalsa` para testes e roteiro do `--simular` |
| plataforma | `plataforma/ntfy.py` | `Notificador` (Protocol), `NotificadorNtfy`, `NotificadorFalso` |
| plataforma | `plataforma/rede.py` | Descobre o IP do Tailscale |
| web | `web/` | Interface do celular (HTML/CSS/JS puro, sem build) |

**Regra de dependência:** `__main__`/`app` → `api` → `servicos` → `dominio` / `plataforma`. Nunca o contrário. `dominio` não importa nada do projeto. Só `__main__.py` e `app.py` escolhem implementações concretas.

## Comandos
```powershell
py -m venv .venv
.venv\Scripts\pip install -e ".[dev]"

.venv\Scripts\python -m pytest            # testes
.venv\Scripts\ruff check . ; .venv\Scripts\ruff format .   # lint + formatação

cd src; py -m lol_remoto --simular        # cliente LoL falso com roteiro (http://localhost:8766)
cd src; py -m lol_remoto --simular --config $env:TEMP\teste.json   # sem mexer no config real
cd src; py -m lol_remoto --trocar-pin     # define um novo PIN
cd src; py -m lol_remoto --testar-notificacao   # manda uma notificação de teste ao celular
cd src; py -m lol_remoto --ausente   # app de verdade, já com o modo ausente ligado
cd src; py -m lol_remoto --gravar ..\gravacoes  # grava eventos reais da LCU (para fixtures)
cd src; py -m lol_remoto --anonimizar ..\gravacoes\x.jsonl ..\tests\fixtures\gravacoes\x.jsonl
```

## Regras
1. **Nada dentro da partida.** Ações só nas fases `ReadyCheck` e `ChampSelect` (`dominio/fase.py`); fora delas o serviço levanta `ForaDeFase` (409). Não remova essa trava nem crie ações para outras fases.
2. **Testes nunca falam com a LCU real nem com o ntfy.sh.** Use `LcuFalsa` e `NotificadorFalso`. Contra o cliente real, durante o desenvolvimento, só GETs, a menos que o Felipe esteja jogando e peça.
3. **Runtime só com biblioteca padrão.** Dependências novas só em `[project.optional-dependencies].dev`.
4. **Segredos fora do repo e do log.** Config e sessões ficam em `%APPDATA%\LolRemoto`. Nunca grave nem registre em log: PIN, senha do lockfile, token de sessão, token de uso único, tópico do ntfy.
5. **Fixtures anonimizadas.** Gravações da LCU só entram em `tests/fixtures/` depois de passar pelo anonimizador (sem `puuid`, `summonerId`, nomes, tags). Gravações reais valem mais que JSON montado à mão: o formato real já surpreendeu (ver `docs/roteiro.md`, etapa 7).
6. **Não afrouxe as proteções da API** (`api/protecao.py`, JSON no POST, `SameSite=Strict`, timeout, verificação TLS da LCU) sem um ADR explicando o motivo.
7. **Toda mudança de comportamento vem com teste** em `tests/`. Antes de commitar: `ruff check .`, `ruff format --check .` e `pytest` passando. Nos testes, gere hashes com `gerar_hash(pin, iteracoes=1_000)`.
8. **Decisão de arquitetura nova → ADR novo** em `docs/decisoes/NNNN-titulo.md`. Atualize o `CHANGELOG.md`. Ao concluir uma etapa, atualize o [docs/roteiro.md](docs/roteiro.md).
9. **Commits** em português, [Conventional Commits](https://www.conventionalcommits.org/pt-br/): `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, `ci:`.
10. **Código e mensagens em português**, nomes descritivos; arquivos pequenos (~150 linhas) e com uma responsabilidade.
11. **Scripts `.ps1` só com caracteres ASCII** (o Windows PowerShell 5.1 lê arquivos sem BOM como ANSI e quebra acentos).

## Como adicionar uma nova ação na seleção (ex.: trocar feitiço)
1. `plataforma/lcu.py`: nada, se for só um `PATCH`/`POST` genérico; senão, método novo no `Protocol Lcu`, em `LcuHttp` e em `LcuFalsa`.
2. `servicos/acoes.py`: método que confere a fase (`exigir_fase`) e chama a LCU.
3. `api/rotas_cliente.py`: função de rota; registro em `ROTAS` de `api/rotas.py` (exceções novas em `_STATUS_POR_ERRO`).
4. `web/`: botão chamando a rota.
5. Testes em `tests/test_acoes.py` e `tests/test_api.py`; atualizar `README.md` e `CHANGELOG.md`.

## Como adicionar um novo aviso (notificação)
1. `dominio/avisos.py`: regra pura `(estado_anterior, estado_novo) -> Aviso | None`, com teste.
2. `servicos/mensagens.py`: título, texto, prioridade e emoji do novo tipo.
3. Se puder, confira com uma gravação real (`tests/test_gravacoes_reais.py`).
