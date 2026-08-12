# A API do sistema financeiro — o "sistema de terceiro" do cenário.
#
# Ela vive num container próprio de propósito: no mundo real, o financeiro é de
# outro fornecedor, roda em outro servidor e o projeto de dados só conhece a URL
# e a chave. Manter essa fronteira física evita a armadilha silenciosa de o
# pipeline "espiar" o banco do financeiro em vez de consumir a API — algo que
# funcionaria na máquina do analista e quebraria no cliente.
FROM python:3.12-slim

# Rodar como usuário sem privilégio: se a aplicação for comprometida, o atacante
# não herda root dentro do container.
RUN useradd --create-home --shell /bin/bash financeiro
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# As dependências entram antes do código: assim o cache do Docker só é invalidado
# quando o pyproject muda, e não a cada edição de arquivo.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
RUN uv sync --frozen --no-dev && chown -R financeiro:financeiro /app

USER financeiro
EXPOSE 8100

# A sonda diz ao Docker se o serviço está de pé de verdade, não apenas se o
# processo existe.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8100/saude')"

CMD ["uv", "run", "uvicorn", "logistica_otif_mlops.api_custos.main:app", \
     "--host", "0.0.0.0", "--port", "8100"]
