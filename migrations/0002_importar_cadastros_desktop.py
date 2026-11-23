import sqlite3
from contextlib import closing
from pathlib import Path

from django.conf import settings
from django.db import migrations


def importar(apps, schema_editor):
    arquivo = Path(settings.BASE_DIR) / "estudantes.sqlite3"
    if not arquivo.is_file():
        return
    estudante = apps.get_model("rotaweb", "Estudante")
    with closing(sqlite3.connect(arquivo.as_uri() + "?mode=ro", uri=True)) as origem:
        tabela = origem.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'estudantes'"
        ).fetchone()
        if tabela:
            estudante.objects.using(schema_editor.connection.alias).bulk_create(
                (estudante(nome=nome, endereco=endereco)
                 for nome, endereco in origem.execute("SELECT nome, endereco FROM estudantes")),
                ignore_conflicts=True,
            )


class Migration(migrations.Migration):
    dependencies = [("rotaweb", "0001_initial")]
    operations = [migrations.RunPython(importar, migrations.RunPython.noop)]
