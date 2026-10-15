# 0011 — Instalação como tarefa no logon, com firewall só para o Tailscale

**Status:** aceita · **Data:** 2026-10-15

## Contexto
Até aqui o Felipe abria um terminal e rodava `py -m lol_remoto` antes de jogar. Esquecer isso é justamente o caso em que o app faz falta: ele sai do PC na fila e o celular não alcança nada. O [desligador](https://github.com/Felipefredbarros/desligador) já resolve o mesmo problema no mesmo PC, com uma tarefa agendada e uma regra de firewall.

## Decisão
- **`scripts/instalar.ps1`** (administrador), igual ao do desligador:
  - **Tarefa "LoL Remoto"** no Agendador, no **logon do usuário**, com `pythonw.exe -m lol_remoto` (sem janela), `RunLevel Limited` e reinício automático (3 vezes, 1 min).
  - **Firewall "LoL Remoto (Tailscale)":** entrada TCP na porta do config (8766) e na seguinte (8767, do `--simular`), **só de `100.64.0.0/10`**. O app já escuta só em `127.0.0.1` e no IP do Tailscale; a regra é a segunda camada.
  - **PIN antes da tarefa:** sem config, o app geraria um PIN aleatório e o mostraria num console que não existe. O instalador roda `--trocar-pin` quando não há config e mantém o que já existe.
  - No fim mostra o endereço para o celular e oferece `--testar-notificacao`, que também mostra o tópico do ntfy para assinar (só no console, nunca no log).
- **`scripts/desinstalar.ps1`** remove a tarefa e a regra e mantém a configuração e os logs.
- **`scripts/reiniciar.ps1`** só para e inicia a tarefa, para pegar o código novo depois de atualizar.
- **`--simular` na porta seguinte** (`config.para_simulacao`), para rodar junto com o app instalado sem brigar pela porta.
- Os scripts são **só ASCII** (regra 11) e têm conferências estáticas em `tests/test_scripts.py`.

## Consequências
- O app fica sempre disponível depois do logon, sem janela e sem privilégio de administrador.
- Abrir o app num terminal com o instalado rodando falha na porta ("já está rodando?"). Para usar o código novo, rode `reiniciar.ps1`.
- Para o celular simular, a página fica em `:8767`.
