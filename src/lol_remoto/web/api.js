// Conversa com o servidor do PC: JSON (com cookie de sessão) e o stream SSE.

export class ErroApi extends Error {
  constructor(mensagem, status, codigo) {
    super(mensagem);
    this.status = status;
    this.codigo = codigo || ""; // nome do erro no servidor, ex.: "SemPaginaLivre"
  }
}

export async function chamar(caminho, corpo) {
  const opcoes = corpo === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  };
  let resposta;
  try {
    resposta = await fetch(caminho, opcoes);
  } catch (erro) {
    // fetch lança TypeError quando não alcança o PC (desligado, sem Tailscale...).
    throw new ErroApi("Sem conexão com o PC.", 0);
  }
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) {
    throw new ErroApi(dados.erro || "Erro " + resposta.status, resposta.status, dados.codigo);
  }
  return dados;
}

// Abre o stream do estado. `aoCair` recebe a fonte quando ela fecha ou perde a conexão.
export function ouvir(aoReceber, aoCair) {
  const fonte = new EventSource("/api/eventos");
  fonte.addEventListener("message", (evento) => aoReceber(JSON.parse(evento.data)));
  fonte.addEventListener("error", () => aoCair(fonte));
  return fonte;
}
