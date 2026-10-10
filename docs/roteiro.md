# Roteiro da v0.1.0

Etapas de desenvolvimento, na ordem. Cada etapa vira um ou mais commits. Atualize este arquivo ao concluir uma etapa (status, commit e observações).

Legenda: ✅ concluída · 🔄 em andamento · ⏳ pendente

| # | Etapa | Status | Commit |
|---|---|---|---|
| 0 | Reconhecimento ao vivo da LCU (só leitura) | ✅ | — |
| 1 | Estrutura do projeto (pyproject, ruff, git) | ✅ | `1998026` |
| 2 | Documentação: CLAUDE.md, arquitetura, ADRs 0001–0008 | ✅ | `2c449e1` |
| 3 | Domínio: fases, seleção, avisos, campeões, PIN | ✅ | `545c155` |
| 4 | Cliente WebSocket (stdlib) | ✅ | `e43ff80` |
| 5 | Cliente LCU (lockfile, HTTPS, eventos) + `--gravar` + anonimizador | ✅ | `e9f8282` |
| 6 | Notificador ntfy + config | ✅ | (próximo commit `feat`) |
| 7 | Monitor, estado, notificações e modo ausente | 🔄 | |
| 8 | Ações: ready check, pick/ban, ARAM | ⏳ | |
| 9 | Autenticação: PIN, sessões (cookie) e tokens de uso único | ⏳ | |
| 10 | API HTTP + SSE | ⏳ | |
| 11 | Interface web do celular | ⏳ | |
| 12 | `--simular` com roteiro falso (fila → seleção → carregando) | ⏳ | |
| 13 | Scripts de instalação (Agendador, firewall, PIN, tópico do ntfy) | ⏳ | |
| 14 | CI, README, CHANGELOG e versão 0.1.0 | ⏳ | |

## Detalhes

### 0. Reconhecimento ao vivo ✅
GETs na LCU com o cliente aberto, sem nenhuma ação. Resultados:
- TLS verifica com o `riotgames.pem` só sem `VERIFY_X509_STRICT` (Python 3.13+) → [ADR 0004](decisoes/0004-tls-com-certificado-da-riot.md).
- WebSocket: handshake 101 com `Sec-WebSocket-Protocol: wamp`; assinatura aceita.
- Locale `pt_BR`: `champion-summary.json` já traz os nomes em português; ícones PNG de ~30 KB via `/lol-game-data/assets/v1/champion-icons/{id}.png`.
- Fora da fila, `ready-check` e `champ-select/session` respondem 404 (esperado).

### 3. Domínio ✅
`dominio/fase.py`, `selecao.py`, `avisos.py`, `campeoes.py` e `pin.py` (cópia do desligador), com testes. Por enquanto, as fixtures de sessão (`tests/fixtures/selecao_*.json`) são montadas à mão; na etapa 5 são trocadas por gravações reais.
- O catálogo real tem 250 campeões, com nomes em pt_BR ("Nunu e Willump"). Ele inclui 77 variantes "Jade_" (ids 60001–60267) com o mesmo nome do campeão normal. A busca mostra um por nome, o de menor id.

### 4. Cliente WebSocket ✅
RFC 6455 mínimo sobre `ssl` (`plataforma/websocket.py`), testado contra um servidor WebSocket falso (`tests/servidor_ws_falso.py`): quadros de 0 a 200 KB, fragmentados com ping no meio, close e queda de conexão.
- Conferido na LCU real: ao conectar chega a boas-vindas do WAMP `[0, "<sessão>", 1, "WAMP-1.0-RiotRemoting"]`, que deve ser ignorada.

### 5. Cliente LCU ✅
Leitura do lockfile, HTTPS com o `riotgames.pem`, assinatura de eventos e reconexão. O `--gravar` salva os eventos reais em `gravacoes/`, pasta ignorada pelo git. O anonimizador gera as fixtures sem `puuid`, IDs ou nomes.

- Conferido no cliente real: certificado empacotado, assinatura e GETs funcionando.
- `LcuFalsa` (`plataforma/lcu_falsa.py`): `emitir()` simula eventos e também atualiza o GET daquele caminho.
- O anonimizador confere no fim se algum nome original sobrou na saída; se sobrou, não grava nada.

**Pendente com o Felipe (não bloqueia as próximas etapas):** gravar uma normal alternada (ou ranqueada) e uma ARAM jogando normalmente. A gravação para no carregamento, então não é preciso jogar nem kitar. Uma personalizada também serve, porque sair dela não tem punição.
```powershell
cd src; py -m lol_remoto --gravar ..\gravacoes
py -m lol_remoto --anonimizar ..\gravacoes\gravacao-AAAAMMDD-HHMMSS.jsonl ..\tests\fixtures\gravacoes\draft.jsonl
```

### 6. Notificador ntfy ✅
Publicação em JSON no ntfy.sh com prioridade, link para a página e botões `http` (`plataforma/ntfy.py`). Comando `--testar-notificacao`.
- O `config.py` entrou aqui, antes da etapa 9, porque o teste precisa do tópico. Na primeira execução ele cria `%APPDATA%\LolRemoto\config.json` com PIN e tópico aleatórios.
- O tópico e o token do ntfy não aparecem em `repr()`, logs nem mensagens de erro.

**Pendente com o Felipe:** instalar o app ntfy no Android, rodar `cd src; py -m lol_remoto --testar-notificacao`, assinar o tópico mostrado e conferir se a notificação chega.

### 7. Monitor e estado
Loop do lockfile → conexão → eventos → `Estado`. Gera avisos nas transições e notifica só com o modo ausente ligado. O modo desliga em `GameStart`.

### 8. Ações
Aceitar/recusar, marcar/confirmar campeão, reroll e troca do banco no ARAM. Fora de `ReadyCheck`/`ChampSelect` levanta `ForaDeFase` (409).

### 9. Autenticação
PIN + bloqueio por IP, sessões com cookie (só o SHA-256 salvo) e tokens de uso único para os botões da notificação.

### 10. API + SSE
Rotas JSON, `/api/eventos` (SSE), ícones dos campeões via LCU e as proteções de `Host`/`Origin`/JSON copiadas do desligador.

### 11. Interface web
Login, modo ausente, tela da seleção (bans, picks, quem está escolhendo, timer), busca e grade de campeões, ARAM e botão "Testar notificação".

### 12. Simulação
`--simular`: `LcuFalsa` percorre fila → ready check → seleção → carregamento, para testar o celular sem abrir o LoL.

### 13. Instalação
`instalar.ps1`/`desinstalar.ps1`: tarefa "LoL Remoto", firewall 8766 só para `100.64.0.0/10`, PIN, tópico do ntfy e o endereço para o celular.

### 14. Publicação
CI no GitHub Actions, README completo, CHANGELOG e `chore: versão 0.1.0`. Criar o repositório público `lol-remoto` e fazer push **só depois de confirmar com o Felipe**.

## Depois da v0.1.0 (ideias)
- Swiftplay e Arena.
- Runas e feitiços pelo celular.
- Favoritos/posição preferida na lista de campeões.
