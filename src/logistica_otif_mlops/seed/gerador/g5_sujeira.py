"""G5: a sujeira final — o mundo limpo demais vira o mundo real.

As fatias anteriores geram um mundo coerente. Sistema de verdade não é assim:
tem nome digitado de três jeitos, telefone em formato livre, documento com e sem
máscara, recebedor em CAIXA ALTA, estorno lançado como valor negativo, cadastro
duplicado, data preenchida no dedo. Esta fatia passa por cima do mundo pronto e
suja de propósito, **sem quebrar a integridade referencial**: tudo que se altera
aqui é texto, formato ou lançamento, nunca a chave.

Cada bagunça é catalogada em `.contexto/referencias/catalogo_sujeira.md`, que é o
gabarito da etapa de qualidade (o Discovery precisa ACHAR, não receber pronto).

Rodar: uv run python -m logistica_otif_mlops.seed.gerador.g5_sujeira
"""

from __future__ import annotations

import random
import unicodedata
from typing import Any

from logistica_otif_mlops.db import criar_engine

SEMENTE = 20260805

PCT_NOME_BAGUNCADO = 0.12      # nome do recebedor em caixa alta / com espaço extra
PCT_SEM_ACENTO = 0.08          # sistema legado que comeu os acentos
PCT_LOGRADOURO_ABREVIADO = 0.30  # "Rua" ou "R."? cada cadastro tem sua escola
PCT_DOC_SEM_MASCARA = 0.35     # CNPJ com e sem pontuação
ABREVIACOES = [("Rua ", "R. "), ("Avenida ", "Av. "), ("Rodovia ", "Rod. "),
               ("Travessa ", "Tv. "), ("Estrada ", "Est. "), ("Praça ", "Pç. ")]
PCT_ESTORNO = 0.004            # lançamento negativo (estorno de nota)
PCT_OBSERVACAO_RUIDO = 0.05    # texto livre com lixo de digitação
RUIDOS = ["  ", " -", " ...", " ??", " (verificar)", " sem informacao", " N/A"]


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def executar() -> None:
    engine = criar_engine()
    raw = engine.raw_connection()
    cur = raw.cursor()
    cur.execute("select count(*) from operacao.entrega where recebedor = upper(recebedor)"
                " and recebedor is not null")
    linha = cur.fetchone()
    assert linha is not None
    if linha[0] > 1000:
        print("g5: sujeira já aplicada; nada a fazer.")
        return

    rng = random.Random(SEMENTE)
    total = 0
    total += _nomes_de_recebedor(cur, rng)
    total += _documentos_e_logradouros(cur, rng)
    total += _acentuacao_perdida(cur, rng)
    total += _estornos(cur, rng)
    total += _observacoes_com_ruido(cur, rng)
    raw.commit()
    print(f"G5 OK: {total} registros sujados de propósito")
    cur.close()
    raw.close()


def _nomes_de_recebedor(cur: Any, rng: random.Random) -> int:
    """Quem assina o canhoto digita como quer: CAIXA ALTA, espaço sobrando, só o 1º nome."""
    cur.execute("select id, recebedor from operacao.entrega"
                " where recebedor is not null and fl_sucesso")
    alteracoes = []
    for eid, nome in cur.fetchall():
        if rng.random() >= PCT_NOME_BAGUNCADO:
            continue
        sorteio = rng.random()
        if sorteio < 0.45:
            novo = nome.upper()
        elif sorteio < 0.7:
            novo = f"  {nome} "
        elif sorteio < 0.85:
            novo = nome.lower()
        else:
            novo = f"{nome} {rng.choice(['Silva', 'Souza', 'Santos'])}".upper()
        alteracoes.append((novo[:60], eid))
    cur.executemany("update operacao.entrega set recebedor = %s where id = %s", alteracoes)
    return len(alteracoes)


def _documentos_e_logradouros(cur: Any, rng: random.Random) -> int:
    """CNPJ com e sem máscara, logradouro abreviado: a bagunça de cadastro."""
    cur.execute("select id, documento, logradouro from operacao.endereco")
    alteracoes = []
    for eid, documento, logradouro in cur.fetchall():
        novo_doc, novo_log = documento, logradouro
        if documento and rng.random() < PCT_DOC_SEM_MASCARA:
            digitos = "".join(c for c in documento if c.isdigit())
            novo_doc = digitos if rng.random() < 0.7 else f"{digitos} "
        if logradouro and rng.random() < PCT_LOGRADOURO_ABREVIADO:
            for inteiro, abreviado in ABREVIACOES:
                if logradouro.startswith(inteiro):
                    novo_log = abreviado + logradouro[len(inteiro):]
                    break
            else:
                novo_log = logradouro.upper()
        if (novo_doc, novo_log) != (documento, logradouro):
            alteracoes.append((novo_doc[:20] if novo_doc else None,
                               novo_log[:150] if novo_log else None, eid))
    cur.executemany(
        "update operacao.endereco set documento = %s, logradouro = %s where id = %s",
        alteracoes)
    return len(alteracoes)


def _acentuacao_perdida(cur: Any, rng: random.Random) -> int:
    """Parte do cadastro passou por um sistema que comeu os acentos."""
    alteracoes_end = []
    cur.execute("select id, cidade, nome_local from operacao.endereco")
    for eid, cidade, nome_local in cur.fetchall():
        if rng.random() >= PCT_SEM_ACENTO:
            continue
        alteracoes_end.append((_sem_acento(cidade),
                               _sem_acento(nome_local) if nome_local else None, eid))
    cur.executemany(
        "update operacao.endereco set cidade = %s, nome_local = %s where id = %s",
        alteracoes_end)

    alteracoes_item = []
    cur.execute("select id, descricao from operacao.item")
    for iid, descricao in cur.fetchall():
        if rng.random() < PCT_SEM_ACENTO:
            alteracoes_item.append((_sem_acento(descricao), iid))
    cur.executemany("update operacao.item set descricao = %s where id = %s", alteracoes_item)
    return len(alteracoes_end) + len(alteracoes_item)


def _estornos(cur: Any, rng: random.Random) -> int:
    """Nota cancelada vira lançamento negativo na competência seguinte.

    O total do cliente continua certo; quem somar sem olhar o sinal se engana.
    """
    cur.execute("""
        select id, cliente_sigla, referencia_numero, tipo_operacao, competencia,
               valor_com_icms, valor_icms, dt_faturamento
        from custos.faturamento_operacao
        where tipo_operacao = 'TRANSPORTE' and competencia >= '2023-01'
        order by id""")
    novos = []
    for _fid, sigla, ref, tipo, comp, valor, icms, dt in cur.fetchall():
        if rng.random() >= PCT_ESTORNO:
            continue
        ano, mes = int(comp[:4]), int(comp[5:])
        prox = f"{ano + (mes == 12):04d}-{(mes % 12) + 1:02d}"
        novos.append((sigla, ref, tipo, prox, -valor, -icms, dt))
    cur.executemany(
        "insert into custos.faturamento_operacao (cliente_sigla, referencia_numero,"
        " tipo_operacao, competencia, valor_com_icms, valor_icms, dt_faturamento)"
        " values (%s, %s, %s, %s, %s, %s, %s)", novos)
    return len(novos)


def _observacoes_com_ruido(cur: Any, rng: random.Random) -> int:
    """Texto livre é onde o operador desabafa: ruído, abreviação, campo vazio."""
    cur.execute("select id, observacao from operacao.ocorrencia where observacao is not null")
    alteracoes = []
    for oid, observacao in cur.fetchall():
        if rng.random() >= PCT_OBSERVACAO_RUIDO:
            continue
        sorteio = rng.random()
        if sorteio < 0.4:
            novo = observacao + rng.choice(RUIDOS)
        elif sorteio < 0.7:
            novo = observacao.upper()
        else:
            novo = rng.choice(RUIDOS).strip() or "-"
        alteracoes.append((novo[:200], oid))
    cur.executemany("update operacao.ocorrencia set observacao = %s where id = %s", alteracoes)
    return len(alteracoes)


if __name__ == "__main__":
    executar()
