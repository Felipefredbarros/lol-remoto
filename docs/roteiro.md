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
| 6 | Notificador ntfy + config | ✅ | `3f307b8` |
| 7 | Monitor, estado, notificações e modo ausente | ✅ | `531a64b`, ajustes `0e327f4` e `6b28178` |
| 8 | Ações: ready check, pick/ban, ARAM | ✅ (ban e ARAM a validar ao vivo) | `f409d53` |
| 9 | Autenticação: PIN, sessões (cookie) e tokens de uso único | ✅ | `ee43194` |
| 10 | API HTTP + SSE | ✅ | `90a4279`, ajuste `a58ecd5` |
| 10b | Runas recomendadas e feitiços | ✅ (runas validadas; feitiços a conferir) | `ffe9548` |
| 11 | Interface web do celular | ✅ (usada numa ranqueada) | `0b1ee5b` |
| 11b | Feitiços separados das runas e página em etapas | ✅ (falta ver no celular e numa fila) | `9a29159` e o seguinte |
| 12 | `--simular` com roteiro falso (fila → seleção → carregando) | ✅ | `aa7fcd8` |
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

### 7. Monitor e estado ✅
Loop do lockfile → conexão → eventos → `Estado`. Gera avisos nas transições e notifica só com o modo ausente ligado. O modo desliga em `GameStart`.
- `servicos/estado.py`, `monitor.py` e `notificacoes.py`, mais `dominio/ready_check.py`. O envio das notificações roda numa thread própria.
- Só avisa transições vistas com o cliente conectado: conectar no meio de uma seleção ou o cliente fechar não viram "dodge" nem "seleção cancelada".
- Ao ligar o modo ausente sai uma notificação de confirmação (prioridade baixa).
- `--ausente`: inicia com o modo ligado, para testar antes de a página existir.
- Conferido no cliente real: conecta, lê a fase, carrega 250 campeões e encerra limpo.

**Teste ao vivo (Felipe), depois do `--testar-notificacao` da etapa 6:**
```powershell
cd src; py -m lol_remoto --ausente
```
Entre na fila e confira se chegam: partida encontrada, sua vez de banir/escolher e "partida carregando". Os botões Aceitar/Recusar só chegam na etapa 9/10; por enquanto, aceite no PC.

### 7b. Ajustes com gravações reais ✅
O teste do Felipe numa personalizada e duas gravações (`tests/fixtures/gravacoes/`) mostraram:
- **Bug:** no planejamento o primeiro ban já vem "em andamento". O app avisava "Sua vez de banir" na entrada da seleção e não avisava de novo quando os bans começavam de verdade. Corrigido: o planejamento tem aviso próprio ("Seleção começou: declare sua intenção").
- **Aviso falso:** a personalizada passa por `ReadyCheck` em milissegundos. Agora "Partida encontrada!" exige dados de ready check (o monitor faz GET ao entrar na fase).
- **ARAM:** novo aviso com o campeão sorteado e o tamanho do banco, sem "sua vez".
- **Saída da fila:** novo aviso quando a partida encontrada some sem aceite ("Você saiu da fila").
- `tests/test_gravacoes_reais.py` reproduz as gravações pelo monitor e confere as notificações.

**Fila de verdade (normal alternada, fila 400), duas gravações:**
- Funcionou de ponta a ponta no celular: partida encontrada → seleção começou → sua vez de banir → sua vez de escolher → carregando.
- Na normal o planejamento dura 12 s, e os 10 bans ficam "em andamento" ao mesmo tempo (bans simultâneos).
- A partida encontrada manda um evento por segundo (`timer` de 0 a 10) e dura uns 10 s.
- Troca de ordem de pick gera um segundo "sua vez de escolher", correto pelos dados.
- A gravação feita logo após o cliente abrir **não recebeu os eventos do ready check**. Agora o app assina o canal geral `OnJsonApiEvent` e filtra pelo `uri` (ADR 0002). Validado ao vivo depois (etapa 10b).
- Dodge na finalização vira fixture real (`normal_alternada_dodge.jsonl`).

**ARAM (decidido com o Felipe):** no começo aparecem alguns campeões para escolher e, se ele não escolher, o cliente escolhe sozinho. Ele **não quer escolher pelo celular**: basta aceitar a partida, saber qual campeão pegou e ser avisado do carregamento, o que o app já faz. Sem aviso de "sua vez" no ARAM. A página do ARAM mostra só o campeão e o time.

**Pendente com o Felipe:** gravar uma **fila de verdade** (normal ou ranqueada), de preferência numa partida que ele já ia jogar. Ela confirma os dados de ready check, que a personalizada não tem.

### 8. Ações ✅
Aceitar/recusar, marcar/confirmar campeão, reroll e troca do banco no ARAM. Fora de `ReadyCheck`/`ChampSelect` levanta `ForaDeFase` (409).
- `servicos/acoes.py`. Há um teste para cada fase sem ação, conferindo que nada chega à LCU.
- No planejamento, "marcar" declara a intenção (PATCH no meu pick); "confirmar" é recusado.
- O campeão é validado contra `pickable`/`bannable-champion-ids` antes de ir ao cliente.
- Confirmar usa `PATCH .../actions/{id}` com `{"championId", "completed": true}`.

**A validar ao vivo (com o Felipe na fila):** aceitar, intenção no planejamento, marcar e confirmar ban/pick, reroll e banco no ARAM.

**Ranqueada solo/duo pelo celular (11/10/2026), gravada em `tests/fixtures/gravacoes/ranqueada_solo.jsonl`:**
- Funcionou: aceitar pela notificação, intenção no planejamento, confirmar o pick, runas e todos os avisos (iguais aos do teste da gravação).
- **Bug:** na hora do ban a grade de campeões ficou vazia e o ban passou em branco. A suspeita é que o cliente devolveu `bannable-champion-ids` vazio (ou 404). Agora, sem essa lista, o app oferece o catálogo menos os já banidos (na ranqueada dá para banir qualquer campeão) e registra um aviso no log. A página diz "Nenhum campeão disponível agora" em vez de uma grade vazia, e uma resposta atrasada da lista não sobrescreve mais a da ação atual.
- **Falta confirmar** numa próxima ranqueada: o ban pelo celular e, no log, se aparece "O cliente não informou os campeões baníveis" (isso confirma a causa).

### 9. Autenticação ✅
PIN + bloqueio por IP, sessões com cookie (só o SHA-256 salvo) e tokens de uso único para os botões da notificação.
- `servicos/autenticacao.py` (cópia do desligador), `sessoes.py`, `tokens.py` e `trocar_pin.py`.
- `--trocar-pin` apaga o `sessoes.json`: todos os aparelhos precisam entrar de novo.
- A notificação de partida encontrada tem os botões Aceitar/Recusar (um token, uma vez). Os tokens deixam de valer quando a fase sai de `ReadyCheck`. No `__main__` eles só entram na etapa 10, junto com a rota que os botões chamam.

### 10. API + SSE ✅
Rotas JSON, `/api/eventos` (SSE), ícones dos campeões via LCU e as proteções de `Host`/`Origin`/JSON copiadas do desligador.
- Tabela de rotas em `docs/arquitetura.md`. A composição saiu do `__main__` para o `app.py`.
- Os botões Aceitar/Recusar da notificação passam a funcionar: o `app.py` liga os tokens às notificações.
- Testes de ponta a ponta com servidor real (`tests/api_falsa.py`): login, cookie, proteções, trava de fase, tokens, SSE e ícones.
- Conferido com o app completo: login, estado, SSE e o servidor no IP do Tailscale.

### 10b. Runas recomendadas e feitiços ✅
Pedido do Felipe: escolher pelo celular uma das **3 páginas de runas recomendadas** do cliente, com os feitiços.
- Decisões: o app grava sempre numa página chamada **"LoL Remoto"** (cria se houver espaço; senão pergunta se pode sobrescrever a atual) e põe o **Flash sempre no D**.
- Só na seleção, depois de travar o campeão (ou recebê-lo, no ARAM). Vale também para o ARAM.
- Primeiro passo: explorar os endpoints com o cliente aberto, só leitura (`/lol-perks/v1/pages`, `/lol-perks/v1/recommended-pages/...`, `/lol-champ-select/v1/session/my-selection`). Depois: serviço, rotas, testes e ADR.
- Exploração feita: não há comando de "aplicar recomendação"; o app monta a página. O Felipe tinha as 3 páginas ocupadas e renomeou uma para "LoL Remoto".
- **Teste ao vivo autorizado:** `PUT` na página "LoL Remoto" com a 1ª recomendação da Ahri funcionou (mesmo id, válida, selecionada).
- Recomendações reais (Ahri meio e Soraka ARAM) salvas em `tests/fixtures/runas_recomendadas.json`. No ARAM os feitiços vieram com o Flash no F, e o app inverte.
- A assinatura do canal geral de eventos foi validada ao vivo (eventos de lobby chegaram).
- **Falta validar numa seleção:** os feitiços (`PATCH my-selection`). Ver [ADR 0009](decisoes/0009-runas-recomendadas-na-pagina-lol-remoto.md).

### 11. Interface web ✅
Login, modo ausente, tela da seleção (bans, picks, quem está escolhendo, timer), busca e grade de campeões, ARAM e botão "Testar notificação".
- `web/`: `index.html`, `estilo.css` (claro/escuro, como o desligador, com o dourado do LoL) e módulos JS pequenos: `app.js` (login, SSE, ações), `painel.js` (fase, partida encontrada, modo ausente), `selecao.js` (times, bans, timer, vez), `campeoes.js` (grade com busca, marcar/confirmar), `runas.js`, `api.js` e `util.js`.
- Partida encontrada: contagem e botões grandes Aceitar/Recusar (recusar pede confirmação).
- Seleção: a grade aparece na sua vez e no planejamento (para a intenção). No ARAM, só o seu campeão e o time.
- Runas: aparecem quando você tem campeão. Se não houver página "LoL Remoto", a página pergunta antes de sobrescrever a atual.
- Sem navegador nesta máquina para conferir o visual: `tests/test_web.py` confere IDs, importações, CSP, ausência de `innerHTML` e o contrato com `api/visao.py`. A sintaxe do JS foi conferida com esprima.
- A API passou a mandar `codigo` (nome do erro) junto com `erro`, para a página distinguir erros com o mesmo status.

### 11b. Feitiços separados e página em etapas ✅
Pedido do Felipe depois da ranqueada de 11/10: trocar os feitiços sem mexer nas runas e uma página que siga a ordem da partida.
- **Feitiços:** botões D e F com a grade dos feitiços do modo; escolher o da outra tecla troca os dois de lugar. Aplicar runas não muda mais os feitiços ([ADR 0010](decisoes/0010-feiticos-separados-das-runas.md)).
- **Etapas:** `api/passos.py` monta fila → partida → intenção → ban → pick → runas → carregando (sem bans, pula intenção e ban; no ARAM, campeão → runas). A página mostra a barra de etapas, a etapa atual, o histórico ("Intenção: Kai'Sa", "Ban: Yasuo") e a ordem dos picks dos dois times.
- Conferido com a ranqueada gravada: as etapas seguem intenção → ban → pick → runas. O cliente **zera a intenção** uns 20 s depois do seu pick; depois disso o histórico mostra só "Intenção" (sem dizer qual).
- Conferido com o `--simular` e um "celular falso" por HTTP: o ciclo inteiro, os feitiços do modo e a troca.
- Conferido no cliente real, só com GET: o formato de `summoner-spells.json` (`gameModes`, `iconPath`), agora a fixture `tests/fixtures/feiticos.json`.
- **Fotos no `--simular`:** a simulação lê as imagens do cliente de verdade, se estiver aberto (`plataforma/ativos_reais.py`, só `/lol-game-data/assets/`), e os ícones ficam em cache em disco (`%LOCALAPPDATA%\LolRemoto\icones`).
- **Falta:** o Felipe ver no celular (o visual não foi conferido em navegador) e usar numa fila de verdade.

### 12. Simulação ✅
`--simular`: um cliente do LoL simulado percorre fila → partida encontrada → seleção → carregamento, para testar o celular sem abrir o LoL.
- Ciclo: lobby (3 s) → fila (6 s) → partida encontrada (até 10 s; se você não aceitar, sai da fila) → planejamento (10 s) → bans simultâneos (20 s) → picks em 6 turnos (20 s cada) → finalização (8 s) → carregando → em partida (15 s) → fim de jogo → de novo. A cada 3 ciclos alguém dá dodge na finalização.
- Você é o meio (célula 2). Os outros 9 são bots que agem em 2 a 5 s. Se o tempo acabar, o cliente simulado trava o que estiver marcado (ou sorteia o pick).
- Reage à página: aceitar/recusar, intenção, marcar/confirmar, runas (página "LoL Remoto") e feitiços. Com o cliente aberto, as fotos vêm dele (ver 11b); senão, do cache em disco ou as iniciais.
- As notificações são reais (ntfy) quando o modo ausente está ligado, então dá para testar os botões Aceitar/Recusar no celular.
- `tests/test_simulacao.py` roda o ciclo acelerado (1 s = 20 ms) com um jogador automático. Testei também com o servidor completo e um "celular falso" por HTTP.
- Bug achado no teste manual e corrigido: marcar a intenção encerrava o planejamento na hora.
- Também nesta etapa: se o cliente apagar o ready check antes de mudar de fase, o monitor guarda a última resposta até a fase mudar. Assim o aviso "você saiu da fila" não se perde.

**Para o Felipe testar no celular (sem abrir o LoL):**
```powershell
cd C:\Users\felip\Documents\lol-remoto\src
py -m lol_remoto --simular
```
No celular (Tailscale ligado), abra `http://<IP do Tailscale do PC>:8766` (aparece no log como "Ouvindo em ...") e entre com o PIN. Ligue o modo ausente para receber as notificações com os botões. Para parar: `Ctrl+C`.

### 13. Instalação
`instalar.ps1`/`desinstalar.ps1`: tarefa "LoL Remoto", firewall 8766 só para `100.64.0.0/10`, PIN, tópico do ntfy e o endereço para o celular.

### 14. Publicação
CI no GitHub Actions, README completo, CHANGELOG e `chore: versão 0.1.0`. Criar o repositório público `lol-remoto` e fazer push **só depois de confirmar com o Felipe**.

## Depois da v0.1.0 (ideias)
- Swiftplay e Arena.
- Runas e feitiços pelo celular.
- Favoritos/posição preferida na lista de campeões.
