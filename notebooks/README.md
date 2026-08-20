# notebooks/ — o laboratório da análise

Notebook é onde o dado é **interrogado** e onde a conclusão fica registrada **ao
lado da evidência que a sustenta**. É o laudo do exame: o achado e a imagem que o
comprova, no mesmo lugar. Quem abrir daqui a seis meses precisa entender não só o
que foi concluído, mas por quê.

O que **não** é: lugar de código de produção. Assim que uma transformação vira
rotina, ela sai do notebook e vira módulo em `src/`, com teste. O notebook então
passa a chamar o módulo. Regra prática: se roda mais de uma vez, sai do notebook.

## Organização

```
notebooks/
├── operacional/    # domínio 1 (vai primeiro: abre o trilho)
└── financeiro/     # domínio 2 (reaproveita o caminho já aberto)
```

Nomeie na ordem em que devem ser lidos: `00_eda_qualidade`, `01_eda_descritiva`,
`02_eda_inferencial`, `03_features`. A numeração conta a história do projeto.

### operacional/

| Notebook | O que estabelece |
|---|---|
| `00_eda_qualidade_dados_ope.ipynb` | o diagnóstico: 7 achados de qualidade no Bronze, com severidade e ação |
| `01_validacao_silver_ope.ipynb` | a prestação de contas: o que o Silver fez com cada célula que tocou, e o que fez com as que não devia tocar |

O par não é opcional. O primeiro diz o que precisa ser corrigido; o segundo prova
que a correção fez isso e **só** isso. Limpeza sem prestação de contas é o ponto
onde um projeto de dados mais facilmente perde a confiança do cliente, porque é
onde se mexe no dado dele sem que ele veja.

## Acesso a dados: sempre pelo conector

```python
from logistica_otif_mlops.connectors.registry import obter

df = obter("operacao_db").ler("select * from operacao.pedido limit 1000")
```

Nunca escreva credencial, host ou caminho de arquivo dentro do notebook. A mesma
análise precisa rodar na máquina de qualquer pessoa que tenha o `.env`
preenchido, sem editar uma linha — e o notebook vai para um repositório público.

## Higiene antes de commitar

- **Limpe as saídas** de células que imprimam dado sensível ou volumoso.
- **Rode do começo ao fim** antes de fechar: notebook que só funciona na ordem em
  que você foi executando não é reprodutível, é um bilhete para si mesmo.
- **Escreva as conclusões em markdown**, não em comentário de código. O leitor do
  relatório não lê `#`.
