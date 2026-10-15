// Runas recomendadas pelo cliente: mostra as 3 e aplica a escolhida (só as runas).

import { chamar, ErroApi } from "./api.js";
import { criar, el, mensagem } from "./util.js";

let campeaoAtual = null;
let aoSairDoLogin = null;

export function iniciar(pedirLogin) {
  aoSairDoLogin = pedirLogin;
  el("ver-runas").addEventListener("click", carregar);
}

// Chamado a cada atualização: mostra o cartão quando você já tem campeão.
export function preparar(campeao) {
  const id = campeao ? campeao.id : null;
  el("runas").hidden = !id;
  if (id !== campeaoAtual) {
    campeaoAtual = id;
    el("lista-runas").replaceChildren();
    el("ver-runas").hidden = false;
  }
}

function tratarErro(erro) {
  if (erro instanceof ErroApi && erro.status === 401) aoSairDoLogin();
  else mensagem(erro.message, "erro");
}

async function carregar() {
  try {
    const dados = await chamar("/api/runas");
    el("ver-runas").hidden = true;
    el("lista-runas").replaceChildren(...dados.recomendacoes.map(cartao));
    if (dados.recomendacoes.length === 0) mensagem("O cliente não tem recomendações agora.", "erro");
  } catch (erro) {
    tratarErro(erro);
  }
}

function cartao(recomendacao) {
  const botao = criar("button", "runa");
  botao.type = "button";
  botao.setAttribute("aria-pressed", "false");
  botao.append(
    criar("strong", null, recomendacao.principal),
    criar("span", null, [recomendacao.descricao, recomendacao.estilos].filter(Boolean).join(" · ")),
    criar("span", null, "Feitiços sugeridos: " + recomendacao.feiticos.join(" + ")),
  );
  botao.addEventListener("click", () => aplicar(recomendacao, botao));
  return botao;
}

async function aplicar(recomendacao, botao, sobrescrever) {
  try {
    await chamar("/api/runas/aplicar", {
      indice: recomendacao.indice,
      sobrescrever_atual: Boolean(sobrescrever),
    });
    el("lista-runas").querySelectorAll(".runa").forEach((b) => b.setAttribute("aria-pressed", "false"));
    botao.setAttribute("aria-pressed", "true");
    mensagem("Runas aplicadas: " + recomendacao.principal, "sucesso");
  } catch (erro) {
    // Sem página "LoL Remoto" e sem espaço: só sobrescreve a atual se você confirmar.
    if (erro instanceof ErroApi && erro.codigo === "SemPaginaLivre" && !sobrescrever &&
        confirm(erro.message + "\n\nSobrescrever a página de runas atual?")) {
      await aplicar(recomendacao, botao, true);
      return;
    }
    tratarErro(erro);
  }
}
