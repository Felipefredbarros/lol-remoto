# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado
- Estrutura inicial do projeto, CLAUDE.md, documento de arquitetura e ADRs 0001 a 0008.
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

### Corrigido
- "Sua vez de banir" saía no início do planejamento, e não quando os bans começavam.
- "Partida encontrada!" saía em partidas personalizadas, que não têm nada para aceitar.
