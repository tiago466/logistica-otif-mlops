# notebooks/ — exploração (consumidores finos do pacote)

Os notebooks servem para **explorar e comunicar** (EDA, Data Discovery, análises).
Eles são **consumidores finos**: importam o pacote `logistica_otif_mlops` e
chamam suas funções e conectores — **nunca** reimplementam regra de negócio nem
abrem caminho de arquivo/credencial direto.

Padrão de acesso a dados (sempre pelo conector, nunca pelo caminho cru):

```python
from logistica_otif_mlops.connectors import obter

df = obter("logistica_db").ler("SELECT * FROM pedidos LIMIT 1000")
```

Assim a mesma análise roda na máquina de qualquer pessoa que tenha o `.env`
preenchido — sem editar uma linha do notebook.
