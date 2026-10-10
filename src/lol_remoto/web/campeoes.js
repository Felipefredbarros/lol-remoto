// Grade de campeões com busca: marcar (hover/intenção) e confirmar ban/pick.

import { chamar } from "./api.js";
import { criar, el, icone, mensagem, normalizar } from "./util.js";

let agir = null;
let lista = [];
let chaveAtual = null; // muda a cada nova ação (ban, pick, planejamento)
let tipoAtual = "pick";
let podeConfirmar = false;
let selecionado = null;

export function iniciar(funcaoAgir) {
  agir = funcaoAgir;
  el("busca").addEventListener("input", desenharGrade);
  el("confirmar").addEventListener("click", () => {
    if (!selecionado) return;
    const verbo = tipoAtual === "ban" ? "Banido" : "Escolhido";
    agir("/api/selecao/confirmar", { campeao: selecionado.id }, verbo + ": " + selecionado.nome);
  });
}

// Chamado a cada atualização da seleção. Só recarrega a lista quando a ação muda.
export async function preparar(tipo, chave, marcado, confirmavel) {
  podeConfirmar = confirmavel;
  if (chave !== chaveAtual) {
    chaveAtual = chave;
    tipoAtual = tipo;
    selecionado = null;
    el("busca").value = "";
    lista = [];
    desenharGrade();
    try {
      lista = (await chamar("/api/campeoes?tipo=" + tipo)).campeoes;
    } catch (erro) {
      mensagem(erro.message, "erro");
    }
  }
  if (marcado && (!selecionado || selecionado.id !== marcado)) {
    selecionado = lista.find((c) => c.id === marcado) || selecionado;
  }
  desenharGrade();
}

export function esquecer() {
  chaveAtual = null;
  selecionado = null;
}

function desenharGrade() {
  const filtro = normalizar(el("busca").value);
  const grade = el("grade-campeoes");
  const visiveis = lista.filter((c) => normalizar(c.nome).includes(filtro));
  grade.replaceChildren(...visiveis.map((campeao) => {
    const botao = criar("button", "campeao");
    botao.type = "button";
    botao.setAttribute("aria-pressed", String(Boolean(selecionado) && selecionado.id === campeao.id));
    botao.append(icone(campeao), criar("span", null, campeao.nome));
    botao.addEventListener("click", () => marcar(campeao));
    return botao;
  }));
  const confirmar = el("confirmar");
  confirmar.hidden = !podeConfirmar;
  confirmar.disabled = !selecionado;
  const verbo = tipoAtual === "ban" ? "Banir" : "Escolher";
  confirmar.textContent = selecionado ? verbo + " " + selecionado.nome : verbo;
}

function marcar(campeao) {
  selecionado = campeao;
  desenharGrade();
  agir("/api/selecao/marcar", { campeao: campeao.id });
}
