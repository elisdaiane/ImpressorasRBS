import logging
import os
import smtplib
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from email.message import EmailMessage
from threading import Thread
from time import sleep
from uuid import uuid4

from config.configuracoes import SMTP_HOST, SMTP_PORTA, SMTP_TIMEOUT_ESTOQUE
from estoque import conectar


logger = logging.getLogger(__name__)


def _preparar_envio(agora):
    if agora.weekday() != 0 or agora.hour < 8:
        return None

    semana = agora.date().isoformat()
    token = uuid4().hex
    with closing(conectar()) as conexao, conexao:
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS envios_estoque_semanal (
                semana TEXT PRIMARY KEY,
                token TEXT NOT NULL,
                iniciado_em TEXT NOT NULL,
                enviado_em TEXT
            )
        """)
        conexao.execute("BEGIN IMMEDIATE")
        anterior = conexao.execute(
            "SELECT iniciado_em, enviado_em FROM envios_estoque_semanal WHERE semana = ?",
            (semana,),
        ).fetchone()
        if anterior:
            iniciado_em, enviado_em = anterior
            if enviado_em or datetime.fromisoformat(iniciado_em) > agora - timedelta(minutes=15):
                return None
            conexao.execute(
                "DELETE FROM envios_estoque_semanal WHERE semana = ?", (semana,)
            )
        conexao.execute(
            "INSERT INTO envios_estoque_semanal (semana, token, iniciado_em) VALUES (?, ?, ?)",
            (semana, token, agora.isoformat()),
        )
        if not conexao.execute(
            "SELECT 1 FROM sugestoes_estoque WHERE semana = ?", (semana,)
        ).fetchone():
            conexao.execute(
                "INSERT INTO sugestoes_estoque (semana, criada_em) VALUES (?, ?)",
                (semana, agora.isoformat()),
            )
            conexao.execute("""
                INSERT INTO sugestoes_estoque_itens
                    (semana, toner_id, marca, codigo, cor, modelos, estoque, minimo)
                SELECT ?, id, marca, codigo, cor, modelos_compativeis, estoque, estoque_minimo
                FROM toners WHERE ativo = 1 AND estoque <= estoque_minimo
            """, (semana,))
        itens = conexao.execute("""
            SELECT marca, codigo, cor, modelos, estoque, minimo
            FROM sugestoes_estoque_itens WHERE semana = ?
            ORDER BY marca, codigo, cor
        """, (semana,)).fetchall()
    return semana, token, itens


def _mensagem(itens, remetente, destinatario):
    mensagem = EmailMessage()
    mensagem["Subject"] = "Sugestão semanal de reposição de toners"
    mensagem["From"] = remetente
    mensagem["To"] = destinatario
    linhas = ["Bom dia!", ""]
    sugeridos = [
        (marca, codigo, cor, max(0, minimo - saldo))
        for marca, codigo, cor, _modelos, saldo, minimo in itens
        if minimo > saldo
    ]
    if sugeridos:
        linhas.extend(["Gostaria de solicitar os seguintes toners:", ""])
        for marca, codigo, cor, quantidade in sugeridos:
            unidade = "unidade" if quantidade == 1 else "unidades"
            linhas.append(f"- Toner {marca} {codigo} ({cor}) — {quantidade} {unidade}")
    else:
        linhas.append("Não há quantidades de toners sugeridas nesta semana.")
    linhas.extend([
        "",
        "Obrigada!",
        "",
        "Sugestão automática: nenhum pedido foi realizado.",
    ])
    mensagem.set_content("\n".join(linhas))
    return mensagem


def verificar_envio_semanal(agora=None):
    agora = agora or datetime.now()
    reserva = _preparar_envio(agora)
    if reserva is None:
        return False

    semana, token, itens = reserva
    try:
        remetente = os.environ.get("GMAIL_REMETENTE")
        senha = os.environ.get("GMAIL_SENHA_APP")
        destinatario = os.environ.get("EMAIL_ESTOQUE_SEMANAL")
        if not remetente or not senha or not destinatario:
            raise ValueError("Configure GMAIL_REMETENTE, GMAIL_SENHA_APP e EMAIL_ESTOQUE_SEMANAL.")
        mensagem = _mensagem(itens, remetente, destinatario)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORTA, timeout=SMTP_TIMEOUT_ESTOQUE) as servidor:
            servidor.starttls()
            servidor.login(remetente, senha)
            servidor.send_message(mensagem)
    except (OSError, smtplib.SMTPException, ValueError):
        with closing(conectar()) as conexao, conexao:
            conexao.execute(
                "DELETE FROM envios_estoque_semanal WHERE semana = ? AND token = ? AND enviado_em IS NULL",
                (semana, token),
            )
        raise

    with closing(conectar()) as conexao, conexao:
        resultado = conexao.execute(
            "UPDATE envios_estoque_semanal SET enviado_em = ? WHERE semana = ? AND token = ?",
            (datetime.now().isoformat(), semana, token),
        )
        if resultado.rowcount != 1:
            raise RuntimeError("Não foi possível registrar o envio semanal de estoque.")
    logger.info("Resumo semanal de estoque enviado.")
    return True


def _executar_agendador():
    while True:
        try:
            verificar_envio_semanal()
        except (OSError, smtplib.SMTPException, sqlite3.Error, ValueError, RuntimeError):
            logger.exception("Falha ao enviar o resumo semanal de estoque; nova tentativa em 5 minutos.")
            sleep(300)
        else:
            sleep(60)


def iniciar_agendador_estoque():
    Thread(target=_executar_agendador, daemon=True, name="email-estoque-semanal").start()
