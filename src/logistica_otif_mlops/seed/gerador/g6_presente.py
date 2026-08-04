"""G6: o corte do presente — o mundo deixa de ser história e vira sistema vivo.

As fatias anteriores geram o passado inteiro, com todo pedido concluído. Um ERP
consultado agora nunca é assim: existe uma **carteira em voo**, com pedidos
parados na fase corrente (`dt_saida` nula), carga na estrada sem canhoto, coleta
agendada e não executada, nota a emitir.

Isso não é enfeite. É onde o modelo vai operar: ele pontua pedido que ainda não
foi entregue. Sem esta fatia, a base não tem um único caso de inferência real, e
qualquer pipeline treinado nela quebraria no primeiro dia de produção — quando
receber, pela primeira vez, uma linha sem desfecho.

O corte é uma **decisão de calendário**: tudo que aconteceria depois de
`DATA_CORTE` simplesmente ainda não aconteceu. Nada é inventado; o futuro é
removido, e o que estava em andamento fica em andamento.

Rodar: uv run python -m logistica_otif_mlops.seed.gerador.g6_presente
       uv run python -m logistica_otif_mlops.seed.gerador.g6_presente --em 2026-07-28
"""

from __future__ import annotations

import argparse
from datetime import date
from typing import Any

import psycopg

from logistica_otif_mlops.config import obter_settings, url_libpq

# "hoje" do sistema: o último dia em que a operação registrou movimento
DATA_CORTE = date(2026, 7, 28)


def executar(corte: date) -> None:
    cfg = obter_settings()
    if not cfg.database_url:
        raise SystemExit("DATABASE_URL não configurada")
    print(f"cortando o presente em {corte:%d/%m/%Y}\n")
    with psycopg.connect(url_libpq(cfg.database_url)) as conn:
        with conn.cursor() as cur:
            _fases(cur, corte)
            _entregas(cur, corte)
            _servicos_pendentes(cur, corte)
            _financeiro(cur, corte)
            _estoque(cur, corte)
            _expurgar_pos_cancelamento(cur)
            _coerencia_documental(cur)
            _vincular_campanhas(cur)
        conn.commit()
        with conn.cursor() as cur:
            _relatorio(cur)


def _fases(cur: psycopg.Cursor[Any], corte: date) -> None:
    """O que ainda não começou some; o que estava em curso fica em aberto."""
    cur.execute("delete from operacao.pedido_fase where dt_entrada > %s", (corte,))
    print(f"  fases que ainda não começaram, removidas: {cur.rowcount:,}")
    cur.execute(
        "update operacao.pedido_fase set dt_saida = null"
        " where dt_entrada <= %s and dt_saida > %s", (corte, corte))
    print(f"  fases em andamento (dt_saida nula):       {cur.rowcount:,}")


def _entregas(cur: psycopg.Cursor[Any], corte: date) -> None:
    """Carga na estrada: embarcou, ainda não chegou.

    A entrega **permanece** (com desfecho nulo) porque é ela que liga o pedido à
    minuta em que viajou. Apagá-la faria o pedido em trânsito perder o embarque,
    e junto a feature de consolidação que o modelo vai usar.
    """
    cur.execute(
        "delete from operacao.ocorrencia where dt_ocorrencia > %s", (corte,))
    print(f"  ocorrências futuras, removidas:           {cur.rowcount:,}")
    cur.execute("delete from operacao.retirada_base where dt_retirada > %s", (corte,))
    print(f"  retiradas ainda não feitas, removidas:    {cur.rowcount:,}")

    # embarque que ainda não saiu não existe, e a entrega dele tampouco: as duas
    # somem juntas (a ocorrência ligada a essas entregas sai antes, pela FK)
    cur.execute(
        "delete from operacao.ocorrencia o using operacao.entrega e, operacao.minuta m"
        " where o.entrega_id = e.id and e.minuta_id = m.id and m.dt_expedicao > %s",
        (corte,))
    cur.execute(
        "delete from operacao.entrega e using operacao.minuta m"
        " where e.minuta_id = m.id and m.dt_expedicao > %s", (corte,))
    print(f"  entregas de embarque não saído, removidas:{cur.rowcount:,}")
    cur.execute("delete from operacao.minuta where dt_expedicao > %s", (corte,))
    print(f"  minutas ainda não expedidas, removidas:   {cur.rowcount:,}")

    # o que já embarcou mas não chegou fica sem desfecho: NULL é "em trânsito"
    cur.execute(
        "update operacao.entrega set dt_chegada = null, dt_entrada_base = null,"
        " recebedor = null, fl_canhoto = false, fl_sucesso = null"
        " where dt_chegada > %s", (corte,))
    print(f"  entregas em trânsito (sem desfecho):      {cur.rowcount:,}")
    cur.execute(
        "update operacao.entrega set dt_entrada_base = null"
        " where dt_entrada_base > %s", (corte,))
    print(f"  cargas na base aguardando entrada:        {cur.rowcount:,}")


def _servicos_pendentes(cur: psycopg.Cursor[Any], corte: date) -> None:
    """Coleta agendada e positivação aberta: a fila de serviço do dia."""
    cur.execute(
        "update operacao.coleta set dt_coleta = null, status = 'SOLICITADA'"
        " where dt_coleta > %s", (corte,))
    print(f"  coletas agendadas e não executadas:       {cur.rowcount:,}")
    cur.execute(
        "update operacao.positivacao set dt_servico = null, status = 'ABERTA'"
        " where dt_servico > %s", (corte,))
    print(f"  positivações abertas:                     {cur.rowcount:,}")


def _financeiro(cur: psycopg.Cursor[Any], corte: date) -> None:
    """Nota que ainda não foi emitida não existe no financeiro."""
    cur.execute(
        "delete from custos.faturamento_operacao where dt_faturamento > %s", (corte,))
    print(f"  faturamentos ainda não emitidos:          {cur.rowcount:,}")
    cur.execute(
        "delete from custos.custo_operacao where dt_competencia > %s", (corte,))
    print(f"  custos ainda não lançados:                {cur.rowcount:,}")


def _estoque(cur: psycopg.Cursor[Any], corte: date) -> None:
    """Foto de fechamento de mês que ainda não chegou."""
    cur.execute("delete from operacao.estoque_snapshot where data > %s", (corte,))
    print(f"  fotos de estoque futuras, removidas:      {cur.rowcount:,}")


def _expurgar_pos_cancelamento(cur: psycopg.Cursor[Any]) -> None:
    """Remove pedido feito depois de o cliente ter cancelado o contrato.

    Achado do Tiago explorando o banco: a G2 decidia quem estava ativo olhando
    o **mês** (referência no dia 15), então quem cancelava no dia 17 seguia
    recebendo pedidos até o fim do mês. A causa já está corrigida na origem
    (a vigência agora vale por dia); esta rede de segurança limpa o que ficou e
    protege contra qualquer regressão futura da mesma natureza.

    Cadastro que contradiz movimento é veneno para o modelo: a feature "cliente
    ativo" deixaria de significar o que diz.
    """
    cur.execute("""
        create temp table pedido_expurgo as
        select p.id, p.numero from operacao.pedido p
        join operacao.organizacao o on o.id = p.cliente_id
        where o.dt_cancelamento is not null
          and p.dt_solicitacao::date > o.dt_cancelamento""")
    cur.execute("select count(*) from pedido_expurgo")
    linha = cur.fetchone()
    total = linha[0] if linha else 0
    if not total:
        print("  pedidos após o cancelamento:              0")
        cur.execute("drop table pedido_expurgo")
        return

    for tabela in ("operacao.ocorrencia", "operacao.retirada_base", "operacao.entrega",
                   "operacao.ordem_coleta", "operacao.pedido_item",
                   "operacao.pedido_fase", "operacao.positivacao"):
        cur.execute(
            f"delete from {tabela} where pedido_id in (select id from pedido_expurgo)")
    for tabela in ("custos.faturamento_operacao", "custos.custo_operacao"):
        cur.execute(f"delete from {tabela}"
                    " where referencia_numero in (select numero from pedido_expurgo)")
    cur.execute("delete from operacao.pedido where id in (select id from pedido_expurgo)")
    print(f"  pedidos após o cancelamento, removidos:   {total:,}")
    cur.execute("""
        delete from operacao.minuta m
        where not exists (select 1 from operacao.entrega e where e.minuta_id = m.id)""")
    print(f"  minutas que ficaram sem carga, removidas: {cur.rowcount:,}")
    cur.execute("drop table pedido_expurgo")


def _coerencia_documental(cur: psycopg.Cursor[Any]) -> None:
    """A nota fiscal nasce na fase EN: antes dela, o campo tem de estar vazio.

    Isto é **anti-vazamento**, não estética. Se todo pedido em voo já tivesse
    número de NF, o modelo aprenderia que "ter NF" prevê entrega — quando na
    verdade ter NF significa que o pedido já andou quase até o fim. Em produção,
    a NF chega DEPOIS do instante da previsão, e o modelo desabaria.
    """
    cur.execute("""
        update operacao.pedido p set nf_numero = null
        where not exists (
            select 1 from operacao.pedido_fase pf
            join operacao.fase f on f.id = pf.fase_id and f.codigo = 'EN'
            where pf.pedido_id = p.id and pf.dt_saida is not null)""")
    print(f"  pedidos sem NF (ainda não emitida):       {cur.rowcount:,}")


def _vincular_campanhas(cur: psycopg.Cursor[Any]) -> None:
    """Liga o pedido à campanha vigente do segmento do cliente.

    O calendário comercial já movia os volumes (a sazonalidade está nos dados),
    mas o vínculo ficava implícito e `campanha_id` nascia nulo — uma feature
    forte jogada fora, já que campanha é justamente quando a operação estoura.
    """
    # espelha o BOOST_SEGMENTO da G2: o vínculo tem de contar a mesma história
    # que moveu os volumes, senão a feature contradiz a sazonalidade observada
    cur.execute("""
        update operacao.pedido p set campanha_id = c.id
        from operacao.campanha c, operacao.organizacao o
        where o.id = p.cliente_id
          and p.dt_solicitacao::date between c.dt_inicio and c.dt_fim
          and (
            (c.descricao like 'Páscoa%' and o.segmento = 'ALIMENTICIO') or
            (c.descricao like 'Dia das Mães%' and o.segmento in
                ('COSMETICOS_DERMATOLOGICOS', 'MODA_ACESSORIOS', 'JOALHERIA')) or
            (c.descricao like 'Dia dos Namorados%' and o.segmento = 'JOALHERIA') or
            (c.descricao like 'Black Friday%' and o.segmento = 'ELETRONICOS') or
            (c.descricao like 'Natal%' and o.segmento in
                ('ALIMENTICIO', 'COSMETICOS_DERMATOLOGICOS', 'MODA_ACESSORIOS',
                 'JOALHERIA', 'ELETRONICOS'))
          )""")
    print(f"  pedidos vinculados a campanha:            {cur.rowcount:,}")


def _relatorio(cur: psycopg.Cursor[Any]) -> None:
    cur.execute("""
        select f.codigo, f.nome, count(*) as pedidos
        from operacao.pedido_fase pf
        join operacao.fase f on f.id = pf.fase_id
        where pf.dt_saida is null
        group by 1, 2, f.ordem order by f.ordem""")
    linhas = cur.fetchall()
    total = sum(linha[2] for linha in linhas)
    print(f"\nCARTEIRA EM VOO: {total:,} pedidos parados na fase corrente")
    for codigo, nome, quantidade in linhas:
        print(f"  {codigo}  {nome:<32} {quantidade:>6,}")
    cur.execute("select count(*) from operacao.entrega where fl_sucesso is null")
    linha = cur.fetchone()
    print(f"\n  entregas na estrada (desfecho nulo): {linha[0]:,}" if linha else "")


def principal() -> None:
    parser = argparse.ArgumentParser(description="Corta o presente do mundo gerado")
    parser.add_argument("--em", type=date.fromisoformat, default=DATA_CORTE,
                        help="data que passa a ser o 'hoje' do sistema (AAAA-MM-DD)")
    args = parser.parse_args()
    executar(args.em)


if __name__ == "__main__":
    principal()
