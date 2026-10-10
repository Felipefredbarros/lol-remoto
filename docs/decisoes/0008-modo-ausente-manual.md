# 0008 — Modo ausente ligado manualmente

**Status:** aceita · **Data:** 2026-10-10

## Contexto
Notificar em toda fila incomoda quem está no PC. Detectar ausência por inatividade (sem mouse/teclado há N segundos) falha justamente no caso comum: a fila pode estourar antes do tempo de inatividade passar. Também se considerou um atalho de teclado no PC, mas o usuário não quis.

## Decisão
- Um **modo ausente**, ligado e desligado por um botão na página (celular ou `localhost`), controla se as notificações saem. A página e as ações funcionam sempre, com o modo ligado ou não.
- O modo **desliga sozinho** ao entrar em `GameStart`, logo depois do aviso "Partida carregando, volta pro PC!".
- O estado do modo fica em memória e começa desligado quando o servidor inicia. A opção `--ausente` faz o servidor já iniciar com ele ligado; ela existe para testes e para usar o app antes de a página existir.
- Ao ligar o modo, sai uma notificação de confirmação (prioridade baixa). Ela também serve para conferir se o ntfy está chegando antes de você sair do PC.

## Consequências
- Você decide quando quer ser avisado (banheiro, cama...) e nunca recebe push jogando.
- Se esquecer de ligar, não há notificação. A página continua mostrando tudo ao vivo.
- Se o PC reiniciar, o modo volta desligado. É o lado seguro.
