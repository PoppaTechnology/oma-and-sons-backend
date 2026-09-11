import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oma_and_sons.settings')
os.environ.setdefault('PAYSTACK_SECRET_KEY', 'sk_test_mock_paystack_secret_key')
os.environ.setdefault('PAYSTACK_PUBLIC_KEY', 'pk_test_mock_paystack_public_key')
os.environ.setdefault('FLUTTERWAVE_SECRET_KEY', 'FLWSECK_TEST-mock_flw_secret_key')
os.environ.setdefault('FLUTTERWAVE_PUBLIC_KEY', 'FLWPUBK_TEST-mock_flw_public_key')
os.environ.setdefault('FLUTTERWAVE_SECRET_HASH', 'mock_flw_secret_hash')
django.setup()

from rest_framework.test import APIClient
from decimal import Decimal
import json

client = APIClient()

def run_tests():
    print("=" * 60)
    print("STARTING OMA & SONS REST API COMPREHENSIVE VERIFICATION")
    print("=" * 60)

    # 1. Categories API (Verify image field is NOT in category)
    print("\n--- 1. Testing Categories API ---")
    res = client.get('/products/categories/')
    assert res.status_code == 200
    cats = res.json()
    assert len(cats) >= 4
    for c in cats:
        assert 'image' not in c, "Image field should have been removed from Category entity!"
        assert 'name' in c and 'slug' in c
    print(f"✓ Categories API verified: {len(cats)} categories found, 'image' field successfully excluded.")

    # 3. Products List & Filtering API (Verify is_new_arrival is on Product, not on Variant)
    print("\n--- 3. Testing Products API & Filters ---")
    res = client.get('/products/')
    assert res.status_code == 200
    products = res.json()
    assert len(products) >= 15
    for p in products:
        assert 'is_new_arrival' in p, "is_new_arrival must be on Product entity!"
        for v in p['variants']:
            assert 'is_new_arrival' not in v, "is_new_arrival must NOT be on ProductVariant entity!"
    print("✓ Product schema verified: is_new_arrival confirmed on Product and absent from ProductVariant.")

    # Filter by category
    res_cat = client.get('/products/?category=shoes')
    assert res_cat.status_code == 200
    shoes = res_cat.json()
    assert all(p['category'] == 'shoes' for p in shoes)
    print(f"✓ Filter by category=shoes returned {len(shoes)} products.")

    # Filter by new arrivals
    res_new = client.get('/products/new-arrivals/')
    assert res_new.status_code == 200
    new_items = res_new.json()
    assert len(new_items) > 0
    print(f"✓ New arrivals API returned {len(new_items)} items.")

    # Filter by search
    res_search = client.get('/products/?search=blender')
    assert res_search.status_code == 200
    search_results = res_search.json()
    assert any('blender' in p['name'].lower() for p in search_results)
    print(f"✓ Search query 'blender' returned {len(search_results)} item(s).")

    # 4. Product Detail & Recommendations
    print("\n--- 4. Testing Product Detail & Recommendations ---")
    slug = 'professional-stand-mixer-series-7'
    res_detail = client.get(f'/products/{slug}/')
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail['slug'] == slug
    assert len(detail['variants']) >= 1
    assert 'recommendations' in detail and len(detail['recommendations']) > 0
    assert 'is_hot_deal' not in detail, "is_hot_deal should be removed from Product!"
    print(f"✓ Product Detail for '{detail['name']}' returned with variants and recommendations.")

    # 5. Accounts: Auth, Profile, Addresses, Wishlist
    print("\n--- 5. Testing Accounts & Authentication API ---")
    import uuid as _uuid
    email = f"testbuyer_{_uuid.uuid4().hex[:6]}@example.com"
    res_reg = client.post('/accounts/register/', {
        'first_name': 'Ngozi',
        'last_name': 'Eze',
        'email': email,
        'phone_number': '+2348033334444',
        'password': 'StrongPassword123!'
    }, format='json')
    assert res_reg.status_code == 201
    reg_data = res_reg.json()
    token = reg_data['token']
    print(f"✓ User registered successfully. Auth Token received.")

    # Login
    res_log = client.post('/accounts/login/', {
        'email': email,
        'password': 'StrongPassword123!'
    }, format='json')
    assert res_log.status_code == 200
    print("✓ User login verified.")

    # Authenticated client
    auth_client = APIClient()
    auth_client.credentials(HTTP_AUTHORIZATION='Token ' + token)

    # Profile
    res_prof = auth_client.get('/accounts/profile/')
    assert res_prof.status_code == 200
    print(f"✓ Profile retrieved for: {res_prof.json()['email']}")

    # Wishlist Toggle
    res_wish = auth_client.post('/accounts/wishlist/', {'slug': slug}, format='json')
    assert res_wish.status_code == 201
    assert res_wish.json()['saved'] is True
    res_wish_list = auth_client.get('/accounts/wishlist/')
    assert slug in res_wish_list.json()['saved_ids']
    print(f"✓ Wishlist/Saved Items verified for product '{slug}'.")

    # 6. Cart API
    print("\n--- 6. Testing Cart Management API ---")
    # Add to cart
    res_add = client.post('/cart/items/', {
        'product_id': slug,
        'quantity': 2
    }, format='json')
    assert res_add.status_code == 200
    cart_data = res_add.json()
    assert cart_data['total_items'] == 2
    print(f"✓ Added item to cart. Total items: {cart_data['total_items']}, Subtotal: ₦{cart_data['subtotal']}")

    item_id = cart_data['items'][0]['id']
    # Update quantity
    res_upd = client.patch(f'/cart/items/{item_id}/', {'quantity': 3}, format='json')
    assert res_upd.status_code == 200
    assert res_upd.json()['total_items'] == 3
    print("✓ Updated cart item quantity to 3.")

    # 7. Promo Code Validation
    print("\n--- 7. Testing Promo Code Validation ---")
    res_promo = client.post('/orders/validate-promo/', {
        'code': 'OMAWHITE',
        'subtotal': '100000.00'
    }, format='json')
    assert res_promo.status_code == 200
    promo_data = res_promo.json()
    assert promo_data['valid'] is True
    assert Decimal(str(promo_data['discount_amount'])) == Decimal('10000.00')
    print(f"✓ Promo code 'OMAWHITE' verified: {promo_data['discount_percent']}% applied (₦{promo_data['discount_amount']} off).")

    # 8. Checkout & Order Placement
    print("\n--- 8. Testing Checkout & Order Placement ---")
    checkout_payload = {
        'email': 'ngozi@example.com',
        'phone': '+2348033334444',
        'firstName': 'Ngozi',
        'lastName': 'Eze',
        'fulfillment': 'ship',
        'deliveryMethod': 'standard',
        'address': '45 Bourdillon Road, Ikoyi',
        'city': 'Ikoyi',
        'state': 'Lagos',
        'discountCode': 'OMAWHITE',
        'items': [
            {'productId': 'classic-oxford-shoes', 'quantity': 1},
            {'productId': 'vintage-tweed-blazer', 'quantity': 1}
        ]
    }
    # Shoes: 35,000 + Blazer: 24,500 = Subtotal: 59,500
    # Discount (10%): 5,950
    # Delivery (standard): 2,500
    # Taxes (5% of 59,500): 2,975
    # Total: 59,500 - 5,950 + 2,500 + 2,975 = 59,025

    res_checkout = client.post('/orders/checkout/', checkout_payload, format='json')
    assert res_checkout.status_code == 201, f"Checkout failed: {res_checkout.data}"
    checkout_res = res_checkout.json()
    order = checkout_res['order']
    order_num = order['order_number']
    payment_ref = checkout_res['payment_reference']
    print(f"✓ Order placed successfully: Order {order_num}")
    print(f"  - Subtotal: ₦{order['subtotal']}")
    print(f"  - Discount: ₦{order['discount_amount']} ({order['discount_code']})")
    print(f"  - Delivery: ₦{order['delivery_fee']} ({order['delivery_method']})")
    print(f"  - Tax: ₦{order['tax_amount']}")
    print(f"  - Total: ₦{order['total_amount']}")
    print(f"  - Status: {order['order_status']}")
    print(f"  - Payment Reference: {payment_ref}")

    # 9. Order Detail Authorization & Guest Tracking
    print("\n--- 9. Testing Order Authorization & Guest Tracking API ---")
    clean_order_num = order_num.lstrip('#')

    # 9a. Unauthenticated access to /orders/<order_number>/ must return 401
    res_unauth = client.get(f'/orders/{clean_order_num}/')
    assert res_unauth.status_code == 401, f"Expected 401 for unauthenticated order detail, got {res_unauth.status_code}"
    print("✓ Unauthenticated request to /orders/<order_number>/ correctly rejected with 401 Unauthorized.")

    # 9b. Place authenticated order with auth_client
    auth_checkout_res = auth_client.post('/orders/checkout/', checkout_payload, format='json')
    assert auth_checkout_res.status_code == 201
    auth_order_num = auth_checkout_res.json()['order']['order_number']
    clean_auth_order_num = auth_order_num.lstrip('#')

    # Authenticated owner retrieves their order -> 200 OK with full details
    res_owner = auth_client.get(f'/orders/{clean_auth_order_num}/')
    assert res_owner.status_code == 200
    assert res_owner.json()['order_number'] == auth_order_num
    assert 'phone_number' in res_owner.json()
    assert 'delivery_address' in res_owner.json()
    print("✓ Authenticated owner successfully retrieved their order (200 OK) with full details.")

    # 9c. Another authenticated user accessing non-owned order -> 404 Not Found (no info disclosure)
    other_user_email = f"otherbuyer_{_uuid.uuid4().hex[:6]}@example.com"
    res_other_reg = client.post('/accounts/register/', {
        'first_name': 'Other',
        'last_name': 'User',
        'email': other_user_email,
        'phone_number': '+2348099998888',
        'password': 'StrongPassword123!'
    }, format='json')
    other_token = res_other_reg.json()['token']
    other_client = APIClient()
    other_client.credentials(HTTP_AUTHORIZATION='Token ' + other_token)

    res_non_owner = other_client.get(f'/orders/{clean_auth_order_num}/')
    assert res_non_owner.status_code == 404, f"Expected 404 for non-owner, got {res_non_owner.status_code}"
    print("✓ Non-owner authenticated user correctly received 404 Not Found (no order enumeration).")

    # 9d. Guest tracking via /orders/track/ with order_number + email
    res_guest_track = client.get(f'/orders/track/?number={clean_order_num}&email={checkout_payload["email"]}')
    assert res_guest_track.status_code == 200
    track_data = res_guest_track.json()
    assert track_data['order_number'] == order_num
    assert 'phone_number' not in track_data, "Phone number must not be exposed in public tracking!"
    assert 'delivery_address' not in track_data, "Delivery address must not be exposed in public tracking!"
    print("✓ Guest tracking verified: 200 OK returned sanitized tracking data without customer PII.")

    # Guest tracking without email -> 400 Bad Request
    res_track_no_email = client.get(f'/orders/track/?number={clean_order_num}')
    assert res_track_no_email.status_code == 400
    print("✓ Guest tracking without email correctly rejected with 400 Bad Request.")

    # 10. Payment Initialization & Verification (Paystack & Flutterwave)
    print("\n--- 10. Testing Payment Initialization & Verification (Paystack & Flutterwave) ---")
    from unittest.mock import patch, MagicMock

    # 10a. Initialize with Paystack
    with patch('requests.post') as mock_init_post:
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {
            'status': True,
            'message': 'Authorization URL created',
            'data': {
                'authorization_url': 'https://checkout.paystack.com/0123456789',
                'access_code': '0123456789',
                'reference': payment_ref
            }
        }
        mock_init_post.return_value = mock_res

        res_init = client.post('/payments/initialize/', {
            'order_number': order_num,
            'provider': 'PAYSTACK'
        }, format='json')
        assert res_init.status_code == 200, f"Initialization failed: {res_init.data}"
        init_data = res_init.json()
        assert init_data['success'] is True
        assert init_data['provider'] == 'PAYSTACK'
        assert init_data['checkout_url'] == 'https://checkout.paystack.com/0123456789'
        active_ref = init_data['payment_reference']
        print(f"✓ Paystack Payment Initialization verified: checkout URL received -> {init_data['checkout_url']} (ref: {active_ref})")

    # 10b. Verify Payment
    with patch('requests.get') as mock_verify_get:
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {
            'status': True,
            'message': 'Verification successful',
            'data': {
                'id': 998877,
                'status': 'success',
                'reference': active_ref,
                'amount': int(round(Decimal(str(order['total_amount'])) * 100)),
                'currency': 'NGN',
                'gateway_response': 'Successful',
                'paid_at': '2026-09-08T12:00:00.000Z',
                'customer': {'email': checkout_payload['email']}
            }
        }
        mock_verify_get.return_value = mock_res

        res_pay = client.post('/payments/verify/', {'reference': active_ref}, format='json')
        assert res_pay.status_code == 200, f"Verification failed: {res_pay.data}"
        pay_data = res_pay.json()
        assert pay_data['verified'] is True
        assert pay_data['order']['order_status'] == 'CONFIRMED'
        assert pay_data['payment']['payment_status'] == 'SUCCESSFUL'
        print(f"✓ Payment verified! Order status updated to CONFIRMED and Payment marked SUCCESSFUL.")

    print("\n" + "=" * 60)
    print("ALL 10 API TEST SUITES PASSED FLAWLESSLY!")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
