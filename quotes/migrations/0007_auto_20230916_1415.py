from django.db import migrations
import pandas as pd
import os

def fill_db_with_French_stocks(apps, schema_editor):

    FinancialObject = apps.get_model("quotes", "FinancialObject")
    df = pd.read_csv("List_stocks.csv")
    etf_category = "Stock"
    objects = []

    for i in range(df.shape[0]):
        obj = FinancialObject(
            name=df.loc[i]["Nom"],
            category=etf_category,
            isin=df.loc[i]["ISIN"],
            ticker=df.loc[i]["Code Yahoo Finance"])

        objects.append(obj)

    FinancialObject.objects.bulk_create(objects)

class Migration(migrations.Migration):

    dependencies = [
        ('quotes', '0001_squashed_0006_financialobject_ticker'),
    ]

    operations = [
        migrations.RunPython(fill_db_with_French_stocks),
    ]
