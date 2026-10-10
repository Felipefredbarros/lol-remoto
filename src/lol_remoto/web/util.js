// Utilidades de tela. Regra: texto vindo do cliente do LoL (nomes) entra só por textContent.

export const el = (id) => document.getElementById(id);

export function criar(tag, classe, texto) {
  const elemento = document.createElement(tag);
  if (classe) elemento.className = classe;
  if (texto !== undefined && texto !== null) elemento.textContent = texto;
  return elemento;
}

export function normalizar(texto) {
  return texto.normalize("NFKD").replace(/[̀-ͯ]/g, "")
    .toLowerCase().replace(/[^a-z0-9]/g, "");
}

function iniciais(nome) {
  return (nome || "?").replace(/[^A-Za-zÀ-ÿ ]/g, "").split(" ")
    .map((parte) => parte.charAt(0)).join("").slice(0, 2).toUpperCase() || "?";
}

// Ícone do campeão (ou um círculo vazio). Se a imagem não carregar, mostra as iniciais.
export function icone(campeao, classeExtra) {
  const classe = "avatar" + (classeExtra ? " " + classeExtra : "");
  if (!campeao) return criar("span", classe + " vazio");
  const imagem = criar("img", classe);
  imagem.alt = campeao.nome;
  imagem.title = campeao.nome;
  imagem.loading = "lazy";
  imagem.src = "/api/campeoes/" + campeao.id + ".png";
  imagem.addEventListener("error", () => {
    const substituto = criar("span", classe, iniciais(campeao.nome));
    substituto.title = campeao.nome;
    imagem.replaceWith(substituto);
  }, { once: true });
  return imagem;
}

function formatar(segundos) {
  const m = Math.floor(segundos / 60);
  const s = segundos % 60;
  return m > 0 ? m + ":" + String(s).padStart(2, "0") : String(s);
}

// Contagens regressivas locais: o servidor manda os segundos restantes, a página conta.
const contagens = new Map();

export function contar(elemento, segundos) {
  clearInterval(contagens.get(elemento));
  if (segundos === null || segundos === undefined) {
    elemento.textContent = "";
    return;
  }
  const fim = Date.now() + segundos * 1000;
  const atualizar = () => {
    const restante = Math.max(0, Math.round((fim - Date.now()) / 1000));
    elemento.textContent = formatar(restante);
    if (restante === 0) clearInterval(contagens.get(elemento));
  };
  atualizar();
  contagens.set(elemento, setInterval(atualizar, 250));
}

export function mensagem(texto, tipo) {
  const alvo = el("mensagem");
  alvo.textContent = texto || "";
  alvo.dataset.tipo = tipo || "info";
}
