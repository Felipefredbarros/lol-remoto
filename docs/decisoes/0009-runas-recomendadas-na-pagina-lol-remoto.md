# 0009 — Runas recomendadas do cliente, gravadas na página "LoL Remoto"

**Status:** aceita; a parte dos feitiços foi substituída pela [ADR 0010](0010-feiticos-separados-das-runas.md) · **Data:** 2026-10-10

## Contexto
O Felipe quer escolher as runas pelo celular durante a seleção. O cliente já mostra 3 páginas **recomendadas** para o campeão e a posição (`/lol-perks/v1/recommended-pages/champion/{id}/position/{pos}/map/{mapa}`), com os feitiços recomendados. Não existe na LCU um comando de "aplicar recomendação": o clique no cliente monta uma página com esses dados.

Cada conta tem poucas páginas editáveis. No teste, as 3 estavam ocupadas (`canAddCustomPage: false`). Gravar runas numa página apaga o que havia nela.

## Decisão
- Usar **só as recomendações do próprio cliente** (nada de sites externos).
- Gravar sempre numa página chamada **"LoL Remoto"** (comparação sem maiúsculas e sem espaços nas pontas), com `PUT /lol-perks/v1/pages/{id}` e `current: true`. O Felipe renomeou uma página dele para isso.
- Sem essa página: criar uma (`POST /lol-perks/v1/pages`) se houver espaço. Senão, recusar (409) e só **sobrescrever a página atual com confirmação explícita** (`sobrescrever_atual: true`), mantendo o nome dela.
- Feitiços pela seleção (`PATCH /lol-champ-select/v1/session/my-selection`), com o **Flash sempre no D**: a recomendação do ARAM veio como `[Clareza, Flash]`.
- Só na fase `ChampSelect` e depois de haver campeão (marcado ou travado); no ARAM, usa o mapa 12 e a posição `NONE`.

## Consequências
- As runas ficam iguais às que o cliente recomenda, inclusive no ARAM.
- As outras páginas do Felipe nunca são tocadas sem ele confirmar.
- Conferido no cliente real (10/2026): o `PUT` mantém o id e o nome, deixa a página válida e selecionada. Os feitiços ainda precisam ser validados numa seleção.
