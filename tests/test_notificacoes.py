import pytest

from lol_remoto.dominio.campeoes import Catalogo
from lol_remoto.dominio.fase import Fase
from lol_remoto.dominio.ready_check import ReadyCheck, Resposta
from lol_remoto.dominio.selecao import selecao_de
from lol_remoto.plataforma.ntfy import Notificacao, NotificadorFalso
from lol_remoto.servicos.estado import Estado
from lol_remoto.servicos.notificacoes import ServicoNotificacoes

ENDERECO = "http://100.64.0.1:8766/"
READY = ReadyCheck(em_andamento=True, resposta=Resposta.NENHUMA, segundos_decorridos=0.5)


@pytest.fixture
def montagem():
    estado = Estado()
    notificador = NotificadorFalso()
    servico = ServicoNotificacoes(estado, notificador, endereco=lambda: ENDERECO)
    estado.atualizar(conectado=True, fase=Fase.FILA)
    yield estado, notificador, servico
    servico.encerrar()


def _titulos(notificador, servico):
    servico.aguardar_envios()
    return [n.titulo for n in notificador.enviadas]


def test_sem_modo_ausente_nao_notifica(montagem):
    estado, notificador, servico = montagem
    estado.atualizar(fase=Fase.PARTIDA_ENCONTRADA, ready_check=READY)
    assert _titulos(notificador, servico) == []


def test_ligar_o_modo_ausente_manda_confirmacao(montagem):
    estado, notificador, servico = montagem
    estado.definir_ausente(True)
    assert _titulos(notificador, servico) == ["Modo ausente ligado"]
    assert notificador.enviadas[0].prioridade == 2


def test_partida_encontrada_com_modo_ausente(montagem):
    estado, notificador, servico = montagem
    estado.definir_ausente(True)
    estado.atualizar(fase=Fase.PARTIDA_ENCONTRADA, ready_check=READY)
    servico.aguardar_envios()
    notificacao = notificador.enviadas[-1]
    assert notificacao.titulo == "Partida encontrada!"
    assert notificacao.prioridade == 5
    assert notificacao.link == ENDERECO


def test_sua_vez_com_tempo_e_intencao(montagem, sessao_draft):
    estado, notificador, servico = montagem
    estado.catalogo = Catalogo.de_json([{"id": 103, "name": "Ahri"}])
    estado.definir_ausente(True)
    estado.atualizar(fase=Fase.SELECAO, selecao=selecao_de(sessao_draft))
    servico.aguardar_envios()
    notificacao = notificador.enviadas[-1]
    assert notificacao.titulo == "Sua vez de escolher!"
    assert notificacao.mensagem == "27 s restantes. Sua intenção: Ahri. Toque para abrir."


def test_dodge(montagem, sessao_aram):
    estado, notificador, servico = montagem
    estado.atualizar(fase=Fase.SELECAO, selecao=selecao_de(sessao_aram))
    estado.definir_ausente(True)
    estado.atualizar(fase=Fase.FILA, selecao=None)
    assert _titulos(notificador, servico)[-1] == "Alguém deu dodge"


def test_partida_carregando_avisa_e_desliga_o_modo_ausente(montagem):
    estado, notificador, servico = montagem
    estado.atualizar(fase=Fase.SELECAO)
    estado.definir_ausente(True)
    estado.atualizar(fase=Fase.CARREGANDO)
    assert _titulos(notificador, servico)[-1] == "Partida carregando"
    assert estado.atual.ausente is False
    estado.atualizar(fase=Fase.EM_PARTIDA)
    assert len(notificador.enviadas) == 2  # confirmação + carregando; nada dentro da partida


def test_cliente_fechando_nao_e_selecao_cancelada(montagem):
    estado, notificador, servico = montagem
    estado.atualizar(fase=Fase.SELECAO)
    estado.definir_ausente(True)
    estado.atualizar(conectado=False, fase=Fase.NENHUMA)
    assert _titulos(notificador, servico) == ["Modo ausente ligado"]


def test_conectar_no_meio_da_partida_encontrada_nao_avisa():
    estado = Estado(ausente=True)
    notificador = NotificadorFalso()
    servico = ServicoNotificacoes(estado, notificador)
    estado.atualizar(conectado=True, fase=Fase.PARTIDA_ENCONTRADA, ready_check=READY)
    assert _titulos(notificador, servico) == []
    servico.encerrar()


def test_falha_no_envio_nao_para_os_proximos(montagem):
    estado, notificador, servico = montagem
    notificador.falhar = True
    estado.definir_ausente(True)
    servico.aguardar_envios()
    notificador.falhar = False
    estado.atualizar(fase=Fase.PARTIDA_ENCONTRADA, ready_check=READY)
    assert _titulos(notificador, servico) == ["Partida encontrada!"]


def test_link_desconhecido_fica_vazio():
    estado = Estado()
    servico = ServicoNotificacoes(estado, NotificadorFalso())
    estado.atualizar(conectado=True, fase=Fase.FILA)
    from lol_remoto.dominio.avisos import Aviso, TipoAviso

    notificacao = servico.montar(Aviso(TipoAviso.DODGE), estado.atual)
    assert notificacao == Notificacao(
        "Alguém deu dodge", "Você voltou para a fila.", prioridade=4, tags=("warning",)
    )
    servico.encerrar()


def test_mensagem_do_aram(montagem, sessao_aram):
    estado, notificador, servico = montagem
    estado.catalogo = Catalogo.de_json([{"id": 36, "name": "Dr. Mundo"}])
    estado.definir_ausente(True)
    estado.atualizar(fase=Fase.SELECAO, selecao=selecao_de(sessao_aram))
    servico.aguardar_envios()
    assert notificador.enviadas[-1].mensagem == (
        "Você está de Dr. Mundo. 2 no banco. Toque para abrir."
    )


def test_mensagem_do_planejamento(montagem, sessao_draft):
    estado, notificador, servico = montagem
    sessao_draft["timer"].update(phase="PLANNING", adjustedTimeLeftInPhase=24000)
    estado.definir_ausente(True)
    estado.atualizar(fase=Fase.SELECAO, selecao=selecao_de(sessao_draft))
    servico.aguardar_envios()
    assert notificador.enviadas[-1].titulo == "Seleção começou"
    assert notificador.enviadas[-1].mensagem == (
        "Declare sua intenção de pick. 24 s restantes. Toque para abrir."
    )
