# 0005 — Notificações pelo ntfy.sh, com tópico secreto e tokens de uso único

**Status:** aceita · **Data:** 2026-10-10

## Contexto
O ready check dura cerca de 10 s, então o aviso precisa chegar como push e, de preferência, permitir aceitar sem abrir a página. O celular é Android. Uma página web só consegue push (Web Push) em HTTPS, e o servidor roda em HTTP dentro do Tailscale.

O [ntfy](https://ntfy.sh) entrega push com prioridade e tem **botões de ação `http`**: o próprio app do ntfy faz uma requisição HTTP a partir do celular. No ntfy.sh público, porém, qualquer pessoa que saiba o nome de um tópico pode ler as mensagens dele.

## Decisão
- Publicar em `https://ntfy.sh` (configurável), num **tópico aleatório** gerado na instalação (`lolremoto-` + 24 caracteres de `secrets.token_urlsafe`). O tópico fica só no `config.json`.
- O ready check gera dois botões `http`. Cada um faz `POST http://<ip tailscale>:8766/api/ready-check/{aceitar|recusar}` com um **token de uso único**:
  - 32 bytes aleatórios;
  - válido por 15 s e só enquanto a fase for `ReadyCheck`;
  - consumido no primeiro uso;
  - serve só para essas duas rotas.
- As mensagens não levam PIN nem token de sessão. O conteúdo se limita a fase, campeões e tempo restante.
- Prioridades: partida encontrada e sua vez = 5 (máxima); carregando = 5; dodge/recusa = 4.

## Consequências
- Mesmo que alguém leia o tópico, o token é inútil depois de 15 s ou de um uso. E a URL só é alcançável de dentro do Tailscale.
- Depende do ntfy.sh estar no ar (latência típica de 1 a 2 s). Dá para apontar para um servidor próprio no `config.json` sem mudar código.
- O usuário precisa instalar o app ntfy e assinar o tópico. O instalador mostra o nome dele.
- A URL dos botões usa o IP do Tailscale, que funciona mesmo sem o MagicDNS resolver nomes curtos no celular.
