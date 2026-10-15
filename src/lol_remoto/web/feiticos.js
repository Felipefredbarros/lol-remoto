// Feitiços (D e F), separados das runas: mostra os atuais e troca pela grade do modo.

import { chamar } from "./api.js";
import { criar, el, icone, mensagem } from "./util.js";

const SLOTS = ["d", "f"];
const ICONES = "/api/feiticos/";
let agir = null;
let lista = null; // os feitiços do modo, carregados uma vez por seleção
let slotAberto = null;
let desenhados = "";

export function iniciar(funcaoAgir) {
  agir = funcaoAgir;
  for (const slot of SLOTS) el("feitico-" + slot).addEventListener("click", () => abrir(slot));
}

// Chamado a cada atualização com os seus feitiços ({d, f}), ou null fora da seleção.
export function preparar(feiticos) {
  el("feiticos").hidden = !feiticos;
  if (!feiticos) {
    lista = null;
    desenhados = "";
    fechar();
    return;
  }
  const chave = SLOTS.map((s) => (feiticos[s] ? feiticos[s].id : 0)).join("/");
  if (chave === desenhados) return; // evita recarregar os ícones a cada atualização
  desenhados = chave;
  for (const slot of SLOTS) {
    const feitico = feiticos[slot];
    el("feitico-" + slot).replaceChildren(
      criar("span", "tecla", slot.toUpperCase()),
      icone(feitico, "pequeno", ICONES),
      criar("span", "nome", feitico ? feitico.nome : "Nenhum"),
    );
  }
}

async function abrir(slot) {
  if (slotAberto === slot) {
    fechar();
    return;
  }
  slotAberto = slot;
  for (const s of SLOTS) el("feitico-" + s).setAttribute("aria-pressed", String(s === slot));
  try {
    lista = lista || (await chamar("/api/feiticos")).disponiveis;
  } catch (erro) {
    mensagem(erro.message, "erro");
    fechar();
    return;
  }
  if (slotAberto !== slot) return; // fechou ou trocou de slot enquanto a lista chegava
  const grade = el("grade-feiticos");
  grade.hidden = false;
  grade.replaceChildren(...lista.map((feitico) => {
    const botao = criar("button", "campeao");
    botao.type = "button";
    botao.append(icone(feitico, null, ICONES), criar("span", null, feitico.nome));
    botao.addEventListener("click", () => escolher(slot, feitico));
    return botao;
  }));
}

function escolher(slot, feitico) {
  fechar();
  agir("/api/feiticos", { slot, feitico: feitico.id },
    feitico.nome + " no " + slot.toUpperCase());
}

function fechar() {
  slotAberto = null;
  for (const s of SLOTS) el("feitico-" + s).setAttribute("aria-pressed", "false");
  el("grade-feiticos").hidden = true;
  el("grade-feiticos").replaceChildren();
}
