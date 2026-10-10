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
