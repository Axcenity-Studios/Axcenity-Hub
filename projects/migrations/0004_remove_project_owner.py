"""Projects are owned through their Owner memberships now (0003 copied every owner)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0003_teams"),
    ]

    operations = [
        migrations.RemoveField(model_name="project", name="owner"),
    ]
