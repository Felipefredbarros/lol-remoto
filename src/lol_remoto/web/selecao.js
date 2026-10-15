// Tela da seleção: a etapa atual em destaque (vez, timer, grade, runas e feitiços), a ordem
// dos picks e os bans. No ARAM, sem ordem de picks, mostra os times.

import * as campeoes from "./campeoes.js";
import * as etapas from "./etapas.js";
import * as feiticos from "./feiticos.js";
import * as ordem from "./ordem.js";
import * as runas from "./runas.js";
import { contar, criar, el, icone } from "./util.js";

const ETAPAS = {
  PLANNING: "Planejamento",
  BAN_PICK: "Bans e picks",
  FINALIZATION: "Finalização",
  GAME_STARTING: "Iniciando",
};
const AGINDO = { ban: "banindo", pick: "escolhendo" };

export function desenhar(estado) {
  const selecao = estado.selecao;
  const visivel = Boolean(selecao) && estado.fase === "ChampSelect";
  el("selecao").hidden = !visivel;
  if (!visivel) {
    contar(el("timer"), null);
    campeoes.esquecer();
    runas.preparar(null);
    feiticos.preparar(null);
    return;
  }
  const eu = selecao.aliados.find((j) => j.eu) || null;
  const passo = etapas.atual(estado);
  const nomeDoPasso = (estado.passos || []).find((p) => p.id === passo);
  el("etapa").textContent = [selecao.aram ? "ARAM" : ETAPAS[selecao.etapa],
    nomeDoPasso && nomeDoPasso.nome].filter(Boolean).join(" · ") || "Seleção";
  contar(el("timer"), selecao.segundos_restantes);
  el("vez").textContent = textoDaVez(selecao, eu);

  desenharAcao(selecao, eu);
  // Runas e feitiços são a etapa depois do seu pick (no ARAM, logo de cara).
  const naEtapaDeRunas = passo === "runas" && Boolean(eu);
  runas.preparar(naEtapaDeRunas ? eu.campeao : null);
  feiticos.preparar(naEtapaDeRunas ? eu.feiticos : null);

  const temOrdem = ordem.desenhar(selecao);
  el("cartao-bans").hidden = selecao.aram;
  desenharBans(el("bans-aliados"), selecao.bans.aliados);
  desenharBans(el("bans-inimigos"), selecao.bans.inimigos);
  el("cartao-aliados").hidden = temOrdem;
  el("cartao-inimigos").hidden = temOrdem || selecao.inimigos.length === 0;
  if (!temOrdem) {
    desenharTime(el("aliados"), selecao.aliados);
    desenharTime(el("inimigos"), selecao.inimigos);
  }
}

function nomeCurto(jogador) {
  return jogador.nome || jogador.posicao || "um jogador";
}

function textoDaVez(selecao, eu) {
  if (selecao.aram) {
    return eu && eu.campeao ? "Você está de " + eu.campeao.nome : "Sorteando os campeões…";
  }
  if (selecao.planejamento) return "Declare sua intenção de pick";
  if (selecao.minha_vez) {
    return selecao.minha_vez.tipo === "ban" ? "Sua vez de banir!" : "Sua vez de escolher!";
  }
  if (eu && eu.confirmado && eu.campeao) return "Você está de " + eu.campeao.nome;
  const agindo = selecao.aliados.concat(selecao.inimigos).filter((j) => j.agindo);
  return agindo.length ? "Aguardando " + agindo.map(nomeCurto).join(", ") : "";
}

// A grade aparece na sua vez e no planejamento (para declarar a intenção). Nunca no ARAM.
function desenharAcao(selecao, eu) {
  const vez = selecao.minha_vez;
  const ativo = !selecao.aram && (Boolean(vez) || (selecao.planejamento && Boolean(eu)));
  el("acao").hidden = !ativo;
  if (!ativo) {
    campeoes.esquecer();
    return;
  }
  const marcado = vez ? vez.campeao : (eu.intencao ? eu.intencao.id : 0);
  el("dica-acao").textContent = vez
    ? "Toque num campeão para marcar e depois confirme."
    : "Toque num campeão para declarar a intenção (seu time vê).";
  campeoes.preparar(vez ? vez.tipo : "pick", vez ? "acao-" + vez.id : "planejamento",
    marcado || null, Boolean(vez));
}

function desenharBans(alvo, bans) {
  alvo.replaceChildren(...bans.map((campeao) => icone(campeao, "pequeno")));
}

function desenharTime(alvo, jogadores) {
  alvo.replaceChildren(...jogadores.map((jogador) => {
    const item = criar("li");
    if (jogador.eu) item.classList.add("eu");
    if (jogador.agindo) item.classList.add("agindo");

    if (jogador.campeao) item.append(icone(jogador.campeao));
    else if (jogador.intencao) item.append(icone(jogador.intencao, "intencao"));
    else item.append(icone(null));

    const nome = criar("span", "nome", jogador.eu ? "Você" : nomeCurto(jogador));
    const detalhes = [];
    if (jogador.posicao && (jogador.nome || jogador.eu)) detalhes.push(jogador.posicao);
    if (jogador.campeao) detalhes.push(jogador.campeao.nome);
    else if (jogador.intencao) detalhes.push("intenção: " + jogador.intencao.nome);
    if (detalhes.length) nome.append(criar("span", "detalhe", detalhes.join(" · ")));
    item.append(nome);

    if (jogador.agindo) item.append(criar("span", "selo vez", AGINDO[jogador.agindo]));
    else if (jogador.confirmado) item.append(criar("span", "selo ok", "pronto"));
    return item;
  }));
}
