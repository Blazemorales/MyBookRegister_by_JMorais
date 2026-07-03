"""Camada de tempo real (Socket.IO) para a página CEP.

Fluxo:

    Raspberry Pi  ──emit("rpi_data")──▶  Servidor Socket.IO
                                              │  valida + normaliza
                                              ▼
        Frontend (aba "Receber relatório")  ◀──emit("relatorio_data")──┘
                  inscrito na room RELATORIO_ROOM

Autenticação no handshake (`auth`):

    Frontend:  { "role": "frontend", "token": "<JWT do /login>" }
    RPi:       { "role": "rpi",      "token": "<RPI_DEVICE_TOKEN>" }

O servidor é montado como ASGI em ``backend_api`` e compartilha o mesmo
processo do FastAPI, então não há porta extra para expor.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from numbers import Number
from typing import Any, Optional

import jwt
import socketio

from auth import ALGORITHM, SECRET_KEY
from cep_alertas import analisar_ponto, extrair_escalar


logger = logging.getLogger(__name__)


# ── Configuração ───────────────────────────────────────────────────────

_DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def get_allowed_origins() -> list[str]:
    """Origens CORS permitidas (mesma var do FastAPI: ``ALLOWED_ORIGINS``)."""
    return [
        o.strip()
        for o in os.environ.get("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",")
        if o.strip()
    ]


ALLOWED_ORIGINS = get_allowed_origins()

# Token compartilhado que o Raspberry Pi usa para se autenticar. Sem ele,
# nenhuma conexão com role="rpi" é aceita (fail-closed).
RPI_DEVICE_TOKEN = os.environ.get("RPI_DEVICE_TOKEN", "")

# Room onde vive a aba "Receber relatório". Todo frontend autenticado
# entra aqui automaticamente; os dados do RPi são emitidos para ela.
RELATORIO_ROOM = "receber_relatorio"

# Cartas CEP aceitas (opcional no payload, mas validada quando presente).
CARTAS_VALIDAS = {"xr", "p", "u", "imr"}

# Rate-limit por conexão RPi. Protege o frontend de um dispositivo defeituoso
# que comece a emitir centenas de mensagens por segundo. 0 ou negativo desliga.
RPI_RATE_LIMIT_HZ = float(os.environ.get("RPI_RATE_LIMIT_HZ", "20"))
_BUCKET_BURST = max(1.0, RPI_RATE_LIMIT_HZ)  # margem de ~1s para rajadas

# Limite servidor-side do replay (cliente pode pedir N, mas N é cortado por isso).
# Evita pedido absurdo varrer a tabela inteira.
STREAM_REPLAY_MAX = int(os.environ.get("STREAM_REPLAY_MAX", "200"))

# DB manager injetado pelo backend_api no startup. Mantém realtime
# desacoplado do tipo concreto e evita ciclo de import.
_db = None


def set_db(mgr) -> None:
    """Injeta o AsyncDBUserManager. Chamado uma vez por backend_api."""
    global _db
    _db = mgr

# sid -> (tokens_disponíveis, last_refill_ts). Estado em memória do processo —
# se um dia escalar horizontalmente, migrar para Redis (AsyncRedisManager).
_buckets: dict[str, tuple[float, float]] = {}


def _consumir_token(sid: str, *, agora: Optional[float] = None) -> bool:
    """Token bucket por sid. Repõe à taxa de RPI_RATE_LIMIT_HZ tokens/s,
    com burst até `_BUCKET_BURST`. Retorna False quando esgotado.
    """
    if RPI_RATE_LIMIT_HZ <= 0:
        return True  # desligado
    if agora is None:
        agora = time.monotonic()
    tokens, last = _buckets.get(sid, (_BUCKET_BURST, agora))
    tokens = min(_BUCKET_BURST, tokens + (agora - last) * RPI_RATE_LIMIT_HZ)
    if tokens < 1.0:
        _buckets[sid] = (tokens, agora)
        return False
    _buckets[sid] = (tokens - 1.0, agora)
    return True


# ── Servidor ───────────────────────────────────────────────────────────

# Escalabilidade horizontal via Redis pub/sub. Quando REDIS_URL está definida,
# múltiplas instâncias do backend compartilham rooms e eventos Socket.IO via
# AsyncRedisManager. Sem REDIS_URL o servidor usa pub/sub em memória (single
# instance, dev local e Render free-tier single-instance).
_REDIS_URL = os.environ.get("REDIS_URL", "")
_SOCKETIO_DEBUG = os.environ.get("SOCKETIO_DEBUG", "").lower() in {"1", "true"}
_SIO_KWARGS = dict(
    async_mode="asgi",
    cors_allowed_origins=ALLOWED_ORIGINS or "*",
    # Heartbeats: detectam quedas rápido e mantêm a conexão viva atrás de
    # proxies (Render/Vercel). A reconexão em si é responsabilidade do
    # cliente (ver socket.io-client `reconnection: true`, default).
    ping_interval=25,
    ping_timeout=20,
    logger=_SOCKETIO_DEBUG,
    engineio_logger=_SOCKETIO_DEBUG,
)

if _REDIS_URL:
    logger.info("Socket.IO usando AsyncRedisManager (%s)", _REDIS_URL)
    sio = socketio.AsyncServer(
        client_manager=socketio.AsyncRedisManager(_REDIS_URL),
        **_SIO_KWARGS,
    )
else:
    sio = socketio.AsyncServer(**_SIO_KWARGS)


# ── Validação dos dados do RPi ─────────────────────────────────────────

def _canal_da_sessao(canal: Any) -> Optional[str]:
    """Normaliza um identificador de canal/dispositivo opcional."""
    if canal is None:
        return None
    canal = str(canal).strip()
    return canal or None


def validar_payload_rpi(data: Any) -> dict[str, Any]:
    """Validação básica do que o RPi envia antes de repassar ao frontend.

    Regras (propositalmente permissivas — o RPi pode mandar formatos
    variados), mas garantindo que o frontend nunca receba lixo:

    - precisa ser um objeto/dict;
    - precisa carregar *algum* dado de medição
      (`valor`, `valores`, `measurements` ou `dados`);
    - `chart`, se presente, tem que ser uma carta CEP válida;
    - números têm que ser finitos.

    Levanta ``ValueError`` com mensagem amigável quando inválido.
    """
    if not isinstance(data, dict):
        raise ValueError("payload deve ser um objeto JSON")

    limpo: dict[str, Any] = {}

    chart = data.get("chart") or data.get("Chart")
    if chart is not None:
        chart = str(chart).strip().lower()
        if chart not in CARTAS_VALIDAS:
            raise ValueError(
                f"chart inválida {chart!r} (esperado: {sorted(CARTAS_VALIDAS)})"
            )
        limpo["chart"] = chart

    # Pelo menos um campo de medição precisa existir.
    medicao_keys = ("valor", "valores", "measurements", "dados", "value", "values")
    presentes = [k for k in medicao_keys if data.get(k) is not None]
    if not presentes:
        raise ValueError(
            "payload sem dados de medição "
            f"(esperado algum de: {list(medicao_keys)})"
        )

    for k in presentes:
        valor = data[k]
        _checar_numeros_finitos(valor, campo=k)
        limpo[k] = valor

    # Campos de metadados opcionais repassados como vieram.
    for meta in ("unidade", "amostra", "subgrupo", "label", "tag"):
        if data.get(meta) is not None:
            limpo[meta] = data[meta]

    canal = _canal_da_sessao(data.get("canal") or data.get("device") or data.get("device_id"))
    if canal:
        limpo["canal"] = canal

    # Timestamp do dispositivo, se houver; senão carimba no servidor.
    limpo["device_ts"] = data.get("timestamp") or data.get("ts")
    limpo["received_at"] = datetime.now(timezone.utc).isoformat()

    return limpo


def _checar_numeros_finitos(valor: Any, *, campo: str) -> None:
    """Garante que números (escalares ou em listas) sejam finitos."""
    import math

    if isinstance(valor, bool):  # bool é subtipo de int — ignora
        return
    if isinstance(valor, Number):
        if not math.isfinite(float(valor)):
            raise ValueError(f"campo {campo!r} contém número não-finito")
        return
    if isinstance(valor, (list, tuple)):
        for item in valor:
            _checar_numeros_finitos(item, campo=campo)
        return
    if isinstance(valor, dict):
        for item in valor.values():
            _checar_numeros_finitos(item, campo=campo)
        return
    # strings e None são aceitos como metadados


# ── Helpers de autenticação no handshake ───────────────────────────────

def _validar_jwt(token: str) -> Optional[str]:
    """Decodifica o JWT do frontend e devolve o username (ou None)."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        logger.info("JWT inválido no handshake Socket.IO: %s", exc)
        return None
    return payload.get("sub")


# ── Handlers de eventos ────────────────────────────────────────────────

@sio.event
async def connect(sid: str, environ: dict, auth: Optional[dict] = None) -> None:
    """Autentica e classifica a conexão (frontend x rpi).

    Levantar ``ConnectionRefusedError`` rejeita o handshake.
    """
    auth = auth or {}
    role = str(auth.get("role", "frontend")).lower()
    token = auth.get("token", "")

    if role == "rpi":
        if not RPI_DEVICE_TOKEN:
            logger.warning("conexão RPi recusada: RPI_DEVICE_TOKEN não configurado")
            raise ConnectionRefusedError("rpi auth indisponível no servidor")
        if token != RPI_DEVICE_TOKEN:
            logger.warning("conexão RPi recusada: token inválido (sid=%s)", sid)
            raise ConnectionRefusedError("token de dispositivo inválido")
        await sio.save_session(sid, {"role": "rpi"})
        logger.info("RPi conectado (sid=%s)", sid)
        return

    # role == "frontend" (default)
    username = _validar_jwt(token) if token else None
    if not username:
        raise ConnectionRefusedError("token de usuário inválido ou ausente")

    await sio.save_session(sid, {"role": "frontend", "username": username})
    # Entra na room da aba "Receber relatório" automaticamente.
    await sio.enter_room(sid, RELATORIO_ROOM)
    logger.info("frontend conectado (sid=%s, user=%s)", sid, username)
    await sio.emit("conectado", {"ok": True, "room": RELATORIO_ROOM}, to=sid)


@sio.event
async def disconnect(sid: str) -> None:
    _buckets.pop(sid, None)
    logger.info("desconectado (sid=%s)", sid)


@sio.event
async def subscribe_relatorio(sid: str, data: Optional[dict] = None) -> dict:
    """Frontend (re)inscreve-se na aba, opcionalmente num canal, e pode
    pedir um replay do histórico recente via `replay_n`.

    Útil após reconexão: o frontend não perde o contexto enquanto estava fora.
    """
    session = await sio.get_session(sid)
    if session.get("role") != "frontend":
        return {"ok": False, "error": "apenas frontends podem se inscrever"}

    payload = data or {}
    await sio.enter_room(sid, RELATORIO_ROOM)
    canal = _canal_da_sessao(payload.get("canal"))
    if canal:
        await sio.enter_room(sid, f"{RELATORIO_ROOM}:{canal}")

    # Replay opcional. Limite servidor-side (STREAM_REPLAY_MAX) é teto duro
    # para evitar varredura abusiva da tabela.
    try:
        pedido = int(payload.get("replay_n") or 0)
    except (TypeError, ValueError):
        pedido = 0
    replay = max(0, min(STREAM_REPLAY_MAX, pedido))

    enviados = 0
    if replay > 0 and _db is not None:
        try:
            pontos = await _db.ultimas_medicoes_stream(canal or "default", replay)
            for ponto in pontos:
                await sio.emit("relatorio_data", ponto, to=sid)
                enviados += 1
        except Exception:
            logger.exception("falha ao enviar replay para sid=%s", sid)

    return {
        "ok": True,
        "room": RELATORIO_ROOM,
        "canal": canal,
        "replay": enviados,
    }


@sio.on("rpi_data")
async def rpi_data(sid: str, data: Any) -> dict:
    """Recebe dados do Raspberry Pi, valida e transmite ao frontend.

    Retorna um ack (entregue ao RPi) com o status e quantos clientes
    receberam — útil para o RPi confirmar a entrega.
    """
    session = await sio.get_session(sid)
    if session.get("role") != "rpi":
        logger.warning("rpi_data de origem não-rpi recusado (sid=%s)", sid)
        return {"ok": False, "error": "não autorizado a publicar dados do RPi"}

    if not _consumir_token(sid):
        logger.warning(
            "rate-limit RPi excedido (sid=%s, limite=%.1f Hz)",
            sid,
            RPI_RATE_LIMIT_HZ,
        )
        await sio.emit(
            "rpi_erro",
            {"error": "rate-limit excedido", "limit_hz": RPI_RATE_LIMIT_HZ},
            to=sid,
        )
        return {"ok": False, "error": "rate-limit excedido"}

    try:
        limpo = validar_payload_rpi(data)
    except ValueError as exc:
        logger.info("payload do RPi rejeitado (sid=%s): %s", sid, exc)
        # devolve o erro pro RPi, mas NÃO repassa ao frontend
        await sio.emit("rpi_erro", {"error": str(exc)}, to=sid)
        return {"ok": False, "error": str(exc)}

    # Broadcast para a aba "Receber relatório".
    await sio.emit("relatorio_data", limpo, room=RELATORIO_ROOM)

    # Emissão direcionada extra para quem assinou um canal específico.
    canal = limpo.get("canal")
    if canal:
        await sio.emit("relatorio_data", limpo, room=f"{RELATORIO_ROOM}:{canal}")

    # Persistir em background — não bloqueia o broadcast nem o ack. Perda
    # de mensagens em queda do processo é aceitável (medições CEP admitem
    # gaps), em troca de latência menor no caminho hot.
    if _db is not None:
        asyncio.create_task(
            _persistir_medicao(canal or "default", limpo.get("chart"), limpo),
        )

    # Análise CEP em streaming. Só dispara para payloads escalares; lotes
    # (`valores`, `dados`) seguem sem análise — quem quiser pode mandar
    # ponto-a-ponto. A análise é síncrona e barata (sem numpy/scipy).
    escalar = extrair_escalar(limpo)
    if escalar is not None:
        try:
            for alerta in analisar_ponto(canal or "default", escalar):
                await sio.emit("alerta_cep", alerta, room=RELATORIO_ROOM)
                if canal:
                    await sio.emit(
                        "alerta_cep", alerta, room=f"{RELATORIO_ROOM}:{canal}"
                    )
        except Exception:
            logger.exception("falha na análise CEP (canal=%s)", canal)

    logger.debug("relatorio_data emitido para room %s", RELATORIO_ROOM)
    return {"ok": True, "received_at": limpo["received_at"]}


async def _persistir_medicao(
    canal: str, chart: Optional[str], payload: dict
) -> None:
    try:
        await _db.salvar_medicao_stream(canal, chart, payload)
    except Exception:
        logger.exception("falha ao persistir medição (canal=%s)", canal)


# Alias amigável: alguns clientes podem emitir "report" em vez de "rpi_data".
sio.on("report", rpi_data)


@sio.on("rpi_status")
async def rpi_status(sid: str, data: Any) -> dict:
    """Status ao vivo de um dispositivo (ex.: lâmpada ligada/desligada).

    Diferente de `rpi_data`: não é uma medição CEP, é só um flag efêmero
    de estado. Não passa por validação de carta nem é persistido — o
    frontend só precisa saber o estado *atual*, não o histórico (que já
    vem pelas sessões em `relatorio_data`/`medicoes_stream`).
    """
    session = await sio.get_session(sid)
    if session.get("role") != "rpi":
        logger.warning("rpi_status de origem não-rpi recusado (sid=%s)", sid)
        return {"ok": False, "error": "não autorizado a publicar status do RPi"}

    if not isinstance(data, dict):
        return {"ok": False, "error": "payload deve ser um objeto JSON"}

    canal = _canal_da_sessao(data.get("canal")) or "default"
    payload = {
        "canal": canal,
        "aceso": bool(data.get("aceso")),
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    await sio.emit("device_status", payload, room=f"{RELATORIO_ROOM}:{canal}")
    return {"ok": True}


def make_asgi_app(other_asgi_app) -> socketio.ASGIApp:
    """Empacota o FastAPI (`other_asgi_app`) + Socket.IO num único ASGI app.

    O Socket.IO atende em ``/socket.io/`` (default do cliente) e todo o
    resto cai no FastAPI. Eventos de lifespan são repassados ao FastAPI,
    então o startup/shutdown do banco continua funcionando.
    """
    return socketio.ASGIApp(sio, other_asgi_app=other_asgi_app)
