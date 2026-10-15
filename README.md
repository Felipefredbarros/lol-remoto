# LoL Remoto

[![CI](https://github.com/Felipefredbarros/lol-remoto/actions/workflows/ci.yml/badge.svg)](https://github.com/Felipefredbarros/lol-remoto/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Windows](https://img.shields.io/badge/plataforma-Windows-0078D6)
![Licença](https://img.shields.io/badge/licen%C3%A7a-MIT-green)

Controle a **fila e a seleção de campeões do League of Legends pelo celular**, para sair do PC (banheiro, cozinha, cama...) enquanto espera a partida sem perder o aceite nem a sua vez.

- **Partida encontrada:** notificação no celular com os botões **Aceitar** e **Recusar**
- **Seleção de campeões pelo celular:** declarar a intenção, **banir**, **escolher**, com busca e fotos dos campeões
- **Página em etapas:** fila → partida → intenção → ban → pick → runas, com o timer, o histórico e a **ordem dos picks** dos dois times
- **Feitiços (D e F)** e **runas recomendadas pelo próprio cliente**, separados
- **Avisos** de sua vez, dodge, seleção cancelada e partida carregando (só com o **modo ausente** ligado)
- Acesso só pela sua rede privada do **Tailscale** + **PIN**; servidor em Python **sem dependências**, inicia sozinho e invisível com o Windows

**O app nunca age dentro da partida.** Ele só faz alguma coisa na partida encontrada e na seleção de campeões, e para quando a partida começa a carregar.

## Como funciona

```
Celular ──(Tailscale)──▶ PC: servidor Python ──▶ cliente do LoL (API local, LCU)
   ▲                                │
   └────── notificação (ntfy) ◀─────┘
```

O PC roda um pequeno servidor que conversa com o cliente do LoL pela API local que o próprio cliente expõe (LCU). O celular abre a página pela rede do [Tailscale](https://tailscale.com), e os avisos chegam pelo app [ntfy](https://ntfy.sh). Detalhes em [docs/arquitetura.md](docs/arquitetura.md).

## Requisitos

- Windows 10 ou 11, com o cliente do League of Legends
- [Python 3.11+](https://www.python.org/downloads/)
- [Tailscale](https://tailscale.com/download) no PC **e** no celular, na mesma conta (gratuito)
- App [ntfy](https://ntfy.sh) no celular, para as notificações (gratuito; Android ou iPhone)

## Instalação

**1. Tailscale:** instale no PC e no celular e entre com a mesma conta. No app do celular, confira se o PC aparece na lista.

**2. Baixe o projeto:**
```powershell
git clone https://github.com/Felipefredbarros/lol-remoto.git
cd lol-remoto
```

**3. Instale para iniciar com o Windows** (PowerShell **como Administrador**, na pasta do projeto):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\instalar.ps1
```
Na primeira instalação o script pede para você **definir o PIN** (ou deixar vazio para gerar um). No final ele mostra o endereço para o celular e oferece uma **notificação de teste**, que também mostra o **tópico do ntfy**.

**4. No celular:**
- No app **ntfy**, assine o tópico mostrado pelo instalador. Para ver de novo: `cd src; py -m lol_remoto --testar-notificacao`.
- Com o Tailscale ligado, abra `http://100.x.y.z:8766` (o IP do PC que aparece no app do Tailscale) e entre com o PIN. Use **"Adicionar à tela inicial"** no menu do navegador.

## Como usar

1. Entre na fila no PC.
2. Antes de sair, toque em **Modo ausente** na página. Sem ele não chega notificação; ele desliga sozinho quando a partida carrega.
3. Partida encontrada: aceite pela notificação ou pela página.
4. Na seleção, a página mostra a etapa atual: declare a intenção, bana, escolha, e depois troque os feitiços e aplique uma das runas recomendadas.

As runas são gravadas numa página chamada **"LoL Remoto"**. Se ela não existir e não houver espaço para criar, a página pergunta antes de sobrescrever a sua página atual. Dica: renomeie uma das suas páginas para "LoL Remoto".

**Testar sem abrir uma partida:** `cd src; py -m lol_remoto --simular` sobe um cliente do LoL falso com bots, na porta **8767** (para rodar junto com o app instalado).

## Segurança

| Camada | O que faz |
|---|---|
| Tailscale | Só os seus aparelhos enxergam o PC; o tráfego é criptografado (WireGuard). Nada fica exposto na internet. |
| Endereço de escuta | O servidor ouve só em `127.0.0.1` e no IP do Tailscale, nunca no Wi-Fi comum. |
| Firewall | As portas 8766 e 8767 só aceitam a faixa do Tailscale (`100.64.0.0/10`). |
| PIN | Mínimo de 6 dígitos, bloqueio de 5 min após 5 erros. Só o hash fica salvo (PBKDF2-SHA256, 600 mil iterações), em `%APPDATA%\LolRemoto`, fora do repositório. |
| Sessão | Cookie `HttpOnly` e `SameSite=Strict`, válido por 30 dias; no disco fica só o SHA-256 do token. Trocar o PIN encerra todas as sessões. |
| Notificações | Tópico do ntfy aleatório. Os botões Aceitar/Recusar levam um token de uso único que vale 15 s. |
| Sites maliciosos | O servidor só aceita pedidos endereçados a este PC (`Host`/`Origin`) e em JSON, o que bloqueia CSRF e DNS rebinding. |
| Cliente do LoL | Conexão HTTPS verificada com o certificado da Riot. O app só lê o que precisa da seleção atual e das runas; nada da sua conta é guardado. |

**Recomendações:**
- Ative a **verificação em duas etapas** na conta que você usa no Tailscale.
- No [painel do Tailscale](https://login.tailscale.com/admin/machines), use **Disable key expiry** no PC, senão ele sai da rede depois de alguns meses.
- O tópico do ntfy funciona como uma senha: não compartilhe.

## Solução de problemas

| Problema | O que fazer |
|---|---|
| Celular mostra "Sem conexão com o PC" | Confira se o Tailscale está ligado no celular e no PC e se o PC aparece como *online*. |
| Não chega notificação | Ligue o **Modo ausente** na página. Confira se o app ntfy assina o tópico certo (`--testar-notificacao`). |
| "Já está rodando?" ao abrir no terminal | O app instalado já usa a porta 8766. Para testar código novo, rode `scripts\reiniciar.ps1`. |
| Página mostra "Host não permitido" | Use o IP do Tailscale (`http://100.x.y.z:8766`). |
| Esqueci o PIN | Ele não fica salvo (só o hash). Defina outro com `cd src; py -m lol_remoto --trocar-pin` e rode `scripts\reiniciar.ps1`. |

Log: `%LOCALAPPDATA%\LolRemoto\lol-remoto.log`

## Atualizar e desinstalar

```powershell
git pull
powershell -ExecutionPolicy Bypass -File scripts\reiniciar.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\desinstalar.ps1   # como Administrador
```
Depois, se quiser, apague as pastas `%APPDATA%\LolRemoto` e `%LOCALAPPDATA%\LolRemoto`.

## Limitações

- Usa a API local do cliente (LCU), que **não é oficial**: um patch da Riot pode mudar o formato sem aviso. As decisões e o que já foi conferido ao vivo estão em [docs/roteiro.md](docs/roteiro.md).
- Testado ao vivo na escolha alternada (normal e ranqueada). O ARAM foi testado numa personalizada. Swiftplay e Arena não têm ações específicas.
- Só Windows.

## Desenvolvimento

```powershell
py -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\python -m pytest
.venv\Scripts\ruff check .
```

- [CLAUDE.md](CLAUDE.md): mapa do código, regras do projeto e como adicionar ações e avisos
- [docs/arquitetura.md](docs/arquitetura.md): camadas, fluxo e rotas da API
- [docs/decisoes/](docs/decisoes/): decisões de arquitetura (ADRs)
- [CHANGELOG.md](CHANGELOG.md)

Projeto irmão: [desligador](https://github.com/Felipefredbarros/desligador).

## Aviso legal

O LoL Remoto não é endossado pela Riot Games e não reflete as opiniões da Riot Games nem de ninguém envolvido oficialmente na produção ou no gerenciamento das propriedades da Riot Games. Riot Games e League of Legends são marcas registradas da Riot Games, Inc.

## Licença

[MIT](LICENSE)
