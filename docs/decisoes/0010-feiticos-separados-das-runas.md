# 0010 — Feitiços separados das runas

**Status:** aceita · **Data:** 2026-10-15 · Substitui a parte dos feitiços da [ADR 0009](0009-runas-recomendadas-na-pagina-lol-remoto.md)

## Contexto
Na ADR 0009, aplicar uma runa recomendada também punha os feitiços sugeridos pelo cliente (com o Flash no D). Depois da ranqueada de 11/10/2026, o Felipe pediu para trocar os feitiços **à parte**: muitas vezes ele quer a runa sugerida, mas outro feitiço (ex.: Teleporte em vez de Incendiar), e às vezes quer só trocar o feitiço.

## Decisão
- **Runas só mudam runas.** `POST /api/runas/aplicar` não chama mais `PATCH my-selection`. O cartão da runa mostra os feitiços sugeridos só como dica.
- **Feitiços pelos botões D e F.** `POST /api/feiticos {slot, feitico}` faz `PATCH /lol-champ-select/v1/session/my-selection` com `{spell1Id, spell2Id}` (D = `spell1Id`). Escolher para uma tecla o feitiço que está na outra **troca os dois de lugar**, como no cliente.
- **Só os feitiços do modo.** A lista vem de `/lol-game-data/assets/v1/summoner-spells.json`, filtrada pelo campo `gameModes` (`CLASSIC` no Summoner's Rift, `ARAM` no ARAM). Se o campo faltar, vale uma lista fixa por modo (`dominio/feiticos.py`). O serviço recusa feitiços fora do modo antes de chamar o cliente.
- **Lista carregada ao conectar**, como o catálogo de campeões (`Monitor` → `Estado.feiticos`), para a página receber os nomes dos seus feitiços no estado sem uma chamada extra à LCU.
- **Ícones pelo PC**, como os dos campeões: `GET /api/feiticos/<id>.png`. O caminho na LCU vem da lista do cliente (`iconPath`), nunca do pedido, e só vale dentro de `/lol-game-data/assets/`.
- A trava de fase continua: só na `ChampSelect` (ADR 0002). Dentro da partida nada muda.

## Consequências
- Dá para usar a runa sugerida com outros feitiços, e trocar os feitiços sem mexer nas runas.
- O Flash não vai mais para o D sozinho; o Felipe escolhe. `flash_no_d` continua só para mostrar a sugestão.
- Conferido no cliente real (15/10/2026, só GET): `summoner-spells.json` tem `gameModes` e `iconPath`, e os ícones vêm como PNG. A lista real (39 feitiços, de vários modos) está em `tests/fixtures/feiticos.json`; filtrada, dá 9 feitiços no Summoner's Rift e 9 no ARAM.
