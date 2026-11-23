from django.db import models


class Estudante(models.Model):
    nome = models.CharField(max_length=160)
    endereco = models.CharField(max_length=250)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["nome", "endereco"], name="estudante_nome_endereco_unicos"),
        ]
