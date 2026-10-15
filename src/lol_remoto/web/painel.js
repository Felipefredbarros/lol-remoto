// Parte de cima da página: fase do cliente, partida encontrada e modo ausente.
// O cartão da fase some quando a etapa atual tem cartão próprio (partida, seleção).

import { contar, el } from "./util.js";

const RESPOSTAS = { Accepted: "Você aceitou.", Declined: "Você recusou." };
let estado = null;

export function iniciar(agir) {
  el("aceitar").addEventListener("click", () => {
    agir("/api/ready-check/aceitar", {}, "Partida aceita!");
  });
  el("recusar").addEventListener("click", () => {
    if (confirm("Recusar a partida? Você sai da fila.")) {
      agir("/api/ready-check/recusar", {}, "Partida recusada.");
    }
  });
  el("ausente").addEventListener("click", () => {
    if (!estado) return;
    const ligar = !estado.ausente;
    agir("/api/ausente", { ativo: ligar },
      ligar ? "Modo ausente ligado: as notificações vão chegar." : "Modo ausente desligado.");
  });
  el("testar").addEventListener("click", () => {
    agir("/api/testar-notificacao", {}, "Notificação enviada. Confira o celular.");
  });
}

export function desenhar(novo) {
  estado = novo;
  el("fase").textContent = novo.fase_descricao;

  const ausente = el("ausente");
  ausente.setAttribute("aria-pressed", String(novo.ausente));
  ausente.textContent = "Modo ausente: " + (novo.ausente ? "ligado" : "desligado");

  const partida = novo.ready_check;
  const visivel = Boolean(partida) && novo.fase === "ReadyCheck";
  el("partida").hidden = !visivel;
  el("cartao-status").hidden = visivel || (Boolean(novo.selecao) && novo.fase === "ChampSelect");
  if (!visivel) {
    contar(el("partida-contagem"), null);
    return;
  }
  contar(el("partida-contagem"), partida.segundos_restantes);
  const respondeu = partida.resposta !== "None";
  el("partida-resposta").textContent = RESPOSTAS[partida.resposta] || "";
  el("aceitar").disabled = respondeu;
  el("recusar").disabled = respondeu;
}

export function conexao(texto) {
  const alvo = el("conexao");
  alvo.textContent = texto || "";
  alvo.hidden = !texto;
}
