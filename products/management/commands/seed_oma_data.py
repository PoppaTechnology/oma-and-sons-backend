from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
from products.models import Category, Product, ProductVariant
from orders.models import PromoCode

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds initial prototype data for Oma & Sons Dynamics'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Beginning database seeding...'))

        # 1. Admin & Test Users
        admin_user, created = User.objects.get_or_create(
            email='admin@omaandsons.com',
            defaults={
                'first_name': 'Oma',
                'last_name': 'Admin',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
                'is_verified': True,
            }
        )
        if created:
            admin_user.set_password('AdminPass123!')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('Created admin user: admin@omaandsons.com'))

        customer_user, created = User.objects.get_or_create(
            email='customer@example.com',
            defaults={
                'first_name': 'Chinedu',
                'last_name': 'Okafor',
                'phone_number': '+2348012345678',
                'role': 'customer',
                'is_verified': True,
            }
        )
        if created:
            customer_user.set_password('CustomerPass123!')
            customer_user.save()
            self.stdout.write(self.style.SUCCESS('Created sample customer: customer@example.com'))

        # 2. Promo Codes
        PromoCode.objects.update_or_create(
            code='OMAWHITE',
            defaults={'discount_percent': Decimal('10.00'), 'is_active': True}
        )
        PromoCode.objects.update_or_create(
            code='WELCOME10',
            defaults={'discount_percent': Decimal('10.00'), 'is_active': True}
        )
        self.stdout.write(self.style.SUCCESS('Seeded promo codes (OMAWHITE, WELCOME10).'))

        # 5. Categories (Without image field as requested)
        categories_data = [
            {'name': 'Kitchen Appliances', 'slug': 'kitchen-appliances', 'description': 'Quality pots, pans, blenders, and everyday culinary essentials.'},
            {'name': 'Shoes', 'slug': 'shoes', 'description': 'Formal shoes, sneakers, and casual everyday footwear.'},
            {'name': 'Clothes', 'slug': 'clothes', 'description': 'Tailored blazers, jackets, tops, knitwear, and trousers.'},
            {'name': 'Bags', 'slug': 'bags', 'description': 'Leather totes, crossbody bags, and everyday carry essentials.'},
        ]

        cat_map = {}
        for c in categories_data:
            cat, _ = Category.objects.update_or_create(
                slug=c['slug'],
                defaults={'name': c['name'], 'description': c['description']}
            )
            cat_map[c['slug']] = cat
        self.stdout.write(self.style.SUCCESS('Seeded categories (image field removed).'))

        # 6. Products and Product Variants
        raw_products = [
            # Kitchen Appliances
            {
                'id': 'professional-stand-mixer-series-7',
                'name': 'Professional Stand Mixer Series 7',
                'category': 'kitchen-appliances',
                'price': Decimal('450000.00'),
                'collection': 'ARTISAN COLLECTION',
                'variant': 'Matte Black',
                'badge': 'BEST SELLER',
                'is_featured': True,
                'is_new_arrival': False,
                'is_hot_deal': True,
                'image': '/assets/professional-stand-mixer-series-7.png',
                'description': 'Engineered for precision and power, the Series 7 stand mixer brings professional-grade baking to your kitchen. Features a 7-quart capacity, 10-speed control, and durable all-metal construction. Perfect for heavy, dense doughs or large batches.'
            },
            {
                'id': 'pro-series-professional-blender',
                'name': 'Pro-Series Professional Blender',
                'category': 'kitchen-appliances',
                'price': Decimal('125000.00'),
                'collection': 'PRO SERIES',
                'variant': 'Deep Slate',
                'badge': '',
                'is_featured': True,
                'is_new_arrival': False,
                'is_hot_deal': False,
                'image': '/assets/pro-series-professional-blender.png',
                'description': 'High-performance blending for sauces, smoothies, soups, and everyday prep. A robust motor and durable jug make quick work of your kitchen routine.'
            },
            {
                'id': 'premium-espresso-maker',
                'name': 'Premium Espresso Maker',
                'category': 'kitchen-appliances',
                'price': Decimal('145000.00'),
                'collection': 'KITCHEN ESSENTIALS',
                'variant': 'Satin Silver',
                'badge': '',
                'is_featured': False,
                'is_new_arrival': True,
                'is_hot_deal': False,
                'image': '/assets/premium-espresso-maker.png',
                'description': 'A compact espresso maker for rich, café-style coffee at home, with a clean stainless finish designed for the everyday kitchen.'
            },
            {
                'id': 'premium-stainless-steel-kettle',
                'name': 'Premium Stainless Steel Kettle',
                'category': 'kitchen-appliances',
                'price': Decimal('45000.00'),
                'collection': 'KITCHEN ESSENTIALS',
                'variant': 'Brushed Steel · 1.7L',
                'badge': 'HOT',
                'is_featured': True,
                'is_new_arrival': False,
                'is_hot_deal': True,
                'image': '/assets/premium-stainless-steel-kettle.png',
                'description': 'A reliable 1.7L electric kettle with a polished stainless-steel body, fast boil performance, and a simple everyday silhouette.'
            },

            # Shoes
            {
                'id': 'classic-oxford-shoes',
                'name': 'Classic Oxford Shoes',
                'category': 'shoes',
                'price': Decimal('35000.00'),
                'collection': 'FORMAL FOOTWEAR',
                'variant': 'Chestnut Brown',
                'badge': 'HOT',
                'is_featured': True,
                'is_new_arrival': False,
                'is_hot_deal': True,
                'image': '/assets/classic-oxford-shoes.png',
                'description': 'A polished lace-up Oxford with a classic formal profile, smooth leather-look upper, and versatile finish for everyday occasions.'
            },
            {
                'id': 'essential-white-sneakers',
                'name': 'Essential White Sneakers',
                'category': 'shoes',
                'price': Decimal('45500.00'),
                'collection': 'EVERYDAY FOOTWEAR',
                'variant': 'White · Size 42',
                'badge': '',
                'is_featured': False,
                'is_new_arrival': True,
                'is_hot_deal': False,
                'image': '/assets/essential-white-sneakers.png',
                'description': 'Clean everyday sneakers with a crisp white finish, comfortable low-profile shape, and easy pairing across casual wardrobes.'
            },
            {
                'id': 'heritage-leather-loafers',
                'name': 'Heritage Leather Loafers',
                'category': 'shoes',
                'price': Decimal('42000.00'),
                'collection': 'FORMAL FOOTWEAR',
                'variant': 'Espresso Brown',
                'badge': '',
                'is_featured': False,
                'is_new_arrival': False,
                'is_hot_deal': False,
                'image': '/assets/heritage-leather-loafers.png',
                'description': 'Classic slip-on loafers with a refined leather-look finish, made to move easily between work and weekend styling.'
            },
            {
                'id': 'canvas-high-top-sneakers',
                'name': 'Canvas High-Top Sneakers',
                'category': 'shoes',
                'price': Decimal('38500.00'),
                'collection': 'CASUAL FOOTWEAR',
                'variant': 'Navy Canvas',
                'badge': '',
                'is_featured': False,
                'is_new_arrival': False,
                'is_hot_deal': False,
                'image': '/assets/canvas-high-top-sneakers.png',
                'description': 'Lightweight canvas high-tops with a casual vintage profile and supportive lace-up construction.'
            },

            # Clothes
            {
                'id': 'vintage-tweed-blazer',
                'name': 'Vintage Tweed Blazer',
                'category': 'clothes',
                'price': Decimal('24500.00'),
                'collection': 'MENSWEAR COLLECTION',
                'variant': 'Heritage Olive',
                'badge': 'NEW',
                'is_featured': True,
                'is_new_arrival': True,
                'is_hot_deal': False,
                'image': '/assets/vintage-tweed-blazer.png',
                'description': 'A structured vintage-inspired tweed blazer with a softly tailored fit, earthy texture, and versatile everyday appeal.'
            },
            {
                'id': 'silk-champagne-blouse',
                'name': 'Silk Champagne Blouse',
                'category': 'clothes',
                'price': Decimal('12000.00'),
                'former_price': Decimal('18500.00'),
                'collection': 'WOMENSWEAR',
                'variant': 'Champagne',
                'badge': 'SALE',
                'is_featured': True,
                'is_new_arrival': False,
                'is_hot_deal': True,
                'image': '/assets/silk-champagne-blouse.png',
                'description': 'A light, elegant champagne blouse with a fluid drape and understated finish for easy elevated dressing.'
            },
            {
                'id': 'classic-blue-denim-jacket',
                'name': 'Classic Blue Denim Jacket',
                'category': 'clothes',
                'price': Decimal('15000.00'),
                'collection': 'UNISEX OUTERWEAR',
                'variant': 'Classic Indigo',
                'badge': '',
                'is_featured': False,
                'is_new_arrival': False,
                'is_hot_deal': False,
                'image': '/assets/classic-blue-denim-jacket.png',
                'description': 'A timeless indigo denim jacket with a relaxed unisex cut, practical pockets, and a familiar everyday layer.'
            },
            {
                'id': 'chunky-knit-wool-sweater',
                'name': 'Chunky Knit Wool Sweater',
                'category': 'clothes',
                'price': Decimal('18500.00'),
                'collection': 'WINTER COLLECTION',
                'variant': 'Charcoal Knit',
                'badge': '',
                'is_featured': False,
                'is_new_arrival': True,
                'is_hot_deal': False,
                'image': '/assets/chunky-knit-wool-sweater.png',
                'description': 'A textured chunky-knit sweater with soft warmth, a relaxed shape, and a tactile winter-ready finish.'
            },

            # Bags
            {
                'id': 'premium-leather-tote',
                'name': 'Premium Leather Tote',
                'category': 'bags',
                'price': Decimal('24500.00'),
                'collection': 'EVERYDAY BAGS',
                'variant': 'Tan',
                'badge': 'SALE',
                'is_featured': True,
                'is_new_arrival': False,
                'is_hot_deal': True,
                'image': '/assets/premium-leather-tote.png',
                'description': 'A practical tan leather-look tote with clean handles and generous daily carrying space.'
            },
            {
                'id': 'executive-leather-tote',
                'name': 'Executive Leather Tote',
                'category': 'bags',
                'price': Decimal('120000.00'),
                'collection': 'EXECUTIVE BAGS',
                'variant': 'Deep Onyx',
                'badge': '',
                'is_featured': True,
                'is_new_arrival': True,
                'is_hot_deal': False,
                'image': '/assets/executive-leather-tote.png',
                'description': 'A refined structured tote in deep onyx, designed for polished workdays and elevated everyday carry.'
            },
            {
                'id': 'classic-leather-tote',
                'name': 'Classic Leather Tote',
                'category': 'bags',
                'price': Decimal('68500.00'),
                'collection': 'EVERYDAY BAGS',
                'variant': 'Espresso Brown',
                'badge': '',
                'is_featured': False,
                'is_new_arrival': False,
                'is_hot_deal': False,
                'image': '/assets/classic-leather-tote.png',
                'description': 'A classic leather-look tote with a balanced, understated profile and generous room for daily essentials.'
            },
            {
                'id': 'camel-crossbody-bag',
                'name': 'Camel Crossbody Bag',
                'category': 'bags',
                'price': Decimal('8500.00'),
                'collection': 'EVERYDAY BAGS',
                'variant': 'Camel',
                'badge': '',
                'is_featured': False,
                'is_new_arrival': False,
                'is_hot_deal': False,
                'image': '/assets/camel-crossbody-bag.png',
                'description': 'A compact camel crossbody with a simple adjustable strap and hands-free everyday practicality.'
            }
        ]

        for p_data in raw_products:
            cat = cat_map[p_data['category']]
            prod, _ = Product.objects.update_or_create(
                slug=p_data['id'],
                defaults={
                    'category': cat,
                    'name': p_data['name'],
                    'description': p_data['description'],
                    'collection': p_data.get('collection', ''),
                    'badge': p_data.get('badge', ''),
                    'is_new_arrival': p_data.get('is_new_arrival', False),
                    'is_featured': p_data.get('is_featured', False),
                    'former_price': p_data.get('former_price', None)
                }
            )

            # Create primary variant (is_new_arrival removed from variant as requested)
            ProductVariant.objects.update_or_create(
                product=prod,
                variant_name=p_data.get('variant', 'Standard'),
                defaults={
                    'price': p_data['price'],
                    'image': p_data.get('image', ''),
                    'stock_quantity': 25,
                    'available': True,
                    'size': 'Standard' if '·' not in p_data.get('variant', '') else p_data.get('variant', '').split('·')[-1].strip()
                }
            )

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {len(raw_products)} products with variants.'))
        self.stdout.write(self.style.SUCCESS('Database seeding completed successfully!'))
