from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("api/rotas/", views.calcular, name="calcular"),
    path("api/logradouros/", views.logradouros, name="logradouros"),
    path("api/demo/", views.demo, name="demo"),
]
