// Início da página: login, stream do estado (SSE) e ações.

import { chamar, ErroApi, ouvir } from "./api.js";
import * as campeoes from "./campeoes.js";
import * as etapas from "./etapas.js";
import * as feiticos from "./feiticos.js";
import * as painel from "./painel.js";
import * as runas from "./runas.js";
import * as selecao from "./selecao.js";
import { el, mensagem } from "./util.js";

let fonte = null;
let religar = null;
let versaoMostrada = -1;

// A resposta de um botão pode chegar depois de um estado mais novo vindo pelo SSE (ex.: trocar
// o feitiço): sem esta conferência, a página voltava a mostrar o feitiço anterior.
function desenhar(estado) {
  if (estado.versao < versaoMostrada) return;
  versaoMostrada = estado.versao;
  etapas.desenhar(estado);
  painel.desenhar(estado);
  selecao.desenhar(estado);
}

function pedirLogin() {
  clearTimeout(religar);
  if (fonte) fonte.close();
  fonte = null;
  el("tela-app").hidden = true;
  el("sair").hidden = true;
  el("tela-login").hidden = false;
  el("pin").focus();
}

function mostrarApp() {
  el("tela-login").hidden = true;
  el("tela-app").hidden = false;
  el("sair").hidden = false;
}

function conectar() {
  clearTimeout(religar);
  versaoMostrada = -1; // o servidor pode ter reiniciado (a versão recomeça do zero)
  if (fonte) fonte.close();
  fonte = ouvir((estado) => {
    painel.conexao("");
    desenhar(estado);
  }, caiu);
}

// O EventSource reconecta sozinho se a rede cair; se o servidor recusar (ex.: 401), fecha.
async function caiu(origem) {
  if (origem !== fonte) return;
  if (origem.readyState !== EventSource.CLOSED) {
    painel.conexao("Reconectando ao PC…");
    return;
  }
  try {
    versaoMostrada = -1;
    desenhar(await chamar("/api/estado"));
  } catch (erro) {
    if (erro.status === 401) {
      pedirLogin();
      return;
    }
    painel.conexao("Sem conexão com o PC. Tentando de novo…");
  }
  religar = setTimeout(conectar, 3000);
}

async function agir(caminho, corpo, textoSucesso) {
  try {
    const dados = await chamar(caminho, corpo);
    if (dados.versao !== undefined) desenhar(dados);
    mensagem(textoSucesso || "", "sucesso");
  } catch (erro) {
    if (erro instanceof ErroApi && erro.status === 401) pedirLogin();
    else mensagem(erro.message, "erro");
  }
}

el("form-login").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  try {
    versaoMostrada = -1;
    desenhar(await chamar("/api/entrar", { pin: el("pin").value.trim() }));
    el("pin").value = "";
    mensagem("");
    mostrarApp();
    conectar();
  } catch (erro) {
    mensagem(erro.message, "erro");
  }
});

el("sair").addEventListener("click", async () => {
  await chamar("/api/sair", {}).catch(() => {});
  pedirLogin();
});

// Ao voltar para a página (celular desbloqueado), garante que o stream está vivo.
document.addEventListener("visibilitychange", () => {
  if (document.hidden || el("tela-app").hidden) return;
  if (!fonte || fonte.readyState === EventSource.CLOSED) conectar();
});

painel.iniciar(agir);
campeoes.iniciar(agir);
feiticos.iniciar(agir);
runas.iniciar(pedirLogin);

chamar("/api/estado").then((estado) => {
  desenhar(estado);
  mostrarApp();
  conectar();
}).catch((erro) => {
  if (erro.status === 401) {
    pedirLogin();
    return;
  }
  mostrarApp();
  painel.conexao(erro.message);
  religar = setTimeout(conectar, 3000);
});
