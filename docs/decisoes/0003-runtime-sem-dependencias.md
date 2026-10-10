# 0003 — Runtime só com a biblioteca padrão, inclusive o WebSocket

**Status:** aceita · **Data:** 2026-10-10

## Contexto
Como no desligador, o servidor inicia sozinho no logon via `pythonw.exe`, e um `pip install` quebrado não pode impedir a inicialização. Mas a biblioteca padrão do Python não tem cliente WebSocket, e os eventos da LCU chegam por WebSocket.

Opções consideradas:
1. o pacote `websocket-client`;
2. polling HTTPS a cada segundo;
3. um cliente WebSocket próprio.

## Decisão
Implementar um **cliente WebSocket mínimo** (`plataforma/websocket.py`, RFC 6455) sobre `socket` + `ssl`:
- handshake com `Sec-WebSocket-Key`/`Accept` e `Sec-WebSocket-Protocol: wamp`;
- quadros de texto com máscara do cliente;
- tamanhos de 7, 16 e 64 bits;
- fragmentação, ping/pong e close.

O resto continua igual ao desligador: `http.server`, `urllib`, `json`, `hmac`, `logging`. Ferramentas de desenvolvimento (pytest, ruff) ficam em `[project.optional-dependencies].dev`.

## Consequências
- Basta ter o Python instalado. Sem dependência para atualizar e com menos superfície de ataque.
- São ~150 linhas a mais para manter. Elas são testadas contra um servidor WebSocket falso local: quadros grandes (a sessão da seleção passa de 20 KB), fragmentados, ping e close.
- O cliente só precisa falar com a LCU. Não suporta extensões (compressão `permessage-deflate`) nem é um cliente de uso geral.
- Polling ficaria mais simples, mas teria até 1 s de atraso por evento e faria ~3 requisições por segundo, o tempo todo.
