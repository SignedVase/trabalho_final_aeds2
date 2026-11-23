from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Estudante",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=160)),
                ("endereco", models.CharField(max_length=250)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("nome", "endereco"), name="estudante_nome_endereco_unicos"),
                ],
            },
        ),
    ]
