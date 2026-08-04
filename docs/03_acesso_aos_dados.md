<a id="topo"></a>

# Acesso aos dados: banco e API

<!-- nav:start -->
[← Documentação](README.md) | [Entendimento do negócio](01_entendimento_do_negocio.md) | [Entendimento dos dados](02_entendimento_dos_dados.md)
<!-- nav:end -->

> Como conectar nas duas fontes da TransBrasil: o **banco relacional** (operação) e a **API financeira** (custos). Serve para quem vai explorar em SQL, para quem vai plugar um BI e para quem vai consumir pelo pipeline.

## 1. As duas fontes, e por que são duas

| Fonte | O que tem | Como se acessa |
|---|---|---|
| **Banco relacional** | operação: pedidos, fases, entregas, estoque, cadastro | SQL direto (DBeaver, psql, pandas) |
| **API financeira** | faturamento, custos, parâmetros, tarifas | HTTP com chave no cabeçalho |

Não é capricho de arquitetura: é o cenário real da empresa. O ERP operacional é da casa, o financeiro é de outro fornecedor e só entrega dados por API. Um pipeline que assume "está tudo num banco só" quebra no primeiro cliente de verdade. Por isso o projeto trata as duas como **conectores** intercambiáveis: quem consome pede um DataFrame e não sabe de onde veio.

## 2. Ambientes

| Ambiente | Onde | Período | Para que |
|---|---|---|---|
| **dev** | Postgres local (Docker) | 2016 a 2026 (completo) | treino de modelo, validação out-of-time, EDA |
| **hmlg** | Neon (nuvem) | últimos 9 meses | estudo de SQL, demonstração, API publicada |

O recorte da nuvem existe porque o mundo completo tem 5,3 GB e o plano gratuito do Neon oferece 512 MB. Os **dados de referência vão inteiros** (carteira, catálogo, rede, réguas): a estrutura e os joins são idênticos, só há menos movimento.

## 3. Conectando no banco (DBeaver)

1. **Nova conexão** → PostgreSQL.
2. Preencha com os dados da connection string que você recebeu (host, porta 5432, banco, usuário, senha).
3. Aba **Driver properties**: `sslmode` = `require`. A nuvem recusa conexão sem TLS, e é assim que tem de ser: senha trafegando em texto claro é senha entregue.
4. Teste a conexão e finalize.

Para começar a explorar:

```sql
-- o mapa: o que existe e quanto tem
select table_schema, table_name
from information_schema.tables
where table_schema in ('operacao', 'custos')
order by 1, 2;

-- os dez maiores clientes por volume de pedidos
select o.sigla, o.nome_fantasia, count(*) as pedidos
from operacao.pedido p
join operacao.organizacao o on o.id = p.cliente_id
group by 1, 2
order by 3 desc
limit 10;
```

**Sua área de exercícios** é o schema `rascunho`: ali você cria views e tabelas à vontade. Nos schemas `operacao` e `custos` o acesso é somente leitura, então nenhum comando seu consegue estragar a base — pode testar sem medo, inclusive os erros.

```sql
create table rascunho.meu_teste as
select cliente_sigla, competencia, sum(valor_com_icms) as receita
from custos.faturamento_operacao
group by 1, 2;
```

## 4. Conectando na API financeira

A API exige a chave no cabeçalho `X-API-Key`. Sem ela, responde `401`.

```bash
curl -H "X-API-Key: SUA_CHAVE" \
  "https://SEU-SERVICO.onrender.com/v1/faturamentos?competencia=2026-06&limite=5"
```

Documentação interativa (Swagger): `https://SEU-SERVICO.onrender.com/docs`

### Endpoints

| Endpoint | O que devolve | Filtros |
|---|---|---|
| `GET /saude` | status do serviço (sem chave) | — |
| `GET /v1/faturamentos` | receita por operação | `cliente_sigla`, `tipo_operacao`, `competencia`, `competencia_de`, `competencia_ate` |
| `GET /v1/custos` | custo variável por operação | `cliente_sigla`, `categoria`, `competencia`, `competencia_de`, `competencia_ate` |
| `GET /v1/parametros` | parâmetros de negócio | — |
| `GET /v1/tarifas-armazenagem` | régua de cobrança por cliente | `cliente_sigla` |

As listagens são **paginadas**: `limite` (máximo 1000) e `deslocamento`. A resposta traz `total`, então dá para saber quantas páginas faltam:

```json
{ "total": 13043, "limite": 100, "deslocamento": 0, "itens": [ ... ] }
```

### Power BI

1. **Obter dados** → **Web** → **Avançado**.
2. Em *Partes da URL*, cole o endereço completo com os filtros.
3. Em *Cabeçalhos de solicitação HTTP*, adicione: nome `X-API-Key`, valor a sua chave.
4. O Power BI abre o JSON; converta `itens` em tabela e expanda as colunas.

Para trazer mais de uma página, monte uma função que receba o `deslocamento` e invoque em lista até somar o `total`. É o exercício que separa quem "puxa uma tabela" de quem **integra uma fonte**.

> **Nunca** deixe a chave escrita dentro de uma consulta compartilhada, de um repositório ou de um print. No Power BI Service, use as credenciais do dataset; no Desktop, parâmetro. Chave que aparece numa tela é chave que precisa ser trocada.

### Python

```python
import httpx
import pandas as pd

resposta = httpx.get(
    "https://SEU-SERVICO.onrender.com/v1/custos",
    params={"competencia": "2026-06", "limite": 500},
    headers={"X-API-Key": os.environ["CUSTOS_API_KEY"]},  # do ambiente, não do código
    timeout=30,
)
resposta.raise_for_status()
df = pd.DataFrame(resposta.json()["itens"])
```

## 5. Segurança, em uma tela

O que este projeto faz, e por quê:

- **Toda credencial vem do ambiente** (`.env` local, variáveis no provedor), nunca do código. O repositório é público: o que estiver nele, está publicado.
- **Menor privilégio**: quem estuda recebe `SELECT` e uma área própria; quem serve a API lê um banco somente leitura. Ninguém opera com o usuário dono.
- **A chave é comparada em tempo constante** (`compare_digest`). Comparação comum retorna mais rápido quando os primeiros caracteres diferem, e essa diferença permite descobrir a chave por medição.
- **Falha fechada**: sem chave configurada, a API se recusa a servir em vez de liberar. Erro de configuração não vira porta aberta.
- **TLS obrigatório** na nuvem (`sslmode=require`).
- **Dados 100% sintéticos**: nenhuma informação de cliente real, em nenhum ambiente.

---

[Início](#topo)
