from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_resume_processing_and_interviews"),
    ]

    operations = [
        migrations.AddField(
            model_name="interviewfeedback",
            name="professional_answers",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
