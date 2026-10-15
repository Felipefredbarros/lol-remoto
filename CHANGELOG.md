# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado
- Estrutura inicial do projeto, CLAUDE.md, documento de arquitetura e ADRs.
- Regras do domínio: fases do cliente (com a trava "nada dentro da partida"), leitura da sessão da seleção de campeões, avisos por transição e busca de campeões sem acento.
- Cliente WebSocket próprio (RFC 6455) sobre a biblioteca padrão, para os eventos do cliente do LoL.
- Cliente da LCU: leitura do lockfile, HTTPS verificado com o certificado da Riot e eventos por WebSocket.
- Comandos `--gravar` (grava eventos reais da LCU, só escutando) e `--anonimizar` (prepara gravações para virar fixtures).
- Notificações pelo ntfy, com prioridade, link e botões de ação; comando `--testar-notificacao`.
- Configuração em `%APPDATA%\LolRemoto\config.json`, criada com PIN e tópico do ntfy aleatórios.
- Monitor do cliente do LoL: espera o cliente abrir, acompanha fila, partida encontrada e seleção de campeões, e reconecta quando o cliente reinicia.
- Notificações de partida encontrada, recusa, sua vez de banir/escolher, dodge, seleção cancelada e partida carregando, só com o modo ausente ligado. Ele desliga sozinho quando a partida carrega.
- Opção `--ausente` para iniciar com o modo ausente ligado.
- Avisos de planejamento (declare a intenção), campeão do ARAM e saída da fila sem aceite.
- Gravações reais anonimizadas como fixtures, reproduzidas pelo monitor nos testes.
- Ações no cliente: aceitar/recusar a partida, declarar intenção, marcar e confirmar ban/pick, reroll e troca do banco no ARAM, sempre conferindo a fase.
- Sessões de login (só o hash do token fica salvo), tokens de uso único para os botões Aceitar/Recusar da notificação e comando `--trocar-pin`, que encerra todas as sessões.
- API HTTP com login por PIN (cookie de sessão), estado e eventos em tempo real (SSE), lista e ícones de campeões, modo ausente e ações no cliente. Os botões Aceitar/Recusar da notificação funcionam.
- Runas recomendadas pelo próprio cliente, aplicadas pelo celular na página "LoL Remoto", com os feitiços recomendados e o Flash sempre no D.
- Página do celular: login, modo ausente, partida encontrada com Aceitar/Recusar, seleção de campeões ao vivo (bans, times, timer, sua vez), grade de campeões com busca e runas recomendadas.
- Opção `--simular`: cliente do LoL simulado com bots (fila, partida encontrada, seleção, dodge) para testar o celular sem abrir o jogo.
- Feitiços pelo celular, separados das runas: botões D e F com a grade dos feitiços do modo. Escolher o feitiço da outra tecla troca os dois de lugar.

- Página em etapas: barra com fila → partida → intenção → ban → pick → runas → carregando, a etapa atual em destaque, o histórico do que já foi feito ("Ban: Yasuo") e a ordem dos picks dos dois times.

- Fotos dos campeões e feitiços no `--simular`, lidas do cliente de verdade quando ele está aberto (só imagens, só GET).
- Cache dos ícones em disco (`%LOCALAPPDATA%\LolRemoto\icones`): as fotos carregam rápido depois de reiniciar e aparecem na simulação mesmo com o cliente fechado.

### Alterado
- Aplicar runas não muda mais os feitiços; a página só mostra os feitiços sugeridos.
- Runas e feitiços aparecem na etapa depois do seu pick (no ARAM, logo no começo). Os times só aparecem quando não há ordem de picks (ARAM).

### Corrigido
- "Sua vez de banir" saía no início do planejamento, e não quando os bans começavam.
- "Partida encontrada!" saía em partidas personalizadas, que não têm nada para aceitar.
- Eventos do cliente que não chegavam quando o app conectava logo depois de o cliente abrir: agora o app assina o canal geral de eventos e filtra os que usa.
- O aviso "você saiu da fila" se perdia se o cliente apagasse o ready check antes de mudar de fase.
- A grade de campeões não oferece mais campeão banido nem já escolhido, mesmo que a lista do cliente traga. No `--simular` dava para escolher um banido.
- Grade de campeões vazia na hora do ban numa ranqueada: sem a lista de baníveis do cliente, o app oferece todos os campeões, menos os já banidos. A página avisa quando não há campeão para mostrar.
