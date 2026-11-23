import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .logradouros import AMOSTRA, FONTE, formatar, obter_catalogo
from .models import Estudante
from .servicos import CATALOGO, FANS, ErroConsulta, consultar_osrm, demonstracao


@require_GET
def inicio(request):
    return render(request, "index.html", {
        "catalogo": CATALOGO + formatar(AMOSTRA), "fans": FANS, "fonte_logradouros": FONTE,
    })


@require_GET
def logradouros(request):
    ruas = obter_catalogo()
    if not ruas:
        return JsonResponse({"ruas": []}, status=503)
    resposta = JsonResponse({"ruas": ruas})
    resposta["Cache-Control"] = "public, max-age=3600"
    return resposta


@require_POST
def calcular(request):
    try:
        dados = json.loads(request.body)
        nome, origem, destino = (dados[campo].strip() for campo in ("nome", "origem", "destino"))
    except (KeyError, AttributeError, TypeError, ValueError):
        return JsonResponse({"erro": "Dados da consulta inválidos."}, status=400)
    if len(nome.split()) < 2 or not origem or not destino:
        return JsonResponse({"erro": "Informe o nome completo, a partida e a chegada."}, status=400)
    if len(nome) > 160 or max(len(origem), len(destino)) > 250:
        return JsonResponse({"erro": "O nome ou o endereço excede o limite de caracteres."}, status=400)
    if origem.casefold() == destino.casefold():
        return JsonResponse({"erro": "Informe endereços diferentes para partida e chegada."}, status=400)
    try:
        resultado = consultar_osrm(origem, destino)
    except ErroConsulta as erro:
        return JsonResponse({"erro": str(erro)}, status=422)
    Estudante.objects.get_or_create(nome=nome, endereco=origem)
    return JsonResponse(resultado)


@require_GET
def demo(request):
    try:
        return JsonResponse(demonstracao())
    except ErroConsulta as erro:
        return JsonResponse({"erro": str(erro)}, status=422)
