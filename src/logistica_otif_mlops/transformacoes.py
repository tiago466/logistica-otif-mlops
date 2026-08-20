"""Regras de transformação do Silver, isoladas e testáveis.

Cada função aqui faz **uma** coisa, recebe e devolve valor simples, e não conhece
banco, arquivo nem DataFrame. Isso não é purismo: é o que permite testar cada
regra com meia dúzia de exemplos e provar que ela trata o caso difícil (o nome
com acento, o CEP com zero à esquerda, o campo que parece vazio mas tem espaço).

A regra que governa todas: **normalizar para comparar, preservar para exibir.**
O Silver corrige forma, nunca conteúdo. "sao paulo" vira "São Paulo" porque é a
mesma cidade escrita de outro jeito; um valor ausente continua ausente, porque
inventá-lo seria criar dado que ninguém coletou.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable

# Partículas que ficam em minúscula no meio de um nome próprio. Sem esta lista,
# "Rua das Flores" viraria "Rua Das Flores", que ninguém escreve.
PARTICULAS = {"de", "da", "do", "das", "dos", "e", "em", "a", "o", "as", "os",
              "para", "com", "no", "na", "nos", "nas", "ao", "aos", "à", "às"}

# Siglas que devem permanecer em caixa alta mesmo dentro de um nome.
SIGLAS = {"br", "sp", "rj", "mg", "rs", "sc", "pr", "ba", "pe", "ce", "go", "df",
          "ltda", "sa", "me", "epp", "cd", "pdv", "km"}

ABREVIACOES_LOGRADOURO = {
    "r.": "Rua", "r": "Rua", "av.": "Avenida", "av": "Avenida",
    "rod.": "Rodovia", "rod": "Rodovia", "tv.": "Travessa", "tv": "Travessa",
    "est.": "Estrada", "est": "Estrada", "pç.": "Praça", "pc.": "Praça",
    "pça.": "Praça", "al.": "Alameda", "trav.": "Travessa",
}


def sem_acento(texto: str) -> str:
    """Remove acentos, preservando as letras. Serve para COMPARAR, não para exibir."""
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def chave_comparacao(texto: str | None) -> str:
    """Reduz o texto à forma comparável: sem acento, sem caixa, sem pontuação.

    É com esta chave que se descobre que "SÃO PAULO", "Sao Paulo" e "são paulo"
    são a mesma cidade. Ela nunca é exibida nem gravada como valor de negócio:
    serve para agrupar e para detectar duplicidade.
    """
    if not texto:
        return ""
    return re.sub(r"[^a-z0-9]", "", sem_acento(str(texto)).lower())


def normalizar_espacos(texto: str | None) -> str | None:
    """Remove espaços das pontas e colapsa os repetidos do meio.

    Um espaço sobrando faz "Maria " e "Maria" virarem duas pessoas diferentes em
    qualquer agrupamento, e a diferença é invisível na tela.
    """
    if texto is None:
        return None
    limpo = re.sub(r"\s+", " ", str(texto)).strip()
    return limpo or None  # string que só tinha espaço é ausência de dado


def capitalizar_nome(texto: str | None) -> str | None:
    """Aplica capitalização de nome próprio, respeitando partículas e siglas.

    `str.title()` do Python não serve aqui: transforma "São Paulo" em "São Paulo"
    (certo), mas "Rua das Flores" em "Rua Das Flores" e "CD SP" em "Cd Sp".
    """
    limpo = normalizar_espacos(texto)
    if not limpo:
        return None
    palavras = limpo.split(" ")
    saida = []
    for posicao, palavra in enumerate(palavras):
        minuscula = palavra.lower()
        nucleo = minuscula.strip(".,")
        if nucleo in SIGLAS:
            saida.append(palavra.upper())
        elif nucleo in PARTICULAS and posicao > 0:
            saida.append(minuscula)
        else:
            saida.append(minuscula[:1].upper() + minuscula[1:])
    return " ".join(saida)


def normalizar_logradouro(texto: str | None) -> str | None:
    """Expande a abreviação do tipo de logradouro e capitaliza o restante.

    "R. das Flores" e "Rua das Flores" são o mesmo endereço; enquanto forem dois
    textos diferentes, são dois destinos distintos em qualquer análise geográfica.
    """
    limpo = normalizar_espacos(texto)
    if not limpo:
        return None
    partes = limpo.split(" ", 1)
    primeira = partes[0].lower()
    if primeira in ABREVIACOES_LOGRADOURO and len(partes) > 1:
        # expande a abreviação e capitaliza o texto INTEIRO de uma vez: capitalizar
        # o resto em separado faria a partícula do meio virar início de frase, e
        # "R. das Flores" sairia como "Rua Das Flores"
        limpo = f"{ABREVIACOES_LOGRADOURO[primeira]} {partes[1]}"
    return capitalizar_nome(limpo)


def tem_acento(texto: str) -> bool:
    """Diz se o texto perdeu acento em relação a si mesmo sem acento."""
    return texto != sem_acento(texto)


def canonizar_variantes(valores: Iterable[str | None]) -> dict[str, str]:
    """Elege uma grafia oficial para cada grupo de variantes e devolve o de-para.

    Capitalizar resolve caixa e espaço, mas **não devolve acento que nunca foi
    digitado**: "Sao Paulo" e "São Paulo" continuam sendo dois textos distintos, e
    portanto duas cidades distintas em qualquer agrupamento. Aqui as variantes são
    reunidas pela chave de comparação e uma delas é eleita para representar todas.

    O critério de eleição, nesta ordem:

      1. **quem tem acento ganha**, porque digitar sem acento é o erro comum e o
         contrário não acontece por descuido (ninguém acentua por engano);
      2. **quem tem caixa de nome próprio ganha** de quem está todo em maiúscula
         ou todo em minúscula, pelo mesmo motivo: são formas de digitação apressada;
      3. depois a mais frequente, que é a forma como a base de fato escreve;
      4. depois a ordem alfabética, só para o resultado ser sempre o mesmo (a
         eleição precisa ser reprodutível: rodar duas vezes tem que dar igual).

    Repare que isto é decidido **a partir dos próprios dados**, sem lista externa
    de cidades. Vale como conformação de forma, não como correção de conteúdo: se
    a base inteira escrever uma cidade errada, ela continua errada, só que uniforme.
    """
    grupos: dict[str, Counter[str]] = {}
    for valor in valores:
        if valor is None or not str(valor).strip():
            continue
        grupos.setdefault(chave_comparacao(valor), Counter())[str(valor)] += 1

    de_para: dict[str, str] = {}
    for contagem in grupos.values():
        if len(contagem) == 1:
            continue  # grafia única: nada a decidir
        eleita = sorted(
            contagem.items(),
            key=lambda par: (not tem_acento(par[0]),
                             par[0].isupper() or par[0].islower(),
                             -par[1], par[0]),
        )[0][0]
        for variante in contagem:
            if variante != eleita:
                de_para[variante] = eleita
    return de_para


def normalizar_documento(texto: str | None) -> str | None:
    """Deixa apenas os dígitos do CNPJ/CPF.

    Guardar só dígitos é o que permite comparar cadastros: com máscara, o mesmo
    documento aparece de três formas. A máscara é assunto de exibição, e se
    reconstrói na hora de mostrar.
    """
    if texto is None:
        return None
    digitos = re.sub(r"\D", "", str(texto))
    return digitos or None


def normalizar_cep(texto: str | None) -> str | None:
    """Mantém os oito dígitos do CEP, preservando zeros à esquerda.

    O zero à esquerda é a razão de CEP ser texto e não número: convertido para
    inteiro, "01001000" vira 1001000 e deixa de ser um CEP válido.
    """
    if texto is None:
        return None
    digitos = re.sub(r"\D", "", str(texto))
    return digitos.zfill(8) if digitos else None
