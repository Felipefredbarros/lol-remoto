import threading

from lol_remoto.dominio.fase import Fase
from lol_remoto.dominio.selecao import selecao_de
from lol_remoto.servicos.estado import Estado


class _Relogio:
    def __init__(self):
        self.agora = 100.0

    def __call__(self):
        return self.agora


def test_atualizar_cria_versao_nova_e_avisa_ouvintes():
    estado = Estado()
    pares = []
    estado.assinar(lambda anterior, novo: pares.append((anterior.fase, novo.fase, novo.versao)))
    estado.atualizar(conectado=True, fase=Fase.LOBBY)
    estado.atualizar(fase=Fase.FILA)
    assert pares == [(Fase.NENHUMA, Fase.LOBBY, 1), (Fase.LOBBY, Fase.FILA, 2)]
    assert estado.atual.fase is Fase.FILA


def test_sem_mudanca_real_nao_avisa_nem_muda_versao():
    estado = Estado()
    chamadas = []
    estado.assinar(lambda a, n: chamadas.append(n))
    estado.atualizar(fase=Fase.LOBBY)
    estado.atualizar(fase=Fase.LOBBY)
    assert len(chamadas) == 1 and estado.atual.versao == 1


def test_mesma_selecao_de_novo_mantem_o_instante_original(sessao_draft):
    relogio = _Relogio()
    estado = Estado(relogio=relogio)
    estado.atualizar(selecao=selecao_de(sessao_draft))
    relogio.agora = 105.0
    estado.atualizar(selecao=selecao_de(sessao_draft))
    assert estado.atual.selecao_recebida_em == 100.0
    assert estado.atual.versao == 1


def test_selecao_nova_registra_o_instante(sessao_draft):
    relogio = _Relogio()
    estado = Estado(relogio=relogio)
    estado.atualizar(selecao=selecao_de(sessao_draft))
    relogio.agora = 107.0
    sessao_draft["timer"]["adjustedTimeLeftInPhase"] = 20000
    estado.atualizar(selecao=selecao_de(sessao_draft))
    assert estado.atual.selecao_recebida_em == 107.0


def test_ouvinte_com_erro_nao_atrapalha_os_outros():
    estado = Estado()
    recebidos = []

    def quebrado(anterior, novo):
        raise RuntimeError("bug")

    estado.assinar(quebrado)
    estado.assinar(lambda a, n: recebidos.append(n.fase))
    estado.atualizar(fase=Fase.FILA)
    assert recebidos == [Fase.FILA]


def test_ouvinte_pode_atualizar_de_novo():
    estado = Estado(ausente=True)

    def desligar_ao_carregar(anterior, novo):
        if novo.fase is Fase.CARREGANDO and novo.ausente:
            estado.definir_ausente(False)

    estado.assinar(desligar_ao_carregar)
    estado.atualizar(fase=Fase.CARREGANDO)
    assert estado.atual.ausente is False
    assert estado.atual.versao == 2


def test_esperar_mudanca():
    estado = Estado()
    assert estado.esperar_mudanca(0, tempo_limite=0.05).versao == 0  # tempo esgotado
    threading.Timer(0.05, lambda: estado.atualizar(fase=Fase.FILA)).start()
    assert estado.esperar_mudanca(0, tempo_limite=2).fase is Fase.FILA


def test_momento():
    estado = Estado()
    estado.atualizar(fase=Fase.SELECAO)
    assert estado.atual.momento.fase is Fase.SELECAO
    assert estado.atual.momento.selecao is None
