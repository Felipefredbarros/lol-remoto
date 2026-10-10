# 0004 — TLS com a LCU verificado pelo certificado raiz da Riot

**Status:** aceita · **Data:** 2026-10-10

## Contexto
A LCU usa HTTPS com um certificado (`CN=rclient`, SAN `localhost` e `127.0.0.1`) emitido pela autoridade privada "LoL Game Engineering Certificate Authority". A Riot publica essa autoridade em `https://static.developer.riotgames.com/docs/lol/riotgames.pem`. Muitos projetos simplesmente desligam a verificação TLS.

O teste no cliente real (2026-10-10, Python 3.14) mostrou que a verificação com o `riotgames.pem` **falha** com `Missing Authority Key Identifier`. Desde o Python 3.13, `ssl.create_default_context()` liga `VERIFY_X509_STRICT`, e o certificado da Riot não tem essa extensão.

## Decisão
- Incluir o `riotgames.pem` no pacote (`plataforma/riotgames.pem`; SHA-256 `CA:8C:9D:32:...:4A:50:4E:A3`, válido até 2043).
- Contexto TLS: `create_default_context(cafile=riotgames.pem)`, **com** `check_hostname` (o SAN tem `127.0.0.1`) e **sem** a flag `VERIFY_X509_STRICT`.
- Nunca usar `CERT_NONE`.

## Consequências
- Só a LCU de verdade é aceita: outro processo que ocupasse a porta com outro certificado seria recusado, e a senha do lockfile não vazaria para ele.
- Tirar `VERIFY_X509_STRICT` só relaxa checagens de formato (como a falta do Authority Key Identifier). A cadeia, a validade e o nome continuam verificados.
- Se a Riot trocar a autoridade, a conexão falha com um erro claro no log, e o `.pem` precisa ser atualizado.
