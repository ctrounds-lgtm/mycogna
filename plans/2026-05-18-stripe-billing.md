# Plan: Stripe Subscription Billing

**Created:** 2026-05-18
**Status:** Draft
**Request:** Add Stripe subscription billing to automate tier upgrades, handle per-seat Legacy pricing, and provide self-service cancellation.

---

## Overview

### What This Plan Accomplishes

Replaces the current manual Supabase tier-editing workflow with a full Stripe billing integration. Users sign up for a paid plan, complete a hosted Stripe Checkout (with promo code support), and are automatically upgraded. Cancellation is self-service from the portal, takes effect at period end, and triggers an automatic downgrade. Legacy Collection tiers (E/F) use per-seat billing tied directly to active code counts.

### Why This Matters

MyCogna cannot operate commercially without a payment layer. This plan makes every tier fully self-service — from first signup through cancellation — and removes the need for any manual database intervention. The per-seat model for Legacy tiers also creates a direct financial incentive around code activity, which aligns with the product's value delivery.

---

## Current State

### Relevant Existing Structure

- `apps/cogna/server.py` — All business logic. Tier enforcement via `storyteller_users.tier` and `users.tier`. Resend email SDK already integrated. Promo code create/deactivate endpoints exist.
- `apps/cogna/static/individual.html` — Pricing buttons use `/signup?plan=X` hrefs
- `apps/cogna/static/storyteller.html` — Upgrade modal with customizable CTA (`showUpgrade(title, body, ctaText, ctaHref)`)
- `apps/cogna/static/portal.html` — Portal UI; no billing section exists yet
- `apps/cogna/static/portal-signup.html` — Portal admin (E/F) signup entry point
- `apps/cogna/supabase_schema.sql` — Schema; `storyteller_users` and `users` both have `tier` columns; no billing columns yet
- `apps/cogna/requirements.txt` — No `stripe` package yet

### Two Billing Contexts

| Tier | Who pays | Account table | Entry point |
|------|----------|--------------|-------------|
| B ($5/mo) | Individual storyteller | `storyteller_users` | `/signup?plan=B` |
| C ($10/mo) | Individual storyteller | `storyteller_users` | `/signup?plan=C` |
| D ($15/mo) | Individual storyteller | `storyteller_users` | `/signup?plan=D` or `/individual#pricing` |
| E ($5/code/mo) | Portal admin | `users` | `/legacy#pricing` |
| F ($25/mo + $5/code/mo) | Portal admin | `users` | `/legacy#pricing` |

### Gaps or Problems Being Addressed

- Tier upgrades require manual Supabase edits — not viable commercially
- No payment collection, subscription management, or cancellation flow
- No confirmation emails explaining billing model (especially critical for E/F per-seat)
- Legacy tier per-seat billing requires code activity to drive Stripe quantity updates

---

## Proposed Changes

### Summary of Changes

- Add `stripe` to `requirements.txt`
- Add 5 Stripe billing columns to `storyteller_users`, 5 to `users` in schema
- Add Stripe config (env vars, price ID map) and helpers to `server.py`
- Add `POST /api/stripe/create-checkout-session` endpoint
- Add `POST /api/stripe/webhook` endpoint (4 event types)
- Add `POST /api/stripe/cancel` and `POST /api/stripe/reactivate` endpoints
- Add `GET /api/stripe/billing-status` endpoint for portal UI
- Add `POST /api/stripe/customer-portal` endpoint for payment method management
- Update `create_promo_code` and `deactivate_promo_code` to sync Stripe quantity for E/F
- Update `storyteller_signup` to redirect to Stripe after account creation when `plan` param is set
- Update portal signup to redirect to Stripe after account creation when `plan` param is set
- Update pricing buttons on `individual.html` and `legacy.html` for logged-in upgrade flow
- Update `storyteller.html` upgrade modal to hit checkout session endpoint
- Add billing section to `portal.html` with cancel/reactivate UI
- Add `_send_billing_confirmation_email()` function using existing Resend pattern

### New Files to Create

| File Path | Purpose |
|-----------|---------|
| *(none — all changes are to existing files)* | |

### Files to Modify

| File Path | Changes |
|-----------|---------|
| `apps/cogna/requirements.txt` | Add `stripe` |
| `apps/cogna/supabase_schema.sql` | Add 5 billing columns to each of `storyteller_users` and `users` |
| `apps/cogna/server.py` | Stripe config, 6 new endpoints, updates to signup + code endpoints, confirmation email |
| `apps/cogna/static/individual.html` | Pricing buttons: detect logged-in state, hit checkout session endpoint |
| `apps/cogna/static/legacy.html` | Pricing buttons: same pattern |
| `apps/cogna/static/storyteller.html` | Upgrade modal CTA → checkout session endpoint |
| `apps/cogna/static/portal.html` | Add billing/subscription management section |
| `apps/cogna/static/signup.html` | After account creation, redirect to Stripe if `plan` param set |
| `CLAUDE.md` | Update MyCogna section to document Stripe env vars and billing model |

---

## Design Decisions

### Key Decisions Made

1. **Account-first flow**: User creates account (tier A) → if `plan` param was set, immediately redirect to Stripe Checkout → webhook fires on success → tier updated. Reason: industry standard; ensures the user exists before payment, and a failed or abandoned payment leaves a valid (free) account rather than a broken state.

2. **Promo codes on every checkout**: `allow_promotion_codes=True` on all Stripe Checkout sessions. A 100% off coupon created in the Stripe dashboard allows internal testing without a credit card. No code changes required to use it.

3. **E tier checkout starts at quantity=1; first code auto-created in webhook**: Rather than a $0 initial checkout, the webhook creates one code automatically when the E/F subscription completes. This gives the user something immediately and avoids a confusing $0 first invoice. Subsequent codes increment the quantity.

4. **No mid-cycle proration**: All quantity changes (E/F code add/remove) use `proration_behavior='none'`. Changes take effect at the next billing cycle. Simpler billing, no surprise charges. Communicated clearly in the checkout description and confirmation email.

5. **Cancellation sets `cancel_at_period_end=True`**: User keeps access until period ends, then the webhook downgrades to tier A. No refunds, no mid-cycle cutoff. User can reactivate before period ends.

6. **`client_reference_id` format encodes user type**: Format `storyteller:{user_id}` or `portal:{email}` so the webhook knows which table to update without an extra DB lookup.

7. **Stripe Customer Portal for payment method updates**: Rather than building a custom payment method update UI, link users to Stripe's hosted Customer Portal. Requires one `POST /api/stripe/customer-portal` endpoint.

8. **`subscription_status` tracks 4 states**: `active`, `canceling` (cancel_at_period_end=true), `canceled`, `past_due`. UI reacts to each state differently. On `past_due`, warn user but do not immediately downgrade — Stripe retries payment automatically.

9. **Stripe price IDs in environment variables**: Differ between test and live mode. Store as `STRIPE_PRICE_B`, `STRIPE_PRICE_C`, etc. in Railway environment. Allows testing with Stripe test mode prices without code changes.

### Alternatives Considered

- **Pay-first flow** (Stripe checkout before account creation): Rejected because abandoned checkouts would leave no account, making recovery harder. Account-first is the industry standard.
- **Stripe metered billing** for E/F seat counting: Rejected in favor of quantity-based subscriptions, which are simpler to implement and give predictable invoices rather than usage-based surprises.
- **Building payment method UI ourselves**: Rejected in favor of Stripe Customer Portal, which handles PCI compliance and card validation automatically.

### Open Questions

1. **Should B/C also have portal access?** Currently B/C are individual storyteller tiers. If a B/C user also wants portal features, they'd need a separate portal account. Clarify whether B/C users ever need portal access.
2. **Stripe test mode vs. live mode**: Implementation will use test mode. Before going live, Railway env vars need to be swapped to live mode keys and real price IDs. Plan notes where this swap happens.

---

## Step-by-Step Tasks

### Step 1: Add Stripe to Requirements

**Actions:**
- Add `stripe` on a new line in `requirements.txt`

**Files affected:**
- `apps/cogna/requirements.txt`

---

### Step 2: Update Supabase Schema

Add billing columns to both `storyteller_users` (for B/C tiers) and `users` (for D/E/F tiers).

**Actions:**

Add the following `ALTER TABLE` statements to `supabase_schema.sql` in the existing migrations section:

```sql
-- Stripe billing columns for individual storyteller subscriptions (B/C tiers)
ALTER TABLE storyteller_users ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;
ALTER TABLE storyteller_users ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT;
ALTER TABLE storyteller_users ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'none';
ALTER TABLE storyteller_users ADD COLUMN IF NOT EXISTS subscription_period_end TIMESTAMPTZ;

-- Stripe billing columns for portal admin subscriptions (D/E/F tiers)
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_seat_item_id TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'none';
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_period_end TIMESTAMPTZ;
```

Note `stripe_seat_item_id` is only on `users` (portal admins), since only E/F tiers need per-seat quantity updates. `subscription_status` values: `none` (no subscription), `active`, `canceling`, `canceled`, `past_due`.

**Files affected:**
- `apps/cogna/supabase_schema.sql`

> **Manual step required**: After pushing, run these `ALTER TABLE` statements directly in the Supabase SQL editor. They are idempotent (`IF NOT EXISTS`) so safe to run multiple times.

---

### Step 3: Add Stripe Config and Helpers to server.py

Add Stripe initialization, price ID map, and two helper functions near the top of `server.py`, after the Resend config block.

**Actions:**

After the `# Resend` config block, add:

```python
# ----------------------------------------------------
# Stripe
# ----------------------------------------------------
try:
    import stripe as stripe_sdk
except ImportError:
    stripe_sdk = None

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Price IDs from Stripe dashboard (test or live depending on env)
STRIPE_PRICES = {
    "B": os.getenv("STRIPE_PRICE_B", ""),       # $5/month flat
    "C": os.getenv("STRIPE_PRICE_C", ""),       # $10/month flat
    "D": os.getenv("STRIPE_PRICE_D", ""),       # $15/month flat
    "E_SEAT": os.getenv("STRIPE_PRICE_E_SEAT", ""),  # $5/unit/month
    "F_FLAT": os.getenv("STRIPE_PRICE_F_FLAT", ""),  # $25/month flat
    "F_SEAT": os.getenv("STRIPE_PRICE_F_SEAT", ""),  # $5/unit/month
}

if stripe_sdk and STRIPE_SECRET_KEY:
    stripe_sdk.api_key = STRIPE_SECRET_KEY


def _update_seat_quantity(portal_email: str, delta: int) -> None:
    """Increment or decrement the Stripe seat quantity for an E/F portal user.
    Called when a promo code is created (delta=+1) or deactivated (delta=-1).
    No-ops gracefully if Stripe is not configured or user has no subscription.
    """
    if not stripe_sdk or not STRIPE_SECRET_KEY:
        return
    if not supabase:
        return
    try:
        r = supabase.table("users").select("stripe_subscription_id, stripe_seat_item_id, tier").eq("email", portal_email).limit(1).execute()
        if not r.data:
            return
        user = r.data[0]
        if user.get("tier") not in ("E", "F"):
            return
        sub_id = user.get("stripe_subscription_id")
        item_id = user.get("stripe_seat_item_id")
        if not sub_id or not item_id:
            return
        item = stripe_sdk.SubscriptionItem.retrieve(item_id)
        new_qty = max(0, (item.get("quantity") or 0) + delta)
        stripe_sdk.SubscriptionItem.modify(
            item_id,
            quantity=new_qty,
            proration_behavior="none",
        )
    except Exception as e:
        print(f"[Stripe] seat quantity update failed for {portal_email}: {e}")


def _send_billing_confirmation_email(email: str, tier: str, first_name: str = "") -> None:
    """Send a post-checkout confirmation email explaining the billing model."""
    if not resend_sdk or not RESEND_API_KEY:
        return
    tier_names = {
        "B": "Storyteller Unlimited",
        "C": "Storyteller + Memoir Builder",
        "D": "AI Companion",
        "E": "Legacy Collection",
        "F": "Legacy Collection + Book Builder",
    }
    tier_name = tier_names.get(tier, tier)
    greeting = f"Hi {first_name}!" if first_name else "Hi!"

    if tier in ("B", "C", "D"):
        body_html = f"""
        <p>{greeting}</p>
        <p>You're now subscribed to <strong>MyCogna {tier_name}</strong>.</p>
        <p>Your subscription renews monthly. You can manage or cancel your subscription
        at any time from the <a href="https://mycogna.org/portal">portal</a>.</p>
        <p>If you have any questions, just reply to this email.</p>
        """
    elif tier == "E":
        body_html = f"""
        <p>{greeting}</p>
        <p>You're now subscribed to <strong>MyCogna {tier_name}</strong>.</p>
        <p><strong>How your billing works:</strong><br>
        You're charged <strong>$5/month per active access code</strong>.
        We've created your first code — it's ready to use in your
        <a href="https://mycogna.org/portal">portal</a>.</p>
        <p>Each new code you generate adds $5/month starting on your next billing date.
        Deactivating a code removes it from your next billing cycle.
        There are no mid-month adjustments — changes take effect at renewal.</p>
        <p>You can cancel at any time from the portal. Your codes stay active until
        the end of your current billing period.</p>
        """
    else:  # F
        body_html = f"""
        <p>{greeting}</p>
        <p>You're now subscribed to <strong>MyCogna {tier_name}</strong>.</p>
        <p><strong>How your billing works:</strong><br>
        Your subscription includes a <strong>$25/month base fee</strong> for AI deepening
        and the book-building workspace, plus <strong>$5/month per active access code</strong>.
        We've created your first code — it's ready in your
        <a href="https://mycogna.org/portal">portal</a>.</p>
        <p>Each new code adds $5/month starting on your next billing date.
        Deactivating a code removes it from your next billing cycle.
        No mid-month adjustments — changes take effect at renewal.</p>
        <p>You can cancel at any time from the portal. Access continues until
        the end of your current billing period.</p>
        """

    try:
        resend_sdk.Emails.send({
            "from": RESEND_FROM,
            "to": [email],
            "subject": f"You're subscribed to MyCogna {tier_name}",
            "html": body_html,
        })
    except Exception as e:
        print(f"[Resend] billing confirmation failed for {email}: {e}")
```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 4: Add `POST /api/stripe/create-checkout-session`

This endpoint creates a Stripe Checkout session for the requested tier and returns the URL to redirect to. It is called by the frontend immediately after account creation (if `plan` param was set) or when an existing user clicks an upgrade button.

Add this endpoint after the existing auth/session endpoints block:

```python
class StripeCheckoutRequest(BaseModel):
    tier: str  # B, C, D, E, F
    user_type: str = "storyteller"  # "storyteller" or "portal"


@app.post("/api/stripe/create-checkout-session")
async def create_checkout_session(
    payload: StripeCheckoutRequest,
    authorization: Optional[str] = Header(default=None),
):
    if not stripe_sdk or not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Payment system not configured.")

    tier = payload.tier.upper()
    base_url = os.getenv("APP_BASE_URL", "https://mycogna.org")

    # Auth: storyteller or portal user
    if payload.user_type == "storyteller":
        user = _auth_storyteller_user(authorization)
        client_ref = f"storyteller:{user['id']}"
        customer_email = user["email"]
        first_name = user.get("first_name", "")
    else:
        user = _auth_user(authorization)
        client_ref = f"portal:{user['email']}"
        customer_email = user["email"]
        first_name = user.get("first_name", "")

    # Build line items based on tier
    if tier == "B":
        line_items = [{"price": STRIPE_PRICES["B"], "quantity": 1}]
        success_path = "/storyteller"
        description = "Unlimited story recordings, custom interview questions."
    elif tier == "C":
        line_items = [{"price": STRIPE_PRICES["C"], "quantity": 1}]
        success_path = "/storyteller"
        description = "Unlimited recordings plus AI-assisted memoir assembly and editing."
    elif tier == "D":
        line_items = [{"price": STRIPE_PRICES["D"], "quantity": 1}]
        success_path = "/storyteller"
        description = "Build a Cogna voice companion for a loved one."
    elif tier == "E":
        line_items = [{"price": STRIPE_PRICES["E_SEAT"], "quantity": 1}]
        success_path = "/portal"
        description = (
            "$5/month per active access code. Your first code is included. "
            "Each code you create adds $5/month. Deactivating a code removes it "
            "from your next billing cycle — no mid-month adjustments."
        )
    elif tier == "F":
        line_items = [
            {"price": STRIPE_PRICES["F_FLAT"], "quantity": 1},
            {"price": STRIPE_PRICES["F_SEAT"], "quantity": 1},
        ]
        success_path = "/portal"
        description = (
            "$25/month for AI deepening and book-building tools, plus $5/month "
            "per active access code. Your first code is included."
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown tier: {tier}")

    session = stripe_sdk.checkout.Session.create(
        mode="subscription",
        line_items=line_items,
        customer_email=customer_email,
        client_reference_id=client_ref,
        allow_promotion_codes=True,
        subscription_data={
            "metadata": {
                "tier": tier,
                "user_type": payload.user_type,
                "description": description,
            }
        },
        metadata={"tier": tier, "user_type": payload.user_type},
        success_url=f"{base_url}{success_path}?checkout=success",
        cancel_url=f"{base_url}{success_path}?checkout=canceled",
    )
    return {"url": session.url}
```

Add `APP_BASE_URL` to Railway env vars (value: `https://mycogna.org`).

**Files affected:**
- `apps/cogna/server.py`

---

### Step 5: Add `POST /api/stripe/webhook`

This is the heart of the integration. It must be unauthenticated (Stripe calls it directly) but verified using the Stripe webhook signing secret.

```python
@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    if not stripe_sdk or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook not configured.")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe_sdk.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except stripe_sdk.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    etype = event["type"]
    data = event["data"]["object"]

    if etype == "checkout.session.completed":
        _handle_checkout_completed(data)
    elif etype == "customer.subscription.updated":
        _handle_subscription_updated(data)
    elif etype == "customer.subscription.deleted":
        _handle_subscription_deleted(data)
    elif etype == "invoice.payment_failed":
        _handle_payment_failed(data)

    return {"ok": True}


def _handle_checkout_completed(session: dict) -> None:
    """Upgrade user tier after successful Stripe checkout."""
    client_ref = session.get("client_reference_id", "")
    tier = (session.get("metadata") or {}).get("tier", "")
    user_type = (session.get("metadata") or {}).get("user_type", "storyteller")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not client_ref or not tier:
        print(f"[Stripe webhook] checkout.session.completed missing ref or tier: {session.get('id')}")
        return

    # Retrieve subscription to get period_end and item IDs
    try:
        sub = stripe_sdk.Subscription.retrieve(subscription_id)
        period_end_ts = sub["current_period_end"]
        period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc).isoformat()
        items = sub["items"]["data"]
    except Exception as e:
        print(f"[Stripe webhook] failed to retrieve subscription {subscription_id}: {e}")
        return

    # Find the seat item ID for E/F tiers
    seat_price_ids = {STRIPE_PRICES.get("E_SEAT"), STRIPE_PRICES.get("F_SEAT")} - {None, ""}
    seat_item_id = next((item["id"] for item in items if item["price"]["id"] in seat_price_ids), None)

    updates = {
        "tier": tier,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "subscription_status": "active",
        "subscription_period_end": period_end,
    }

    first_name = ""

    if user_type == "storyteller" and client_ref.startswith("storyteller:"):
        user_id = client_ref.split(":", 1)[1]
        if supabase:
            r = supabase.table("storyteller_users").select("email, first_name").eq("id", user_id).limit(1).execute()
            if r.data:
                first_name = r.data[0].get("first_name", "")
                email = r.data[0]["email"]
                supabase.table("storyteller_users").update(updates).eq("id", user_id).execute()
                _send_billing_confirmation_email(email, tier, first_name)

    elif user_type == "portal" and client_ref.startswith("portal:"):
        email = client_ref.split(":", 1)[1]
        if supabase:
            r = supabase.table("users").select("first_name").eq("email", email).limit(1).execute()
            if r.data:
                first_name = r.data[0].get("first_name", "")
            portal_updates = {**updates}
            if seat_item_id:
                portal_updates["stripe_seat_item_id"] = seat_item_id
            supabase.table("users").update(portal_updates).eq("email", email).execute()

            # Auto-create first code for E/F tiers
            if tier in ("E", "F"):
                code_tier = "E" if tier == "E" else "F"
                code = _generate_story_promo_code(code_tier)
                record = {
                    "code": code,
                    "tier": code_tier,
                    "description": "First code (auto-created)",
                    "active": True,
                    "created_by": email,
                    "created_at": _utc_now(),
                }
                try:
                    supabase.table("promo_codes").insert(record).execute()
                except Exception as e:
                    print(f"[Stripe webhook] failed to auto-create first code for {email}: {e}")

            _send_billing_confirmation_email(email, tier, first_name)


def _handle_subscription_updated(sub: dict) -> None:
    """Sync tier and status when Stripe subscription changes."""
    customer_id = sub.get("customer")
    status = sub.get("status")  # active, past_due, canceled, etc.
    cancel_at_period_end = sub.get("cancel_at_period_end", False)
    period_end_ts = sub.get("current_period_end")
    period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc).isoformat() if period_end_ts else None

    stripe_status = "canceling" if cancel_at_period_end else ("past_due" if status == "past_due" else "active")
    updates = {"subscription_status": stripe_status, "subscription_period_end": period_end}

    if supabase:
        supabase.table("storyteller_users").update(updates).eq("stripe_customer_id", customer_id).execute()
        supabase.table("users").update(updates).eq("stripe_customer_id", customer_id).execute()


def _handle_subscription_deleted(sub: dict) -> None:
    """Downgrade user to tier A when subscription is fully canceled."""
    customer_id = sub.get("customer")
    updates = {
        "tier": "A",
        "stripe_subscription_id": None,
        "stripe_customer_id": None,
        "subscription_status": "canceled",
        "subscription_period_end": None,
    }
    if supabase:
        supabase.table("storyteller_users").update(updates).eq("stripe_customer_id", customer_id).execute()
        portal_updates = {**updates, "stripe_seat_item_id": None}
        supabase.table("users").update(portal_updates).eq("stripe_customer_id", customer_id).execute()


def _handle_payment_failed(invoice: dict) -> None:
    """Mark subscription as past_due on failed payment. Do not downgrade — Stripe retries."""
    customer_id = invoice.get("customer")
    if supabase:
        supabase.table("storyteller_users").update({"subscription_status": "past_due"}).eq("stripe_customer_id", customer_id).execute()
        supabase.table("users").update({"subscription_status": "past_due"}).eq("stripe_customer_id", customer_id).execute()
```

Note: `Request` from FastAPI is already imported. The webhook endpoint must **not** be wrapped in authentication middleware.

**Files affected:**
- `apps/cogna/server.py`

---

### Step 6: Add Cancel, Reactivate, Billing Status, and Customer Portal Endpoints

```python
@app.post("/api/stripe/cancel")
async def cancel_subscription(authorization: Optional[str] = Header(default=None)):
    """Cancel at period end. User keeps access until period ends."""
    if not stripe_sdk or not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Payment system not configured.")

    # Try storyteller auth first, then portal
    sub_id = None
    period_end = None
    try:
        user = _auth_storyteller_user(authorization)
        sub_id = user.get("stripe_subscription_id")
    except HTTPException:
        user = _auth_user(authorization)
        sub_id = user.get("stripe_subscription_id")

    if not sub_id:
        raise HTTPException(status_code=400, detail="No active subscription found.")

    try:
        sub = stripe_sdk.Subscription.modify(sub_id, cancel_at_period_end=True)
        period_end_ts = sub["current_period_end"]
        period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc).isoformat()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {e}")

    # Update local status (webhook will also fire)
    if supabase:
        updates = {"subscription_status": "canceling", "subscription_period_end": period_end}
        supabase.table("storyteller_users").update(updates).eq("stripe_subscription_id", sub_id).execute()
        supabase.table("users").update(updates).eq("stripe_subscription_id", sub_id).execute()

    return {"ok": True, "period_end": period_end}


@app.post("/api/stripe/reactivate")
async def reactivate_subscription(authorization: Optional[str] = Header(default=None)):
    """Reverse cancel_at_period_end before it takes effect."""
    if not stripe_sdk or not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Payment system not configured.")

    sub_id = None
    try:
        user = _auth_storyteller_user(authorization)
        sub_id = user.get("stripe_subscription_id")
    except HTTPException:
        user = _auth_user(authorization)
        sub_id = user.get("stripe_subscription_id")

    if not sub_id:
        raise HTTPException(status_code=400, detail="No active subscription found.")

    try:
        stripe_sdk.Subscription.modify(sub_id, cancel_at_period_end=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {e}")

    if supabase:
        updates = {"subscription_status": "active"}
        supabase.table("storyteller_users").update(updates).eq("stripe_subscription_id", sub_id).execute()
        supabase.table("users").update(updates).eq("stripe_subscription_id", sub_id).execute()

    return {"ok": True}


@app.get("/api/stripe/billing-status")
async def billing_status(authorization: Optional[str] = Header(default=None)):
    """Return billing info for the portal subscription management UI."""
    try:
        user = _auth_storyteller_user(authorization)
        return {
            "tier": user.get("tier", "A"),
            "subscription_status": user.get("subscription_status", "none"),
            "subscription_period_end": user.get("subscription_period_end"),
            "user_type": "storyteller",
        }
    except HTTPException:
        pass
    user = _auth_user(authorization)
    # For E/F: count active codes to show current monthly total
    active_code_count = 0
    if supabase and user.get("tier") in ("E", "F"):
        r = supabase.table("promo_codes").select("code").eq("created_by", user["email"]).eq("active", True).execute()
        active_code_count = len(r.data or [])
    return {
        "tier": user.get("tier", "A"),
        "subscription_status": user.get("subscription_status", "none"),
        "subscription_period_end": user.get("subscription_period_end"),
        "active_code_count": active_code_count,
        "user_type": "portal",
    }


@app.post("/api/stripe/customer-portal")
async def stripe_customer_portal(authorization: Optional[str] = Header(default=None)):
    """Return a Stripe Customer Portal URL for payment method management."""
    if not stripe_sdk or not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Payment system not configured.")

    customer_id = None
    try:
        user = _auth_storyteller_user(authorization)
        customer_id = user.get("stripe_customer_id")
    except HTTPException:
        user = _auth_user(authorization)
        customer_id = user.get("stripe_customer_id")

    if not customer_id:
        raise HTTPException(status_code=400, detail="No billing account found.")

    base_url = os.getenv("APP_BASE_URL", "https://mycogna.org")
    try:
        session = stripe_sdk.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{base_url}/portal",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {e}")

    return {"url": session.url}
```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 7: Update Code Create/Deactivate to Sync Stripe Quantity

**In `create_promo_code`** — after the code is inserted, add:

```python
    # Sync Stripe seat quantity for E/F portal users
    _update_seat_quantity(user["email"], delta=+1)
    return {"code": code}
```

**In `deactivate_promo_code`** — after updating active=False, add:

```python
    # Find code owner and sync Stripe seat quantity
    try:
        if supabase:
            r = supabase.table("promo_codes").select("created_by").eq("code", code).limit(1).execute()
            if r.data:
                _update_seat_quantity(r.data[0]["created_by"], delta=-1)
    except Exception:
        pass
    return {"ok": True}
```

Note: `_update_seat_quantity` is a no-op for non-E/F users, so this is safe to add unconditionally.

**Files affected:**
- `apps/cogna/server.py`

---

### Step 8: Update Signup Flow to Redirect to Stripe

**In `storyteller_signup`**, after the user is created and session token returned, add logic to return a `checkout_url` when a paid plan was requested:

At the end of the function, change the return from:
```python
    return {"token": token, "user": {...}}
```
to:
```python
    result = {"token": token, "user": {...}}

    # If a paid plan was requested, create a checkout session URL
    plan_hint = (payload.plan or "").strip().upper()
    if plan_hint in ("B", "C") and stripe_sdk and STRIPE_SECRET_KEY:
        try:
            base_url = os.getenv("APP_BASE_URL", "https://mycogna.org")
            session = stripe_sdk.checkout.Session.create(
                mode="subscription",
                line_items=[{"price": STRIPE_PRICES[plan_hint], "quantity": 1}],
                customer_email=payload.email,
                client_reference_id=f"storyteller:{new_user_id}",
                allow_promotion_codes=True,
                metadata={"tier": plan_hint, "user_type": "storyteller"},
                success_url=f"{base_url}/storyteller?checkout=success",
                cancel_url=f"{base_url}/storyteller?checkout=canceled",
            )
            result["checkout_url"] = session.url
        except Exception as e:
            print(f"[Stripe] checkout session creation failed: {e}")

    return result
```

**In `signup.html`**: After receiving the signup response, check for `checkout_url` and redirect:

```javascript
const data = await res.json();
if (data.checkout_url) {
    // Store token first so it's available after redirect back
    localStorage.setItem('st_token', data.token);
    localStorage.setItem('st_email', data.user.email);
    localStorage.setItem('st_first_name', data.user.first_name || '');
    localStorage.setItem('st_tier', data.user.tier || 'A');
    window.location = data.checkout_url;
} else {
    // Existing free-tier flow
    localStorage.setItem('st_token', data.token);
    // ... rest of existing logic
}
```

**Files affected:**
- `apps/cogna/server.py`
- `apps/cogna/static/signup.html`

---

### Step 9: Update Pricing Buttons for Logged-In Upgrade Flow

Buttons on `/individual` (and equivalent on `/family`) currently send all users to `/signup?plan=X`. For already-logged-in users, they should go directly to Stripe checkout instead.

**In `individual.html`**, replace the static `href` on paid pricing buttons with an `onclick` handler:

```html
<!-- Before -->
<a href="/signup?plan=B" class="pricing-btn pricing-btn-fill">Start recording</a>

<!-- After -->
<a href="/signup?plan=B" class="pricing-btn pricing-btn-fill"
   onclick="return handlePricingClick(event, 'B', 'storyteller')">Start recording</a>
```

Add a shared `<script>` block at the bottom of the page:

```javascript
async function handlePricingClick(event, tier, userType) {
    const token = localStorage.getItem('st_token') || localStorage.getItem('portal_token');
    if (!token) return true; // Let href handle it — not logged in, go to signup

    event.preventDefault();
    try {
        const res = await fetch('/api/stripe/create-checkout-session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token,
            },
            body: JSON.stringify({tier, user_type: userType}),
        });
        const data = await res.json();
        if (data.url) window.location = data.url;
    } catch (e) {
        // Fall back to href
        window.location = event.currentTarget.href;
    }
    return false;
}
```

Apply the same pattern to `/legacy.html` for E/F tier buttons (with `userType = 'portal'`).

**Files affected:**
- `apps/cogna/static/individual.html`
- `apps/cogna/static/legacy.html`
- `apps/cogna/static/family.html` (if pricing buttons exist there)

---

### Step 10: Update Storyteller Upgrade Modal

The upgrade modal CTA currently links to `/individual#pricing`. For logged-in users, it should hit the checkout session endpoint directly.

**In `storyteller.html`**, update the `showUpgrade` method to pass a tier and use the checkout endpoint when appropriate:

```javascript
async goToCheckout(tier) {
    const token = stState.authToken;
    if (!token) { window.location = '/individual#pricing'; return; }
    try {
        const res = await fetch(window.location.origin + '/api/stripe/create-checkout-session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token,
            },
            body: JSON.stringify({tier, user_type: 'storyteller'}),
        });
        const data = await res.json();
        if (data.url) window.location = data.url;
    } catch (e) {
        window.location = '/individual#pricing';
    }
},
```

In each `showUpgrade()` call where a specific tier is known (e.g. tier A monthly limit hit → upgrade to B), replace the `ctaHref` with an `onclick`:

```javascript
// Replace href-based CTA with checkout call
document.getElementById('upgradeCta').onclick = () => st.goToCheckout('B');
document.getElementById('upgradeCta').href = '#';
```

**Files affected:**
- `apps/cogna/static/storyteller.html`

---

### Step 11: Add Billing Section to portal.html

Add a "Subscription" section to the portal, visible to all logged-in portal users. This section shows current plan, billing details, and cancel/reactivate controls.

**Location**: Insert as a new panel section near the top of the portal dashboard, before the Cognas/user-codes sections. Give it an `id="billingSection"`.

**HTML to add:**

```html
<div class="panel" id="billingSection" style="display:none;">
  <h3 class="panel-title">Subscription</h3>
  <div id="billingDetails">
    <p class="loading-msg">Loading billing info…</p>
  </div>
</div>
```

**JavaScript to add** (in the portal's `loadDashboard` or `init` function, called after auth):

```javascript
async function loadBillingSection() {
    try {
        const res = await fetch('/api/stripe/billing-status', {
            headers: {'Authorization': 'Bearer ' + portalToken}
        });
        if (!res.ok) return;
        const data = await res.json();
        renderBillingSection(data);
    } catch (e) { /* silent */ }
}

function renderBillingSection(data) {
    const section = document.getElementById('billingSection');
    const details = document.getElementById('billingDetails');
    if (!section || !details) return;

    const tier = data.tier || 'A';
    if (tier === 'A') { section.style.display = 'none'; return; }

    section.style.display = '';

    const tierNames = {B:'Storyteller Unlimited ($5/mo)', C:'Storyteller + Memoir Builder ($10/mo)',
                       D:'AI Companion ($15/mo)', E:'Legacy Collection ($5/code/mo)',
                       F:'Legacy Collection + Book Builder ($25/mo + $5/code/mo)'};
    const status = data.subscription_status;
    const periodEnd = data.subscription_period_end
        ? new Date(data.subscription_period_end).toLocaleDateString('en-US', {month:'long', day:'numeric', year:'numeric'})
        : null;

    let statusHtml = '';
    if (status === 'canceling') {
        statusHtml = `<p class="billing-warning">Your subscription will end on <strong>${periodEnd}</strong>.
            You'll keep access until then.
            <button class="link-btn" onclick="reactivateSubscription()">Keep my subscription</button></p>`;
    } else if (status === 'past_due') {
        statusHtml = `<p class="billing-warning">⚠ Your last payment failed.
            <button class="link-btn" onclick="openCustomerPortal()">Update payment method</button></p>`;
    } else if (status === 'canceled') {
        statusHtml = `<p class="billing-warning">Your subscription has ended.</p>`;
    } else {
        const renewLabel = periodEnd ? `Renews ${periodEnd}` : '';
        statusHtml = `<p class="billing-meta">${renewLabel}</p>`;
    }

    let seatHtml = '';
    if ((tier === 'E' || tier === 'F') && data.active_code_count !== undefined) {
        const seatCost = data.active_code_count * 5;
        const total = tier === 'F' ? 25 + seatCost : seatCost;
        seatHtml = `<p class="billing-meta">${data.active_code_count} active code${data.active_code_count !== 1 ? 's' : ''} — $${total}/month current total</p>`;
    }

    const cancelBtn = (status === 'active' || status === 'past_due')
        ? `<button class="btn-sm btn-sm-outline" onclick="cancelSubscription()" style="margin-top:12px;">Cancel subscription</button>`
        : '';
    const portalBtn = `<button class="link-btn" style="margin-top:8px;display:block;" onclick="openCustomerPortal()">Manage payment method</button>`;

    details.innerHTML = `
        <p class="billing-plan"><strong>${tierNames[tier] || tier}</strong></p>
        ${seatHtml}
        ${statusHtml}
        ${cancelBtn}
        ${portalBtn}`;
}

async function cancelSubscription() {
    if (!confirm('Cancel your subscription? You\'ll keep access until the end of your current billing period.')) return;
    try {
        const res = await fetch('/api/stripe/cancel', {method:'POST', headers:{'Authorization':'Bearer '+portalToken}});
        const data = await res.json();
        await loadBillingSection();
    } catch (e) { alert('Could not cancel. Please try again.'); }
}

async function reactivateSubscription() {
    try {
        await fetch('/api/stripe/reactivate', {method:'POST', headers:{'Authorization':'Bearer '+portalToken}});
        await loadBillingSection();
    } catch (e) { alert('Could not reactivate. Please try again.'); }
}

async function openCustomerPortal() {
    try {
        const res = await fetch('/api/stripe/customer-portal', {method:'POST', headers:{'Authorization':'Bearer '+portalToken}});
        const data = await res.json();
        if (data.url) window.location = data.url;
    } catch (e) { alert('Could not open billing portal.'); }
}
```

**CSS to add:**

```css
.billing-plan { font-size: 15px; margin-bottom: 4px; }
.billing-meta { font-size: 13px; color: var(--ink-muted); margin: 4px 0; }
.billing-warning { font-size: 13px; color: #b45309; background: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px; padding: 10px 14px; margin-top: 8px; }
```

**Files affected:**
- `apps/cogna/static/portal.html`

---

### Step 12: Handle `?checkout=success` and `?checkout=canceled` in Frontend

When Stripe redirects back to `/storyteller?checkout=success` or `/portal?checkout=success`, show an appropriate confirmation message.

**In `storyteller.html`**, in the `window.addEventListener('load', ...)` block:

```javascript
const params = new URLSearchParams(window.location.search);
if (params.get('checkout') === 'success') {
    // Re-fetch /me to pick up the new tier from the webhook
    // (webhook may have fired; if not yet, show a friendly message)
    setTimeout(async () => {
        try {
            const res = await fetch(API + '/me', {headers:{'Authorization':'Bearer '+stState.authToken}});
            if (res.ok) {
                const d = await res.json();
                stState.tier = d.user.tier || 'A';
                localStorage.setItem('st_tier', stState.tier);
            }
        } catch (_) {}
        showScreen('screenHome');
        // Show a brief success notice
        const notice = document.createElement('div');
        notice.style = 'background:var(--gold-light);border:1px solid var(--gold);border-radius:10px;padding:14px 18px;margin-bottom:16px;font-weight:600;';
        notice.textContent = "You're all set! Your plan has been upgraded.";
        document.querySelector('#screenHome .page')?.prepend(notice);
        setTimeout(() => notice.remove(), 6000);
    }, 2000); // 2s delay to let webhook fire
    // Remove query param from URL
    window.history.replaceState({}, '', '/storyteller');
}
```

Apply the same pattern to `/portal` for portal users.

**Files affected:**
- `apps/cogna/static/storyteller.html`
- `apps/cogna/static/portal.html`

---

### Step 13: Update CLAUDE.md

Add Stripe environment variables to the MyCogna deploy section and document the billing model.

**Add to the Deploy process section:**

```markdown
**Stripe environment variables (Railway):**
- `STRIPE_SECRET_KEY` — Stripe secret key (test: `sk_test_...`, live: `sk_live_...`)
- `STRIPE_WEBHOOK_SECRET` — From Stripe dashboard > Webhooks > signing secret
- `STRIPE_PRICE_B` — Price ID for $5/month (Storyteller Unlimited)
- `STRIPE_PRICE_C` — Price ID for $10/month (Storyteller + Memoir Builder)
- `STRIPE_PRICE_D` — Price ID for $15/month (AI Companion)
- `STRIPE_PRICE_E_SEAT` — Price ID for $5/unit/month (Legacy Collection per-seat)
- `STRIPE_PRICE_F_FLAT` — Price ID for $25/month (Legacy + Book Builder flat)
- `STRIPE_PRICE_F_SEAT` — Price ID for $5/unit/month (Legacy + Book Builder per-seat)
- `APP_BASE_URL` — `https://mycogna.org` (used for Stripe redirect URLs)
```

**Files affected:**
- `CLAUDE.md`

---

## Connections & Dependencies

### Files That Reference This Area

- `apps/cogna/static/individual.html` — pricing buttons
- `apps/cogna/static/legacy.html` — E/F pricing buttons
- `apps/cogna/static/family.html` — may have pricing buttons
- `apps/cogna/static/storyteller.html` — upgrade modal
- `apps/cogna/static/signup.html` — account creation flow
- `apps/cogna/static/portal.html` — subscription management
- `apps/cogna/static/portal-signup.html` — portal account creation (may need same Stripe redirect treatment as signup.html for D/E/F tiers — verify during implementation)

### Updates Needed for Consistency

- Stripe webhook must be registered in the Stripe dashboard pointing to `https://mycogna-production.up.railway.app/api/stripe/webhook` with events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`
- Stripe Customer Portal must be enabled in the Stripe dashboard (Billing > Customer Portal settings)
- `vercel.json` rewrites already route `/api/(.*)` to Railway — no change needed

### Impact on Existing Workflows

- `create_promo_code` and `deactivate_promo_code`: new Stripe side-effect added; no-ops gracefully if Stripe not configured
- `storyteller_signup`: new optional `checkout_url` in response; existing free-tier flow unchanged
- Tier enforcement: unchanged — `storyteller_users.tier` and `users.tier` remain the source of truth; Stripe is only the mechanism that updates them

---

## Validation Checklist

### Stripe Dashboard Setup
- [ ] 6 products and prices created (B/C/D flat + E_SEAT/F_FLAT/F_SEAT)
- [ ] Price IDs added to Railway environment variables
- [ ] 100% off test coupon created (e.g. `MYCOGNA-TEST`)
- [ ] Webhook endpoint registered pointing to Railway URL
- [ ] Customer Portal enabled in Stripe dashboard

### Backend
- [ ] `stripe` package in requirements.txt
- [ ] `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, all price IDs, `APP_BASE_URL` set in Railway
- [ ] Supabase schema migrations run (5 columns on `storyteller_users`, 5 on `users`)
- [ ] `POST /api/stripe/create-checkout-session` returns a valid Stripe URL
- [ ] `POST /api/stripe/webhook` returns 200 for each of the 4 event types
- [ ] Checkout with `MYCOGNA-TEST` promo code upgrades tier correctly in Supabase
- [ ] Code creation for E/F user increments Stripe subscription quantity
- [ ] Code deactivation for E/F user decrements Stripe subscription quantity
- [ ] Cancel sets `cancel_at_period_end=True` and `subscription_status='canceling'`
- [ ] Reactivate reverses cancel correctly
- [ ] Confirmation email received after checkout

### Frontend
- [ ] Logged-in tier A user clicking upgrade goes directly to Stripe (not signup)
- [ ] Non-logged-in user clicking pricing button goes to `/signup?plan=X`
- [ ] After checkout success redirect, tier is updated in UI within ~5 seconds
- [ ] Portal billing section shows correct plan, period end, and cost for E/F users
- [ ] Cancel button in portal shows confirmation dialog then updates UI to "cancels on [date]"
- [ ] Reactivate button restores "active" status display
- [ ] "Manage payment method" opens Stripe Customer Portal

---

## Success Criteria

The implementation is complete when:

1. A new user can go from `/individual` → pick a paid plan → create account → complete Stripe checkout (including with the `MYCOGNA-TEST` promo code for $0) → land back on the app with the correct tier active — without any manual Supabase intervention.
2. An existing tier A user can click "Upgrade" in the app → complete Stripe checkout → return to the app with their tier upgraded.
3. A portal admin on E/F tier can create and deactivate codes, and their Stripe subscription quantity updates automatically with each action.
4. Any subscribed user can cancel self-service from the portal, see a clear "access ends on [date]" message, and be automatically downgraded to tier A by the webhook after that date.
5. Every checkout — new signup or upgrade — has a working promo code box.

---

## Notes

- **Test mode first**: Implement against Stripe test mode. All price IDs and keys swap to live equivalents when ready to go live — no code changes required.
- **D tier on `storyteller_users`**: D (AI Companion) is an individual tool, so billing runs through `storyteller_users` alongside B and C. `user_type: 'storyteller'` for D in all checkout sessions and webhook handlers. Easy to move post-launch if needed — just update the webhook lookup and migrate `stripe_customer_id` values for existing D subscribers with a single SQL statement.
- **`portal-signup.html`**: This file was not fully researched. During implementation, check whether it needs the same Stripe redirect treatment as `signup.html` for E/F tier signups. The pattern is identical — return `checkout_url` from the signup endpoint and redirect if present.
- **Proration on plan changes**: This plan only covers initial signups and cancellations. If a user wants to upgrade from B → C mid-cycle, that's a separate feature (Stripe subscription update with optional proration). Not in scope here.
- **Stripe Customer Portal**: Must be configured in the Stripe dashboard (Billing > Customer Portal) to allow customers to view invoices and update payment methods. The portal link uses `return_url = /portal`.
- **Webhook reliability**: Stripe will retry failed webhook deliveries for up to 72 hours. The webhook handler is idempotent (upserts, not inserts), so duplicate events are safe.
