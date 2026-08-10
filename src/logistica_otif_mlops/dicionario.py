"""Gera o dicionário de dados a partir do banco (estrutura) + glossário curado.

Por que gerar em vez de escrever à mão: um dicionário escrito à mão nasce
desatualizado no primeiro `alter table`. Aqui a **estrutura** (tabelas, tipos,
chaves, nulidade) sai do próprio banco, e só a **semântica** (o que a coluna
significa no negócio) é curada neste arquivo. Rodar de novo depois de uma
migration produz o documento correto.

Rodar: uv run python -m logistica_otif_mlops.dicionario > docs/04_dicionario_de_dados.md
"""

from __future__ import annotations

from typing import Any

import psycopg

from logistica_otif_mlops.config import obter_settings, url_libpq

# --- semântica: o que o nome da coluna não conta -----------------------------
TABELAS: dict[str, str] = {
    "operacao.organizacao": "Party pattern: cliente, base parceira e a própria matriz "
        "vivem na mesma tabela, distinguidos por `tipo_parceria`.",
    "operacao.endereco": "Ponto no mapa de qualquer organização. Para destinatário, "
        "guarda também o nome do local e o documento (a NF é emitida contra ele).",
    "operacao.item": "Catálogo por cliente (SKU). O material é do cliente; a "
        "TransBrasil apenas guarda e movimenta.",
    "operacao.local_estoque": "Galpão da matriz ou depósito de base. É onde a coleta "
        "física acontece, e a divisão por local gera as ordens de coleta.",
    "operacao.transportador": "Frota própria, transportadora, agregado ou carreteiro.",
    "operacao.veiculo": "Veículo com placa e tipo. Embarque aéreo não tem veículo.",
    "operacao.rota": "Agrupamento comercial de destinos (por UF/região).",
    "operacao.modalidade": "Modal do transporte: rodoviário ou aéreo.",
    "operacao.lead_time": "Régua de prazo prometido por modalidade × UF × cidade. "
        "É referência, não medição.",
    "operacao.campanha": "Calendário comercial (Páscoa, Mães, Black Friday, Natal). "
        "É a alavanca da sazonalidade e o momento em que a operação estoura.",
    "operacao.fase": "As dez etapas do ciclo de vida do pedido (EA → CE).",
    "operacao.sla_fase": "Meta e limite interno de duração de cada fase, em horas.",
    "operacao.tipo_ocorrencia": "Catálogo de eventos anormais (avaria, ausência, "
        "divergência). `fl_impacta_prazo` diz se conta contra o SLA.",
    "operacao.pedido": "O pedido de expedição (a 'SS'). Grão central do domínio.",
    "operacao.pedido_item": "Linha do pedido. `quantidade` conta VOLUMES (caixas), "
        "que é como o galpão e o painel contam.",
    "operacao.pedido_fase": "Formato LONGO: um registro por passagem de fase. A visão "
        "em colunas é derivação, nunca armazenamento.",
    "operacao.ordem_coleta": "A divisão da coleta por local de estoque (o 'DOC'). "
        "Cada local fecha no seu ritmo, e o mais lento define o fim da coleta.",
    "operacao.minuta": "O embarque: consolida pedidos de vários clientes num veículo. "
        "`tipo_carga` distingue carga consolidada de veículo dedicado.",
    "operacao.entrega": "Uma perna do trajeto (direta, transferência para base ou "
        "última milha). Um pedido pode ter várias.",
    "operacao.ocorrencia": "Evento anormal registrado no pedido ou na entrega.",
    "operacao.retirada_base": "Quando o cliente retira o material no galpão ou na base.",
    "operacao.recebimento": "Entrada de material do cliente no galpão (o abastecimento).",
    "operacao.estoque_snapshot": "Foto mensal do saldo por item × local. É a base da "
        "cobrança de armazenagem e do cálculo de aging.",
    "operacao.coleta": "Ordem de serviço reversa: buscar material fora (descarte ou "
        "retorno ao estoque).",
    "operacao.positivacao": "Ordem de serviço de montagem do material no ponto de venda "
        "ou evento, executada por parceiro local.",
    "custos.categoria_custo": "Classificação do custo variável.",
    "custos.faturamento_operacao": "Receita por operação/competência (o que se cobra).",
    "custos.custo_operacao": "Custo variável por operação/competência (o que se paga).",
    "custos.tarifa_armazenagem": "Régua de cobrança de armazenagem por cliente.",
    "custos.parametro_financeiro": "Parâmetros de negócio (impostos, cubagem, aging, "
        "custo de servir). Quem calcula MC LÊ daqui, não repete o número.",
}

COLUNAS: dict[str, str] = {
    "operacao.organizacao.sigla": "Código de 3 letras. Chave de negócio usada pelo "
        "financeiro (que não tem FK para cá).",
    "operacao.organizacao.tipo_parceria": "CLIENTE, BASE ou MATRIZ.",
    "operacao.organizacao.otif_contratual": "Percentual de pontualidade acordado em "
        "contrato. Abaixo dele, cabe multa.",
    "operacao.organizacao.dt_cancelamento": "Fim da vigência. Depois desta data o "
        "cliente não pode ter pedido (regra conferida na validação global).",
    "operacao.pedido.numero": "A 'SS'. Chave de NEGÓCIO (texto, com zeros à esquerda): "
        "é por ela que o financeiro reconcilia. Nunca use o `id` para isso.",
    "operacao.pedido.canal": "GRADE (rotina programada) ou WEB (avulso).",
    "operacao.pedido.nivel_servico": "PADRAO ou EXCLUSIVO (veículo dedicado, ~3× o "
        "preço, fura a fila).",
    "operacao.pedido.tipo_atendimento": "ENTREGA_DIRETA, ENTREGA_VIA_BASE ou "
        "RETIRA_BASE. **Define qual marco mede o cumprimento do prazo.**",
    "operacao.pedido.dt_prazo_saida_expedicao": "Prazo INTERNO: até quando a esteira "
        "deve liberar. Responsabilidade da produção.",
    "operacao.pedido.dt_prazo_entrega": "Prazo prometido ao CLIENTE. É contra ele que "
        "se mede o OTIF.",
    "operacao.pedido.nf_numero": "Só existe depois da fase EN. Preenchê-lo antes seria "
        "vazamento de futuro em qualquer modelo preditivo.",
    "operacao.pedido.peso_real_kg": "Aferido na balança. Nulo quando não se pesou "
        "(~3% dos casos): use o teórico como alternativa, sinalizando a troca.",
    "operacao.pedido_fase.dt_saida": "NULO = fase em andamento. É assim que se "
        "identifica a carteira em voo.",
    "operacao.entrega.tipo_perna": "DIRETA, TRANSFERENCIA_BASE ou ULTIMA_MILHA_BASE.",
    "operacao.entrega.dt_entrada_base": "Quando a base EFETIVOU a entrada. A diferença "
        "para `dt_chegada` é responsabilidade da base (cabe repasse de multa).",
    "operacao.entrega.fl_sucesso": "Tri-estado: NULO = em trânsito (desfecho "
        "desconhecido), true = entregue, false = tentativa falhou.",
    "operacao.entrega.fl_canhoto": "Comprovante recebido. Sem ele, a cobrança fica "
        "exposta a contestação.",
    "operacao.estoque_snapshot.m3_ocupado": "Espaço ocupado na foto. Multiplicado pela "
        "tarifa e pelo fator de aging, vira a cobrança do mês.",
    "operacao.estoque_snapshot.valor_danificado": "Parcela avariada, para provisão.",
    "operacao.recebimento.dt_validade": "Vencimento do lote. Saldo com validade "
        "expirada é estoque perdido, e o cliente costuma descobrir tarde.",
    "custos.faturamento_operacao.referencia_numero": "SS ou OS. NULO na ARMAZENAGEM, "
        "que fatura por competência e não por operação.",
    "custos.faturamento_operacao.valor_com_icms": "Receita da linha. **Pode ser "
        "negativo** (estorno de nota cancelada): some com o sinal, nunca com abs().",
    "custos.custo_operacao.prestador_nome": "Texto livre: é sistema de terceiro e não "
        "há FK para o cadastro de transportadores.",
    "custos.custo_operacao.dt_competencia": "Competência do custo. Pode ser POSTERIOR à "
        "da receita (nota que chega atrasada): reconcilie pela operação, não pelo mês.",
}

CABECALHO = """<a id="topo"></a>

# Dicionário de Dados

<!-- nav:start -->
[← Documentação](README.md) | [Entendimento dos Dados](02_entendimento_dos_dados.md)
| [Acesso aos dados](03_acesso_aos_dados.md)
<!-- nav:end -->

> Referência de consulta das {n_tabelas} tabelas das duas fontes. **Gerado a partir do
> banco** por `uv run python -m logistica_otif_mlops.dicionario`: a estrutura vem do
> `information_schema` e a semântica de um glossário curado no próprio script, então
> uma migration nova nunca deixa este documento mentindo.
>
> Legenda: 🔑 chave primária · 🔗 chave estrangeira · `NOT NULL` obrigatório.
"""


def gerar() -> str:
    cfg = obter_settings()
    if not cfg.database_url:
        raise SystemExit("DATABASE_URL não configurada")
    linhas: list[str] = []
    with psycopg.connect(url_libpq(cfg.database_url)) as conn, conn.cursor() as cur:
        tabelas = _listar_tabelas(cur)
        linhas.append(CABECALHO.format(n_tabelas=len(tabelas)))
        for esquema in ("operacao", "custos"):
            titulo = ("Sistema Operacional (TBW)" if esquema == "operacao"
                      else "Sistema Financeiro (terceiro, via API)")
            linhas.append(f"\n## Schema `{esquema}` · {titulo}\n")
            for tabela in [t for t in tabelas if t.startswith(f"{esquema}.")]:
                linhas.extend(_secao_tabela(cur, tabela))
    linhas.append("\n---\n\n[Início](#topo)\n")
    return "\n".join(linhas)


def _listar_tabelas(cur: psycopg.Cursor[Any]) -> list[str]:
    cur.execute("""
        select table_schema || '.' || table_name
        from information_schema.tables
        where table_schema in ('operacao', 'custos') and table_type = 'BASE TABLE'
        order by table_schema, table_name""")
    return [linha[0] for linha in cur.fetchall()]


def _secao_tabela(cur: psycopg.Cursor[Any], tabela: str) -> list[str]:
    esquema, nome = tabela.split(".")
    cur.execute("select count(*) from " + tabela)  # noqa: S608 (nome vem do catálogo)
    linha = cur.fetchone()
    total = linha[0] if linha else 0

    cur.execute("""
        select c.column_name, c.data_type, c.character_maximum_length,
               c.numeric_precision, c.numeric_scale, c.is_nullable,
               exists (select 1 from information_schema.key_column_usage k
                       join information_schema.table_constraints t
                         on t.constraint_name = k.constraint_name
                       where t.constraint_type = 'PRIMARY KEY'
                         and k.table_schema = c.table_schema
                         and k.table_name = c.table_name
                         and k.column_name = c.column_name) as pk,
               (select ccu.table_schema || '.' || ccu.table_name
                from information_schema.key_column_usage k
                join information_schema.table_constraints t
                  on t.constraint_name = k.constraint_name
                join information_schema.constraint_column_usage ccu
                  on ccu.constraint_name = t.constraint_name
                where t.constraint_type = 'FOREIGN KEY'
                  and k.table_schema = c.table_schema
                  and k.table_name = c.table_name
                  and k.column_name = c.column_name limit 1) as fk
        from information_schema.columns c
        where c.table_schema = %s and c.table_name = %s
        order by c.ordinal_position""", (esquema, nome))

    out = [f"\n### `{tabela}`  ·  {total:,} linhas".replace(",", ".")]
    descricao = TABELAS.get(tabela)
    if descricao:
        out.append(f"\n{descricao}\n")
    out.append("| Coluna | Tipo | Obrig. | Significado |")
    out.append("|---|---|---|---|")
    for col, tipo, tam, prec, escala, nulo, pk, fk in cur.fetchall():
        marca = "🔑 " if pk else ("🔗 " if fk else "")
        out.append(
            f"| {marca}`{col}` | {_tipo(tipo, tam, prec, escala)} "
            f"| {'sim' if nulo == 'NO' else '—'} "
            f"| {COLUNAS.get(f'{tabela}.{col}', _padrao(col, fk))} |")
    return out


def _tipo(tipo: str, tam: int | None, prec: int | None, escala: int | None) -> str:
    abreviado = {"character varying": "texto", "timestamp without time zone": "data/hora",
                 "date": "data", "boolean": "sim/não", "bigint": "inteiro",
                 "integer": "inteiro", "numeric": "decimal"}.get(tipo, tipo)
    if tam:
        return f"{abreviado}({tam})"
    if tipo == "numeric" and prec:
        return f"{abreviado}({prec},{escala})"
    return abreviado


def _padrao(coluna: str, fk: str | None) -> str:
    if fk:
        return f"Referencia `{fk}`."
    if coluna == "id":
        return "Chave técnica (sequencial). Não use como chave de negócio."
    if coluna.startswith("dt_"):
        return "Data/hora do evento."
    if coluna.startswith("fl_"):
        return "Indicador."
    return ""


if __name__ == "__main__":
    print(gerar())
