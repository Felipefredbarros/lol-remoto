// Barra de etapas da partida e o histórico do que já foi feito (vem pronto em estado.passos).

import { criar, el } from "./util.js";

const MARCAS = { feito: "✓", atual: "●", pendente: "○" };

// A etapa atual ("fila", "partida", "intencao", "ban", "pick", "runas"...), ou null.
export function atual(estado) {
  const passo = (estado.passos || []).find((p) => p.estado === "atual");
  return passo ? passo.id : null;
}

export function desenhar(estado) {
  const passos = estado.passos || [];
  const barra = el("etapas");
  barra.hidden = passos.length === 0;
  barra.replaceChildren(...passos.map((passo) => {
    const item = criar("li", "etapa " + passo.estado);
    if (passo.estado === "atual") item.setAttribute("aria-current", "step");
    item.append(criar("span", "marca", MARCAS[passo.estado]), criar("span", null, passo.nome));
    return item;
  }));

  const feitos = passos.filter((p) => p.estado === "feito");
  el("cartao-historico").hidden = feitos.length === 0;
  el("historico").replaceChildren(...feitos.map((passo) => {
    const item = criar("li");
    const texto = passo.resumo ? passo.nome + ": " + passo.resumo : passo.nome;
    item.append(criar("span", "marca", "✓"), criar("span", null, texto));
    return item;
  }));
}
