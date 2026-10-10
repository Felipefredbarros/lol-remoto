# 0007 — Server-Sent Events para a tela em tempo real

**Status:** aceita · **Data:** 2026-10-10

## Contexto
A seleção de campeões muda várias vezes por segundo nos momentos críticos, e o celular precisa ver bans, picks e o timer ao vivo. As opções eram polling, WebSocket no servidor (sem suporte na stdlib) ou SSE.

## Decisão
`GET /api/eventos` responde `text/event-stream` com o estado completo resumido (não o JSON bruto da LCU) a cada mudança, mais um comentário de heartbeat a cada 15 s.
- No máximo 4 conexões simultâneas: a mais antiga é encerrada.
- Exige sessão (cookie).
- O navegador reconecta sozinho (`EventSource`) e recebe o estado completo na reconexão.
- O timer é enviado como "segundos restantes no momento do envio", e a página conta localmente, como no desligador.

## Consequências
- Funciona com `ThreadingHTTPServer`: cada stream ocupa uma thread, o que é aceitável com o limite de 4.
- O timeout de 10 s vale só para ler o pedido. Durante o stream, as escritas do heartbeat detectam conexões mortas.
- Mandar o estado completo é mais simples que mandar diferenças, e o volume (poucos KB por mudança dentro do Tailscale) é irrelevante.
