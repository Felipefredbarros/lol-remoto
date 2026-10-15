# Segurança

## Como avisar uma falha

**Não abra uma issue pública.** Use o relato privado do GitHub: aba **Security** → **Report a vulnerability** ([link direto](https://github.com/Felipefredbarros/lol-remoto/security/advisories/new)). Só o mantenedor vê o relato.

Ajuda incluir: o que dá para fazer, os passos para reproduzir e a versão (ou commit). Projeto pessoal, sem prazo garantido, mas a ideia é responder em poucos dias e corrigir com prioridade o que permitir agir no cliente do LoL ou no PC sem o PIN.

## Versões

Só a versão mais recente (branch `main`) recebe correções.

## O que conta como falha

- Agir no cliente do LoL (aceitar, banir, escolher, runas, feitiços) **sem sessão válida**, ou fora da partida encontrada e da seleção de campeões ([ADR 0002](docs/decisoes/0002-lcu-api-e-nada-dentro-da-partida.md)).
- Contornar o PIN, o bloqueio por tentativas, a sessão do cookie ou os tokens de uso único das notificações.
- CSRF, DNS rebinding ou outra forma de uma página aberta no navegador falar com o servidor.
- Vazamento do PIN, de tokens, do tópico do ntfy ou da senha do lockfile (em arquivo, log ou resposta).
- Ler arquivos fora da pasta `web/` ou pedir à LCU caminhos que não sejam os do app.

## O que não conta

- Ataques que exigem acesso à sua conta do Tailscale ou ao PC já desbloqueado: o modelo de ameaça parte desses dois estarem seguros (ver o README).
- Falta do atributo `Secure` no cookie: o servidor é HTTP de propósito, e o transporte é criptografado pelo WireGuard do Tailscale ([ADR 0006](docs/decisoes/0006-sessao-com-cookie.md)).
- Mudanças da Riot na API local do cliente (LCU), que não é oficial.

As decisões de segurança estão em [docs/decisoes/](docs/decisoes/).
