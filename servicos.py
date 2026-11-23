"""Integração com Photon e OSRM sob demanda."""
import json
import os
import re
from hashlib import sha256
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.cache import cache

FANS = "Rua Lígia Rodrigues, 600, Fausto Pinto da Fonseca, Nova Serrana - MG"

CATALOGO = [
    {"endereco": FANS, "busca": "FANS Faculdade de Nova Serrana Rua Lígia Rodrigues 600"},
    {"endereco": "Praça da Matriz, Nova Serrana - MG", "busca": "Praça da Matriz Centro"},
    {"endereco": "Praça da Bíblia, Nova Serrana - MG", "busca": "Praça da Bíblia"},
    {"endereco": "Praça Chefe Rose, Nova Serrana - MG", "busca": "Praça Chefe Rose"},
    {"endereco": "Centro, Nova Serrana - MG", "busca": "Centro"},
    {"endereco": "Fausto Pinto da Fonseca, Nova Serrana - MG", "busca": "Fausto Pinto da Fonseca"},
    {"endereco": "Boa Vista de Minas, Nova Serrana - MG", "busca": "Boa Vista de Minas"},
]
CENTRO = (-19.875833, -44.983889)


class ErroConsulta(Exception):
    pass


def obter_json(url, servico):
    chave = "rota-fans:" + sha256(url.encode()).hexdigest()
    dados = cache.get(chave)
    if dados is not None:
        return dados
    if servico == "OSRM" and not cache.add("osrm-consulta-em-curso", True, timeout=1):
        raise ErroConsulta("Aguarde um segundo antes de solicitar outra rota.")
    pedido = Request(url, headers={
        "User-Agent": os.getenv("ROTA_HTTP_USER_AGENT", "RotaFANS/1.0 (academic project)"),
        "Accept": "application/json",
    })
    try:
        with urlopen(pedido, timeout=8) as resposta:
            dados = json.load(resposta)
        if not isinstance(dados, dict):
            raise ValueError
    except HTTPError as erro:
        with erro:
            if servico == "OSRM" and erro.code == 400:
                try:
                    codigo = json.load(erro).get("code")
                except (AttributeError, OSError, ValueError):
                    codigo = None
                if codigo in ("NoSegment", "NoRoute"):
                    return {"code": codigo}
        raise ErroConsulta(f"{servico} não conseguiu processar a consulta. Tente novamente.") from erro
    except (URLError, OSError, ValueError) as erro:
        raise ErroConsulta(f"{servico} está indisponível. Tente novamente.") from erro
    cache.set(chave, dados, timeout=600)
    return dados


def localizar(endereco):
    base = os.getenv("PHOTON_URL", "https://photon.komoot.io").rstrip("/")
    buscas = ("Faculdade de Nova Serrana, Nova Serrana, Minas Gerais", endereco) if endereco == FANS else (endereco,)
    for busca in buscas:
        encontrado = buscar_endereco(base, busca, endereco)
        if encontrado:
            return encontrado
    if endereco == FANS:
        raise ErroConsulta("O Photon não identificou o campus. Experimente editar o destino.")
    raise ErroConsulta(f"Endereço não encontrado: {endereco}. Confira a cidade e o número, ou informe uma rua próxima.")


def buscar_endereco(base, busca, endereco):
    parametros = {"q": busca, "limit": 5, "countrycode": "BR", "lat": CENTRO[0], "lon": CENTRO[1]}
    resposta = obter_json(f"{base}/api/?{urlencode(parametros)}", "Photon")
    numero = re.search(r",\s*(\d+[a-zA-Z]?)\s*(?:,|$)", endereco)
    for item in resposta.get("features", []):
        try:
            prop = item["properties"]
            lon, lat = item["geometry"]["coordinates"]
            if endereco == FANS and busca != endereco:
                nome = str(prop.get("name", "")).casefold()
                if "faculdade" not in nome and "fans" not in nome:
                    continue
                if abs(lat - CENTRO[0]) > 0.12 or abs(lon - CENTRO[1]) > 0.12:
                    continue
            elif numero and str(prop.get("housenumber", "")).casefold() != numero[1].casefold():
                continue
            partes = [prop.get("name"), prop.get("street"), prop.get("housenumber"),
                      prop.get("city"), prop.get("state")]
            rotulo = ", ".join(dict.fromkeys(str(parte) for parte in partes if parte))
            return {"endereco": rotulo or endereco, "ponto": [lon, lat]}
        except (KeyError, TypeError, ValueError):
            continue


def consultar_osrm(origem, destino):
    return rotear(localizar(origem), localizar(destino))


def rotear(partida, chegada):
    a, b = partida["ponto"], chegada["ponto"]
    if a == b:
        raise ErroConsulta("Os endereços foram localizados no mesmo ponto. Confira a partida e a chegada.")
    trecho = f"{a[0]},{a[1]};{b[0]},{b[1]}"
    base = os.getenv("OSRM_URL", "https://routing.openstreetmap.de/routed-car").rstrip("/")
    url = (f"{base}/route/v1/driving/{trecho}"
           "?alternatives=2&overview=full&geometries=geojson&radiuses=150;150&generate_hints=false")
    resultado = obter_json(url, "OSRM")
    if resultado.get("code") == "NoSegment":
        raise ErroConsulta("Não foi encontrada uma via acessível para carros perto de um dos pontos. Confira os endereços.")
    try:
        rotas = []
        for rota in resultado.get("routes", []):
            linha = rota["geometry"]
            pontos = linha["coordinates"]
            if linha["type"] != "LineString" or len(pontos) < 2:
                raise ValueError
            rotas.append({
                "metros": rota["distance"], "segundos": rota["duration"], "geometria": linha,
            })
    except (KeyError, TypeError, ValueError) as erro:
        raise ErroConsulta("O OSRM retornou dados inválidos.") from erro
    if not rotas:
        raise ErroConsulta("Nenhuma rota de carro encontrada entre esses locais.")
    rotas.sort(key=lambda rota: (rota["metros"], rota["segundos"]))
    return {"rotas": rotas[:3], "partida": partida, "chegada": chegada}


def demonstracao():
    return rotear(
        {"endereco": "Ponto de exemplo em Nova Serrana", "ponto": [CENTRO[1], CENTRO[0]]},
        {"endereco": "Segundo ponto de exemplo em Nova Serrana", "ponto": [-44.976, -19.88]},
    )
