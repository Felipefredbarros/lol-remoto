// Ordem dos picks dos dois times, com quem está escolhendo agora e você em destaque.

import { criar, el, icone } from "./util.js";

const SELOS = { agindo: ["vez", "escolhendo"], feito: ["ok", "pronto"] };

// Mostra a lista e devolve true; sem picks (ARAM), esconde e devolve false.
export function desenhar(selecao) {
  const ordem = selecao.ordem_picks || [];
  el("cartao-ordem").hidden = ordem.length === 0;
  el("ordem-picks").replaceChildren(...ordem.map(item));
  return ordem.length > 0;
}

function item(pick) {
  const linha = criar("li", pick.aliado ? "aliado" : "inimigo");
  if (pick.eu) linha.classList.add("eu");
  if (pick.estado === "agindo") linha.classList.add("agindo");

  linha.append(criar("span", "numero", String(pick.ordem)));
  if (pick.campeao) linha.append(icone(pick.campeao));
  else if (pick.intencao) linha.append(icone(pick.intencao, "intencao"));
  else linha.append(icone(null));

  const quem = pick.eu ? "Você" : (pick.nome || pick.posicao || (pick.aliado ? "Aliado" : "Inimigo"));
  const nome = criar("span", "nome", quem);
  const detalhes = [pick.aliado ? "seu time" : "time inimigo"];
  if (pick.posicao && (pick.nome || pick.eu)) detalhes.push(pick.posicao);
  if (pick.campeao) detalhes.push(pick.campeao.nome);
  else if (pick.intencao) detalhes.push("intenção: " + pick.intencao.nome);
  nome.append(criar("span", "detalhe", detalhes.join(" · ")));
  linha.append(nome);

  const selo = SELOS[pick.estado];
  if (selo) linha.append(criar("span", "selo " + selo[0], selo[1]));
  return linha;
}
