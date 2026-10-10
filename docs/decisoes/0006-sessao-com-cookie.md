# 0006 — Login por PIN que gera um cookie de sessão

**Status:** aceita · **Data:** 2026-10-10

## Contexto
No desligador o PIN vai em cada POST, e cada conferência leva ~0,5 s (PBKDF2 de 600 mil iterações). Aqui as ações são várias e sob pressão de tempo (buscar, marcar, confirmar), e a leitura do estado é contínua (SSE). Um `EventSource` não manda corpo nem cabeçalhos próprios, só cookies.

## Decisão
- `POST /api/entrar {"pin": "..."}` confere o PIN, com o mesmo bloqueio por IP do desligador, e devolve `Set-Cookie: lolremoto_sessao=<token>; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000` (30 dias).
- O token tem 32 bytes de `secrets.token_urlsafe`. O servidor guarda só o **SHA-256** dele, com a validade, em `%APPDATA%\LolRemoto\sessoes.json`. A sessão sobrevive a reinícios do PC. Limite de 10 sessões; ao passar disso, a mais antiga cai.
- `POST /api/sair` apaga a sessão. `--trocar-pin` apaga todas.
- Todas as rotas de `/api/` exigem sessão, exceto `entrar` e as duas rotas do ready check, que aceitam o token de uso único ([ADR 0005](0005-ntfy-com-topico-secreto-e-tokens.md)).
- Sem o atributo `Secure`, porque o servidor é HTTP. O transporte é protegido pelo WireGuard do Tailscale.

## Consequências
- O PIN é digitado uma vez a cada 30 dias por aparelho e não fica no `localStorage`. O cookie `HttpOnly` não é lido por JavaScript.
- `SameSite=Strict`, junto com a checagem de `Origin` e a exigência de JSON, mantém a proteção contra CSRF.
- Cookies não são separados por porta: o navegador também manda `lolremoto_sessao` ao desligador (8765) no mesmo host. Isso é inofensivo, porque o desligador ignora o cookie. Por isso o nome tem prefixo.
- Se o arquivo de sessões vazar, os hashes não servem para entrar.
