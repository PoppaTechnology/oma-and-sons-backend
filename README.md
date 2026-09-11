# Oma & Sons Dynamics API

This repository contains the Django REST API for the Oma & Sons storefront. It provides catalog browsing, customer accounts, guest and authenticated carts, checkout, order tracking, promo codes, and Paystack/Flutterwave payment integration.

The API is designed to be consumed by a React storefront. Django also serves the admin site and, during local development, uploaded media and collected static files.

## Contents

- [Technology](#technology)
- [Local setup](#local-setup)
- [Environment variables](#environment-variables)
- [Base URLs and conventions](#base-urls-and-conventions)
- [Authentication](#authentication)
- [Images, media, and static files](#images-media-and-static-files)
- [API reference](#api-reference)
- [Recommended React integration](#recommended-react-integration)
- [Checkout and payment flow](#checkout-and-payment-flow)
- [Errors and frontend behavior](#errors-and-frontend-behavior)
- [Admin workflow](#admin-workflow)
- [Production checklist](#production-checklist)

## Technology

- Python and Django 6.1
- Django REST Framework with token and session authentication
- SQLite for the current local database
- `django-cors-headers` for React development and deployed frontend origins
- Paystack and Flutterwave payment services

## Local setup

From the repository root:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The API is then available at `http://127.0.0.1:8000` and the admin at `http://127.0.0.1:8000/admin/`.

Optional seed data is available through the management command:

```powershell
python manage.py seed_oma_data
```

Run the built-in checks with:

```powershell
python manage.py check
```

## Environment variables

Create a `.env` file in the repository root. Do not commit real secrets.

```env
SECRET_KEY=replace-with-a-long-random-value
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# Required for payment initialization and verification
PAYSTACK_SECRET_KEY=sk_test_...
PAYSTACK_PUBLIC_KEY=pk_test_...
FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST-...
FLUTTERWAVE_PUBLIC_KEY=FLWPUBK_TEST-...
FLUTTERWAVE_SECRET_HASH=replace-with-webhook-secret

# Where a provider sends the customer after checkout
PAYMENT_CALLBACK_URL=http://localhost:5173/checkout/verify

# Required when DEBUG=False. Use the deployed React origin(s), comma-separated.
CORS_ALLOWED_ORIGINS=https://shop.example.com
```

`PAYMENT_CALLBACK_URL` is also accepted per request by the payment initialization endpoint as `callback_url`.

## Base URLs and conventions

Use the `/api/` prefix from React:

```js
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api';
```

Every API route is also exposed without the prefix for backward compatibility. For example, both `/api/products/` and `/products/` work. New frontend code should use the `/api/` form consistently.

The root endpoints return a small service description:

- `GET /` or `GET /api/`
- `GET /admin/` for Django staff administration

JSON requests should send:

```http
Content-Type: application/json
Accept: application/json
```

Prices and totals are returned as decimal values/strings. Treat them as currency amounts and format them as Nigerian naira (`NGN`) in the UI; do not recalculate the final order total on the client.

## Authentication

Registration and login return a DRF token:

```json
{
	"token": "abc123...",
	"user": {
		"id": 1,
		"first_name": "Ada",
		"last_name": "Example",
		"email": "ada@example.com"
	}
}
```

Store the token using the React application's chosen secure strategy and send it on protected requests:

```http
Authorization: Token abc123...
```

Available account endpoints:

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/accounts/register/` | Public | Create an account and return a token |
| `POST` | `/api/accounts/sign-up/` | Public | Alias for registration |
| `POST` | `/api/accounts/login/` | Public | Authenticate with `email` and `password` |
| `POST` | `/api/accounts/logout/` | Required | Delete the current token |
| `GET`, `PATCH`, `PUT` | `/api/accounts/profile/` | Required | Read or update the current profile |
| `GET` | `/api/accounts/wishlist/` | Required | Return saved IDs and saved product records |
| `POST` | `/api/accounts/wishlist/` | Required | Toggle a product using `product_id` or `slug` |

Registration fields are `first_name`, `last_name`, `email`, `phone_number`, and `password` (minimum six characters). The account email is the login identifier.

## Images, media, and static files

### Current product image behavior

Product images are currently represented by the `image` string on `ProductVariant`. The field is a URL or asset path, not a Django `ImageField`. The API does **not** currently expose a multipart upload endpoint.

In the admin, staff enter the image value directly while editing a product variant. Examples:

```text
https://cdn.example.com/products/mixer.webp
/media/products/mixer.webp
```

The product and cart serializers return that same value. Do not assume it is always an absolute URL.

### Resolving image URLs in React

Use absolute URLs unchanged and resolve relative paths against the Django origin:

```js
const API_ORIGIN = import.meta.env.VITE_API_ORIGIN ?? 'http://127.0.0.1:8000';

export function resolveAssetUrl(value) {
	if (!value) return '';
	if (/^https?:\\/\\//i.test(value)) return value;
	return `${API_ORIGIN}${value.startsWith('/') ? value : `/${value}`}`;
}
```

Use it for `product.image`, `variant.image`, cart item `image`, and order item `image`.

### Django media and static paths

The project settings define:

```text
MEDIA_URL=/media/
MEDIA_ROOT=<project>/media/
STATIC_URL=static/
STATICFILES_DIRS=<project>/static/
STATIC_ROOT=<project>/staticfiles/
```

With `DEBUG=True`, Django appends development routes for both media and static files. This means local files can be requested from the React app as:

```text
http://127.0.0.1:8000/media/<path>
http://127.0.0.1:8000/static/<path>
```

`media/` is for user-managed uploads/assets. `static/` is for source static assets used by Django and admin tooling. `staticfiles/` is the deployment output created by `collectstatic`; it is not the source directory.

The React app normally serves its own bundled assets. It should use Django `/static/` only when it intentionally needs a Django/admin static asset. Never import Django admin CSS or JavaScript into the customer storefront as a substitute for React styling.

### If real uploads are required later

The current model must be extended before React can upload images. The backend work should add an `ImageField` (or a dedicated upload model), expose a staff-only multipart endpoint, validate file type and size, store the file under `MEDIA_ROOT`, and return its URL. The React request would then use `FormData` and must not set `Content-Type` manually:

```js
const form = new FormData();
form.append('image', selectedFile);

await fetch(`${API_BASE_URL}/admin/product-images/`, {
	method: 'POST',
	headers: { Authorization: `Token ${token}` },
	body: form,
});
```

That endpoint does not exist in the current codebase, so the snippet is an implementation target, not a currently callable route. For now, upload/manage files through the server or configured object storage, then save the resulting URL/path in the admin's `image` field.

## API reference

### Products

All product endpoints are public.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/products/` | List products |
| `GET` | `/api/products/<slug>/` | Product detail and recommendations; numeric IDs are also accepted |
| `GET` | `/api/products/categories/` | List categories |
| `GET` | `/api/products/trending-deals/` | Up to eight products marked as deals |
| `GET` | `/api/products/new-arrivals/` | New-arrival products |

Product list query parameters include:

- `search` or `q`
- `category` as a category slug, name, or ID
- `min_price` / `minPrice`
- `max_price` / `maxPrice`
- `is_new_arrival` / `new_arrival`
- `is_featured` / `featured`
- `sort=featured`, `low`, `high`, or `newest`

Products include `variants`. Add to cart using a variant ID when the shopper selected a specific variant; a product ID/slug can be used as a fallback to select its first variant.

### Cart

Cart routes are public and support both guests and authenticated customers.

| Method | Endpoint | Body/query | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/cart/` | `X-Cart-Session` for a guest | Get or create the current cart |
| `POST` | `/api/cart/items/` | `variant_id` or `product_id`, `quantity` | Add/increment an item |
| `PATCH` | `/api/cart/items/<id>/` | `quantity`, or `delta` | Set or adjust quantity |
| `DELETE` | `/api/cart/items/<id>/` | Optional product ID | Remove an item |
| `POST` | `/api/cart/clear/` | None | Empty the cart |

For a guest, persist the returned `session_key` and send it on every cart request:

```js
headers: { 'X-Cart-Session': sessionKey }
```

If no header is sent, Django may use its session cookie. An explicit stored `sessionKey` is easier for a separate React origin and avoids losing a guest cart between requests.

Cart responses contain both `items` and the compatibility alias `lines`, plus `total_items` and `subtotal`.

### Orders and checkout

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/orders/checkout/` | Public | Create an order from `items`, `cartLines`, or the current cart |
| `GET` | `/api/orders/` | Required | List the authenticated user's orders |
| `GET` | `/api/orders/<order_number>/` | Required | View a full owned order |
| `GET`, `POST` | `/api/orders/track/` | Public | Track an order using order number and email |
| `POST` | `/api/orders/validate-promo/` | Public | Validate a promo code against a subtotal |

Example checkout request:

```json
{
	"email": "buyer@example.com",
	"phone": "+2348000000000",
	"firstName": "Ada",
	"lastName": "Example",
	"fulfillment": "ship",
	"deliveryMethod": "standard",
	"address": "1 Example Street",
	"city": "Lagos",
	"state": "Lagos",
	"discountCode": "OMAWHITE",
	"items": [
		{ "variant_id": 3, "quantity": 2 }
	]
}
```

Allowed fulfillment values are `ship` and `pickup`. Delivery methods are `standard`, `express`, and `pickup`. The server calculates subtotal, delivery fee, five percent tax, discounts, and total from database values. The response includes an `order` object and a `payment_reference`.

Guest tracking requires both `order_number` (or `number`) and `email`. It intentionally returns sanitized tracking data without phone number or delivery address. Authenticated order detail is restricted to the owning account.

### Payments

Only the supported providers below should be exposed as checkout options in React:

- `PAYSTACK`
- `FLUTTERWAVE`

| Method | Endpoint | Body | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/payments/initialize/` | `order_number` or `order_id`, optional `email`, `provider`, `callback_url` | Create a provider checkout session |
| `POST` | `/api/payments/verify/` | `reference`, optional `provider`, `transaction_id` | Verify the provider transaction |

Initialization returns `checkout_url`, `payment_reference`, `amount`, `currency` (`NGN`), provider, and order number. Redirect the browser to the returned provider URL. Do not collect or send card details to this Django API.

After the provider redirects to the React callback route, call `/api/payments/verify/` with the payment reference. The backend verifies the transaction with the provider, checks currency and amount, and only then marks the payment successful and order confirmed.

The webhook routes are for payment providers, not React:

- `POST /api/payments/webhooks/paystack/`
- `POST /api/payments/webhooks/flutterwave/`

Configure these URLs in the respective provider dashboards. They require the provider signature/hash and should never be simulated by the browser.

## Recommended React integration

Create one API client so the base URL, JSON headers, token, cart session, and error handling are consistent:

```js
export async function apiFetch(path, options = {}) {
	const token = localStorage.getItem('authToken');
	const sessionKey = localStorage.getItem('cartSessionKey');
	const headers = new Headers(options.headers);

	if (!(options.body instanceof FormData)) {
		headers.set('Content-Type', 'application/json');
	}
	headers.set('Accept', 'application/json');
	if (token) headers.set('Authorization', `Token ${token}`);
	if (sessionKey) headers.set('X-Cart-Session', sessionKey);

	const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
	const data = await response.json().catch(() => null);
	if (!response.ok) {
		const error = new Error(data?.detail || data?.error || 'Request failed');
		error.status = response.status;
		error.data = data;
		throw error;
	}
	return data;
}
```

Suggested frontend state boundaries:

1. Fetch catalog data from products endpoints and keep the selected `variant.id` with each cart line.
2. Keep the guest `session_key` returned by cart responses and migrate to the authenticated cart after login according to the product decision for cart merging.
3. On checkout, send line items and customer details. Display totals from the server response.
4. Initialize payment, redirect to `checkout_url`, then verify on the callback route.
5. Refresh the order from the verification response before showing the confirmation screen.

Use `401` to clear stale authentication and return the user to login, `403` for permission failures, `404` for missing products/orders, and `400` to show field-level validation or checkout errors.

## Checkout and payment flow

```text
React catalog
		-> cart (guest X-Cart-Session or authenticated token)
		-> POST /api/orders/checkout/
		-> order PENDING + payment_reference
		-> POST /api/payments/initialize/
		-> redirect to Paystack or Flutterwave checkout_url
		-> provider redirects to React callback
		-> POST /api/payments/verify/
		-> confirmed order returned to React
```

The server is authoritative for inventory lookup, prices, taxes, delivery, discounts, payment amount, currency, and order status.

## Errors and frontend behavior

Common status codes:

| Status | Meaning | React behavior |
| --- | --- | --- |
| `200` | Successful read/update/action | Update local state |
| `201` | Resource created | Store returned resource/token |
| `400` | Invalid input or business rule | Show returned `error`, `errors`, or field messages |
| `401` | Missing/invalid authentication | Clear token and require login |
| `404` | Resource not found or unauthorized order | Show not-found state; do not expose details |
| `500` | Server/provider failure | Show retryable payment/server error |

Do not display raw `details` values from payment errors in a customer-facing UI in production. Log them only in a protected observability system.

## Admin workflow

1. Create a superuser with `python manage.py createsuperuser`.
2. Open `/admin/` on the Django origin.
3. Create categories, products, and product variants.
4. Enter a variant image URL or path in the `image` field.
5. Set price, stock, availability, badges, and featured/new-arrival flags.
6. Manage users, promo codes, orders, and payments through their registered admin screens.

The admin is a Django server-rendered application. It is not a React route and should remain on the backend origin. The `static/` source directory and `collectstatic` output support the admin's CSS and JavaScript; they are separate from React's `public/` or bundled assets.

## Production checklist

- Set `DEBUG=False` and a strong `SECRET_KEY`.
- Set `ALLOWED_HOSTS` to the API host.
- Set `CORS_ALLOWED_ORIGINS` to the exact React origin(s); do not use allow-all CORS.
- Serve `/media/` from durable storage or an object-storage/CDN domain.
- Run `python manage.py collectstatic` and serve `STATIC_ROOT` through the web server or CDN.
- Configure HTTPS and secure proxy headers.
- Configure Paystack and Flutterwave webhook URLs and secrets.
- Keep provider secret keys on the backend only; expose public keys only when the chosen provider's browser SDK requires them.
- Replace SQLite with a production database appropriate for the deployment.
- Add a real validated multipart upload endpoint before asking React to upload files directly.
- Test the complete checkout redirect, callback verification, and webhook paths in provider test mode.

## Verification

The repository includes `verify_api.py` for a broader API smoke test against seeded data. Run it from the activated virtual environment after migrations and seed data are available:

```powershell
python verify_api.py
```
