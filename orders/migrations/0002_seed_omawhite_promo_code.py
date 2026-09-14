from django.db import migrations


def create_omawhite_promo(apps, schema_editor):
    PromoCode = apps.get_model('orders', 'PromoCode')
    PromoCode.objects.get_or_create(
        code='OMAWHITE',
        defaults={
            'discount_percent': 10.00,
            'is_active': True,
        }
    )


def remove_omawhite_promo(apps, schema_editor):
    PromoCode = apps.get_model('orders', 'PromoCode')
    PromoCode.objects.filter(code='OMAWHITE').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_omawhite_promo, remove_omawhite_promo),
    ]
