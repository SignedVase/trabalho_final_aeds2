"""Catálogo público de CEPs e logradouros de Nova Serrana."""
import re
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.core.cache import cache

FONTE = "https://www.novaserrana.mg.gov.br/portal/servicos/1003/ceps/"
CHAVE = "rota-fans:logradouros:v1"

# Amostra do cadastro municipal, disponível durante falhas na fonte.
AMOSTRA = [
    ("Rua Um", "Fausto Pinto da Fonseca II", "35523-258"),
    ("Rua Um", "Floresta", "35524-506"),
    ("Rua Um", "Jardim São Francisco", "35523-121"),
    ("Rua Um", "Mont Serrat", "35524-360"),
    ("Rua Um", "Sandra Regina", "35526-574"),
    ("Rua Um", "Santa Helena", "35523-468"),
    ("Rua Um", "Santa Teresa", "35527-298"),
    ("Rua Um", "São Luiz", "35524-488"),
    ("Rua Dois", "Mangabeiras", "35522-476"),
    ("Rua Onze", "Floresta", "35524-520"),
    ("Rua Nazaré", "São Marcos", "35523-036"),
    ("Avenida Belém", "Ferreira Neto", "35524-042"),
]


class TabelaLogradouros(HTMLParser):
    def __init__(self):
        super().__init__()
        self.linhas = []
        self.linha = None
        self.celula = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.linha = []
        elif tag == "td" and self.linha is not None:
            self.celula = []

    def handle_data(self, data):
        if self.celula is not None:
            self.celula.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.celula is not None:
            self.linha.append(" ".join("".join(self.celula).split()))
            self.celula = None
        elif tag == "tr" and self.linha is not None:
            if len(self.linha) == 4:
                rua, bairro, cidade, cep = self.linha
                if rua and bairro and re.fullmatch(r"Nova Serrana\s*/\s*MG", cidade, re.I):
                    if re.fullmatch(r"\d{5}-\d{3}", cep):
                        self.linhas.append((rua, bairro, cep))
            self.linha = self.celula = None


def formatar(linhas):
    catalogo = []
    for rua, bairro, cep in sorted(set(linhas)):
        # Nomes anteriores entre parênteses permanecem pesquisáveis.
        nome = re.sub(r"\s*\([^()]+\)\s*$", "", rua)
        endereco = f"{nome}, {bairro}, Nova Serrana - MG"
        catalogo.append({"endereco": endereco, "busca": rua, "cep": cep})
    return catalogo


def obter_catalogo():
    anterior = cache.get(CHAVE)
    if anterior and cache.get(CHAVE + ":atual"):
        return anterior
    if not cache.add(CHAVE + ":consulta", True, timeout=300):
        return anterior or []
    try:
        pedido = Request(FONTE, headers={"User-Agent": "RotaFANS/1.0 (academic project)"})
        with urlopen(pedido, timeout=6) as resposta:
            codificacao = resposta.headers.get_content_charset() or "utf-8"
            pagina = resposta.read(6_000_001)
            if len(pagina) > 6_000_000:
                return anterior or []
        tabela = TabelaLogradouros()
        tabela.feed(pagina.decode(codificacao, errors="replace"))
        ruas = formatar(tabela.linhas)
    except (URLError, OSError, LookupError, ValueError):
        return anterior or []
    if not ruas:
        return anterior or []
    cache.set(CHAVE, ruas, timeout=7 * 86400)
    cache.set(CHAVE + ":atual", True, timeout=86400)
    return ruas
