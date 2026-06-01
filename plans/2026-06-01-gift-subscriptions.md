# Plan: Gift Subscription System

**Created:** 2026-06-01
**Status:** Implemented
**Request:** Build a complete gift subscription system so givers can purchase MyCogna access for recipients, targeting Father's Day 2026 (June 21) launch.

---

## Overview

### What This Plan Accomplishes

A gift giver visits `mycogna.org/gift`, selects a tier (B, C, or D) and duration (1, 3, 6, or 12 months), pays via Stripe one-time charge, and receives a unique `GIFT-XXXX-XXXX` code by email. The recipient enters that code at signup to create a portal admin account with the gifted tier active — no payment required. When the gift expires, a banner prompts them to add a payment method to continue.

### Why This Matters

Gift subscriptions unlock a recurring seasonal revenue channel (Father's Day, Mother's Day, Christmas, birthdays) and lower the barrier for new users whose first experience is a gift rather than a purchase decision. This is a self-contained feature that does not touch existing subscription billing logic.

---

## Current State

### Relevant Existing Structure

- `apps/cogna/server.py` — Stripe checkout, webhook handler (`_handle_checkout_completed`), auth/register, `_send_billing_confirmation_email`, promo code generation pattern
- `apps/cogna/static/portal-signup.html` — Plan picker with `selectPlan()`, `handleSignup()`, calls `POST /api/auth/register`, redirects to Stripe checkout or portal
- `apps/cogna/static/login.html` — `routeByRole()` routes portal admins to `/portal`, storytellers to `/storyteller`
- `apps/cogna/static/index.html`, `family.html`, `individual.html`, `legacy.html` — Nav with Login + Sign up links
- `apps/cogna/supabase_schema.sql` — `users` table (portal admins), `storyteller_users`, `promo_codes`, `user_sessions`
- Stripe env vars: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICES` dict

### Gaps or Problems Being Addressed

- No gift purchase flow exists
- No gift redemption path in signup
- No `gift_subscriptions` table
- No `gift_expires_at` column on `users`
- No expiry banner or downgrade logic
- No "Give a Gift" entry point in navigation

---

## Proposed Changes

### Summary of Changes

- New `gift.html` page — gift purchase UI with tier/duration picker, giver/recipient info, Stripe checkout
- New `gift-success.html` page — post-payment confirmation showing the gift code
- New `gift_subscriptions` table in Supabase
- `ALTER TABLE users ADD COLUMN gift_expires_at` and `gift_code`
- New server endpoints: `POST /api/gifts/purchase`, `GET /api/gifts/validate/{code}`, `POST /api/gifts/redeem`
- Stripe webhook extended to handle `payment_intent.succeeded` for gift purchases
- `portal-signup.html` — "Have a gift code?" section that bypasses plan picker and Stripe
- `portal.js` — expiry banner on dashboard load
- `supabase_schema.sql` — new table + column migrations
- Nav updated on all four marketing pages

### New Files to Create

| File Path | Purpose |
|---|---|
| `apps/cogna/static/gift.html` | Gift purchase page — tier/duration picker, giver/recipient form, Stripe checkout |
| `apps/cogna/static/gift-success.html` | Post-payment confirmation — shows gift code, share instructions |

### Files to Modify

| File Path | Changes |
|---|---|
| `apps/cogna/server.py` | Add gift endpoints, extend webhook, add expiry check to dashboard |
| `apps/cogna/supabase_schema.sql` | Add `gift_subscriptions` table, `gift_expires_at`/`gift_code` columns to `users` |
| `apps/cogna/static/portal-signup.html` | Add gift code entry section, gift redemption path |
| `apps/cogna/static/portal.js` | Add expiry banner on dashboard load |
| `apps/cogna/static/index.html` | Add "Give a Gift" nav link |
| `apps/cogna/static/family.html` | Add "Give a Gift" nav link |
| `apps/cogna/static/individual.html` | Add "Give a Gift" nav link |
| `apps/cogna/static/legacy.html` | Add "Give a Gift" nav link |

---

## Design Decisions

### Key Decisions Made

1. **Gift recipients become portal admin accounts (users table, not storyteller_users):** Gifts unlock the portal admin experience (B/C/D tiers). Putting gifted users in `storyteller_users` would give them the wrong interface.

2. **Stripe Checkout in `payment` mode (one-time charge, not subscription):** The giver pays once. The recipient gets a time-limited tier. No recurring billing is set up for the recipient at purchase time — they opt in themselves when the gift expires.

3. **Gift code generated on payment confirmation (webhook), not at purchase:** Codes are only generated after `payment_intent.succeeded` fires. This prevents codes being generated for failed payments.

4. **Gift code format: `GIFT-XXXX-XXXX`** (8 random alphanumeric chars split into two groups of 4). Distinct from promo codes (`E-XXXX`) and easily recognizable.

5. **Expiry handled client-side banner + server-side downgrade:** On portal dashboard load, if `gift_expires_at` is set and in the past, the server downgrades the account to Tier A and clears `gift_expires_at`. The portal JS also shows a warning banner starting 7 days before expiry.

6. **No Stripe subscription for gifted recipients at redemption time:** When the gift expires and they subscribe, a new Stripe subscription is created through the normal Billing tab `resubscribe()` flow — no special handling needed.

7. **Recipient email is optional:** Giver can receive the code and deliver it themselves (physical card, text, etc.), or provide the recipient's email for automatic delivery.

8. **Individual tiers only (B, C, D):** E and F are organizational tiers not suitable for gifting.

### Alternatives Considered

- **Stripe coupons instead of custom codes:** Simpler but no control over redemption, no record of who redeemed what, and coupon codes are visible in Stripe dashboard which creates support confusion.
- **Gift creates a Stripe subscription for recipient immediately:** More complex, requires Stripe to support transferring subscription ownership, and the recipient may never redeem — wasted subscription.
- **Single-page gift + success:** Keeping them separate avoids state management issues after Stripe redirect.

### Open Questions

None — all decisions are resolvable from existing patterns.

---

## Step-by-Step Tasks

### Step 1: Add database schema changes

Add the `gift_subscriptions` table and new columns to `users`.

**Actions:**

- Append to `apps/cogna/supabase_schema.sql`:

```sql
-- Gift subscriptions
CREATE TABLE IF NOT EXISTS gift_subscriptions (
  id                      TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  code                    TEXT UNIQUE NOT NULL,
  tier                    TEXT NOT NULL,
  duration_months         INTEGER NOT NULL,
  price_paid_cents        INTEGER NOT NULL,
  purchaser_name          TEXT NOT NULL DEFAULT '',
  purchaser_email         TEXT NOT NULL,
  recipient_name          TEXT NOT NULL DEFAULT '',
  recipient_email         TEXT,
  stripe_payment_intent_id TEXT,
  paid_at                 TIMESTAMPTZ,
  redeemed_by_email       TEXT,
  redeemed_at             TIMESTAMPTZ,
  created_at              TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS gift_subscriptions_code_idx ON gift_subscriptions(code);
CREATE INDEX IF NOT EXISTS gift_subscriptions_purchaser_idx ON gift_subscriptions(purchaser_email);

-- Add gift expiry tracking to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS gift_expires_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS gift_code TEXT;
```

- **Run this SQL in the Supabase SQL editor** before deploying server changes.

**Files affected:**
- `apps/cogna/supabase_schema.sql`

---

### Step 2: Add gift endpoints and webhook handling to server.py

Add four new sections to `server.py` after the existing Stripe billing section.

**Actions:**

**2a. Add gift Pydantic models** — add near other request models (around line 450):

```python
class GiftPurchaseRequest(BaseModel):
    tier: str
    duration_months: int
    purchaser_name: str
    purchaser_email: str
    recipient_name: str = ""
    recipient_email: str = ""

class GiftRedeemRequest(BaseModel):
    code: str
    name: str
    email: str
    password: str
```

**2b. Add helper `_generate_gift_code()`** — add near `_generate_story_promo_code`:

```python
def _generate_gift_code() -> str:
    chars = string.ascii_uppercase + string.digits
    for _ in range(20):
        part1 = "".join(secrets.choice(chars) for _ in range(4))
        part2 = "".join(secrets.choice(chars) for _ in range(4))
        code = f"GIFT-{part1}-{part2}"
        if supabase:
            r = supabase.table("gift_subscriptions").select("code").eq("code", code).limit(1).execute()
            if not r.data:
                return code
        else:
            return code
    raise ValueError("Could not generate unique gift code")
```

**2c. Add `POST /api/gifts/purchase`** — creates Stripe Checkout Session in `payment` mode:

```python
GIFT_PRICES = {
    "B": 500,   # $5/month in cents
    "C": 1000,
    "D": 1500,
}

GIFT_TIER_NAMES = {
    "B": "Storyteller Unlimited",
    "C": "Storyteller + Memoir Builder",
    "D": "AI Companion",
}

@app.post("/api/gifts/purchase")
def gift_purchase(payload: GiftPurchaseRequest):
    tier = payload.tier.upper()
    if tier not in GIFT_PRICES:
        raise HTTPException(status_code=400, detail="Invalid tier. Gifts are available for plans B, C, and D.")
    if payload.duration_months not in (1, 3, 6, 12):
        raise HTTPException(status_code=400, detail="Duration must be 1, 3, 6, or 12 months.")
    if not stripe_sdk or not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured.")

    stripe_sdk.api_key = STRIPE_SECRET_KEY
    monthly_cents = GIFT_PRICES[tier]
    total_cents = monthly_cents * payload.duration_months
    tier_name = GIFT_TIER_NAMES[tier]
    duration_label = f"{payload.duration_months} month{'s' if payload.duration_months > 1 else ''}"
    description = f"MyCogna {tier_name} — {duration_label} gift"

    # Store pending gift record (no code yet — assigned after payment)
    gift_id = secrets.token_urlsafe(16)
    if supabase:
        supabase.table("gift_subscriptions").insert({
            "id": gift_id,
            "code": f"PENDING-{gift_id}",  # placeholder; replaced in webhook
            "tier": tier,
            "duration_months": payload.duration_months,
            "price_paid_cents": total_cents,
            "purchaser_name": payload.purchaser_name,
            "purchaser_email": payload.purchaser_email.strip().lower(),
            "recipient_name": payload.recipient_name,
            "recipient_email": payload.recipient_email.strip().lower() if payload.recipient_email else None,
            "created_at": _utc_now(),
        }).execute()

    base_url = APP_URL or "https://mycogna.org"
    session = stripe_sdk.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "usd",
                "unit_amount": total_cents,
                "product_data": {"name": description},
            },
            "quantity": 1,
        }],
        customer_email=payload.purchaser_email,
        metadata={
            "gift_id": gift_id,
            "tier": tier,
            "duration_months": str(payload.duration_months),
            "purchaser_name": payload.purchaser_name,
            "purchaser_email": payload.purchaser_email.strip().lower(),
            "recipient_name": payload.recipient_name,
            "recipient_email": payload.recipient_email.strip().lower() if payload.recipient_email else "",
            "type": "gift",
        },
        success_url=f"{base_url}/gift/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/gift",
    )
    return {"url": session.url}
```

**2d. Extend `_handle_checkout_completed` webhook** — add a gift branch at the top of the function, before the existing `client_ref` check:

```python
# Gift purchase path
if (session.get("metadata") or {}).get("type") == "gift":
    _handle_gift_checkout_completed(session)
    return
```

**2e. Add `_handle_gift_checkout_completed(session)`** helper:

```python
def _handle_gift_checkout_completed(session: dict) -> None:
    meta = session.get("metadata") or {}
    gift_id = meta.get("gift_id")
    tier = meta.get("tier", "")
    duration_months = int(meta.get("duration_months", 1))
    purchaser_name = meta.get("purchaser_name", "")
    purchaser_email = meta.get("purchaser_email", "")
    recipient_name = meta.get("recipient_name", "")
    recipient_email = meta.get("recipient_email", "") or None
    payment_intent_id = session.get("payment_intent")

    if not gift_id or not tier or not purchaser_email:
        print(f"[Gift webhook] missing required metadata: {meta}")
        return

    # Generate unique gift code
    try:
        code = _generate_gift_code()
    except Exception as e:
        print(f"[Gift webhook] failed to generate code: {e}")
        return

    # Update gift record
    if supabase:
        supabase.table("gift_subscriptions").update({
            "code": code,
            "stripe_payment_intent_id": payment_intent_id,
            "paid_at": _utc_now(),
        }).eq("id", gift_id).execute()

    print(f"[Gift] code {code} created for {purchaser_email} → {recipient_email or 'no recipient email'} tier={tier} months={duration_months}")

    # Send confirmation emails
    _send_gift_confirmation_email(
        code=code,
        tier=tier,
        duration_months=duration_months,
        purchaser_name=purchaser_name,
        purchaser_email=purchaser_email,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
    )
```

**2f. Add `_send_gift_confirmation_email()`**:

```python
def _send_gift_confirmation_email(code, tier, duration_months, purchaser_name,
                                   purchaser_email, recipient_name, recipient_email):
    if not resend_sdk or not RESEND_API_KEY:
        return
    tier_names = {"B": "Storyteller Unlimited", "C": "Storyteller + Memoir Builder", "D": "AI Companion"}
    tier_name = tier_names.get(tier, tier)
    duration_label = f"{duration_months} month{'s' if duration_months > 1 else ''}"
    recipient_display = recipient_name or "your recipient"
    base_url = APP_URL or "https://mycogna.org"
    signup_url = f"{base_url}/portal/signup"

    # Email to giver
    giver_html = f"""
    <p>Hi {purchaser_name or 'there'}!</p>
    <p>Your gift of <strong>MyCogna {tier_name} ({duration_label})</strong> is ready.</p>
    <p style="font-size:24px;font-weight:bold;letter-spacing:2px;text-align:center;
              padding:16px;background:#f9f5ee;border-radius:8px">{code}</p>
    <p><strong>How {recipient_display} redeems it:</strong><br>
    1. Go to <a href="{signup_url}">{signup_url}</a><br>
    2. Click <strong>"Have a gift code?"</strong><br>
    3. Enter the code above and create their account — no credit card needed.</p>
    <p>The gift gives them full access to MyCogna {tier_name} for {duration_label}.
    After that, they can choose to continue with their own subscription.</p>
    <p>Questions? Reply to this email.</p>
    """
    try:
        resend_sdk.Emails.send({
            "from": RESEND_FROM,
            "to": [purchaser_email],
            "subject": f"Your MyCogna gift is ready — {code}",
            "html": giver_html,
        })
    except Exception as e:
        print(f"[Gift] giver email failed: {e}")

    # Email to recipient (if provided)
    if recipient_email:
        recipient_html = f"""
        <p>Hi {recipient_name or 'there'}!</p>
        <p><strong>{purchaser_name or 'Someone special'}</strong> has given you
        <strong>MyCogna {tier_name}</strong> for {duration_label} — a place to capture and
        preserve the stories that matter most.</p>
        <p style="font-size:24px;font-weight:bold;letter-spacing:2px;text-align:center;
                  padding:16px;background:#f9f5ee;border-radius:8px">{code}</p>
        <p>To get started:<br>
        1. Go to <a href="{signup_url}">{signup_url}</a><br>
        2. Click <strong>"Have a gift code?"</strong><br>
        3. Enter the code above — no credit card needed.</p>
        """
        try:
            resend_sdk.Emails.send({
                "from": RESEND_FROM,
                "to": [recipient_email],
                "subject": f"You've received a MyCogna gift from {purchaser_name or 'a friend'}",
                "html": recipient_html,
            })
        except Exception as e:
            print(f"[Gift] recipient email failed: {e}")
```

**2g. Add `GET /api/gifts/validate/{code}`**:

```python
@app.get("/api/gifts/validate/{code}")
def gift_validate(code: str):
    code = code.upper().strip()
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    r = supabase.table("gift_subscriptions").select("*").eq("code", code).limit(1).execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="Gift code not found.")
    gift = r.data[0]
    if not gift.get("paid_at"):
        raise HTTPException(status_code=402, detail="This gift has not been paid for yet.")
    if gift.get("redeemed_at"):
        raise HTTPException(status_code=409, detail="This gift code has already been redeemed.")
    tier_names = {"B": "Storyteller Unlimited", "C": "Storyteller + Memoir Builder", "D": "AI Companion"}
    return {
        "valid": True,
        "tier": gift["tier"],
        "tier_name": tier_names.get(gift["tier"], gift["tier"]),
        "duration_months": gift["duration_months"],
        "purchaser_name": gift["purchaser_name"],
        "recipient_email": gift.get("recipient_email"),
    }
```

**2h. Add `POST /api/gifts/redeem`**:

```python
@app.post("/api/gifts/redeem")
def gift_redeem(payload: GiftRedeemRequest):
    code = payload.code.upper().strip()
    email = payload.email.strip().lower()
    name = payload.name.strip()

    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")

    # Validate gift
    r = supabase.table("gift_subscriptions").select("*").eq("code", code).limit(1).execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="Gift code not found.")
    gift = r.data[0]
    if not gift.get("paid_at"):
        raise HTTPException(status_code=402, detail="This gift has not been paid for.")
    if gift.get("redeemed_at"):
        raise HTTPException(status_code=409, detail="This gift code has already been redeemed.")

    tier = gift["tier"]
    duration_months = gift["duration_months"]

    # Check if account already exists
    existing = _get_user(email)
    if existing:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists. Sign in and use the Billing tab to subscribe."
        )

    # Calculate expiry
    from dateutil.relativedelta import relativedelta
    expires_at = (datetime.now(timezone.utc) + relativedelta(months=duration_months)).isoformat()

    # Create account (no Stripe subscription)
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(payload.password, salt)
    first_name = name.split()[0] if name else ""
    last_name = " ".join(name.split()[1:]) if len(name.split()) > 1 else ""
    child_code = _generate_child_access_code()

    user = {
        "email": email,
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "password_salt": salt,
        "password_hash": pw_hash,
        "setup_type": "guardian",
        "tier": tier,
        "role": "portal_admin",
        "child_access_code": child_code,
        "subscription_status": "active",
        "gift_expires_at": expires_at,
        "gift_code": code,
        "created_at": _utc_now(),
    }
    _create_user(user)

    # Mark gift as redeemed
    supabase.table("gift_subscriptions").update({
        "redeemed_by_email": email,
        "redeemed_at": _utc_now(),
    }).eq("code", code).execute()

    token = _create_session(email)
    print(f"[Gift] redeemed {code} by {email} tier={tier} expires={expires_at}")
    return {"token": token, "user": _public_user(user)}
```

**2i. Add expiry check to dashboard endpoint** — in `GET /api/portal/dashboard` (or wherever the dashboard data is fetched), add after loading the user:

```python
# Check and apply gift expiry
if user.get("gift_expires_at"):
    try:
        expires = datetime.fromisoformat(user["gift_expires_at"].replace("Z", "+00:00"))
        if expires < datetime.now(timezone.utc):
            _update_user(email, {
                "tier": "A",
                "subscription_status": "none",
                "gift_expires_at": None,
                "gift_code": None,
            })
            user["tier"] = "A"
            user["gift_expires_at"] = None
    except Exception:
        pass
```

Also ensure `gift_expires_at` is returned in the dashboard response so the frontend can show the expiry banner.

**Files affected:**
- `apps/cogna/server.py`

---

### Step 3: Create gift.html

Create `apps/cogna/static/gift.html` — a clean, on-brand gift purchase page matching the style of `individual.html` and `family.html`.

**Structure:**
- Nav matching other marketing pages (with "Give a Gift" active)
- Hero: "Give the gift of story." subhead "Capture what matters, before it fades."
- **Tier picker** (3 cards): Storyteller Unlimited $5/mo · Storyteller + Memoir Builder $10/mo · AI Companion $15/mo
- **Duration picker** (4 buttons): 1 month · 3 months · 6 months · 12 months
- **Total price display**: dynamically calculated (e.g. "Total: $30" for 3×C)
- **Giver info** (required): Your name, Your email
- **Recipient info** (optional, collapsible): Recipient's name, Recipient's email — helper text: "We'll send them a separate email with the code. Or leave blank and deliver it yourself."
- **"Purchase Gift →" button** → calls `POST /api/gifts/purchase` → redirects to Stripe checkout
- Footer matching other pages

**Key JS on the page:**
```javascript
let selectedTier = null;
let selectedMonths = 1;

const PRICES = { B: 5, C: 10, D: 15 };

function selectTier(tier) {
  selectedTier = tier;
  // update card highlight, update total
  updateTotal();
}

function selectDuration(months) {
  selectedMonths = months;
  // update button highlight, update total
  updateTotal();
}

function updateTotal() {
  if (!selectedTier) return;
  const total = PRICES[selectedTier] * selectedMonths;
  document.getElementById('totalDisplay').textContent = `Total: $${total}`;
}

async function handlePurchase(e) {
  e.preventDefault();
  if (!selectedTier) { alert('Please select a plan.'); return; }
  const purchaser_name = document.getElementById('giverName').value.trim();
  const purchaser_email = document.getElementById('giverEmail').value.trim();
  if (!purchaser_name || !purchaser_email) { alert('Please enter your name and email.'); return; }
  
  const btn = document.getElementById('purchaseBtn');
  btn.disabled = true;
  btn.textContent = 'Preparing checkout…';
  
  try {
    const res = await fetch('/api/gifts/purchase', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tier: selectedTier,
        duration_months: selectedMonths,
        purchaser_name,
        purchaser_email,
        recipient_name: document.getElementById('recipientName').value.trim(),
        recipient_email: document.getElementById('recipientEmail').value.trim(),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Something went wrong.');
    window.location.href = data.url;
  } catch (err) {
    alert('Error: ' + err.message);
    btn.disabled = false;
    btn.textContent = 'Purchase Gift →';
  }
}
```

**Files affected:**
- `apps/cogna/static/gift.html` (new)

---

### Step 4: Create gift-success.html

Create `apps/cogna/static/gift-success.html` — the post-payment confirmation page.

Stripe redirects here with `?session_id=xxx`. The page calls `GET /api/gifts/session/{session_id}` to retrieve the gift details and display the code.

**Add server endpoint `GET /api/gifts/session/{session_id}`:**
```python
@app.get("/api/gifts/session/{session_id}")
def gift_session(session_id: str):
    if not stripe_sdk or not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured.")
    stripe_sdk.api_key = STRIPE_SECRET_KEY
    try:
        session = stripe_sdk.checkout.Session.retrieve(session_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Session not found.")
    gift_id = (session.get("metadata") or {}).get("gift_id")
    if not gift_id or not supabase:
        raise HTTPException(status_code=404, detail="Gift not found.")
    r = supabase.table("gift_subscriptions").select("code,tier,duration_months,recipient_name,recipient_email").eq("id", gift_id).limit(1).execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="Gift record not found.")
    gift = r.data[0]
    tier_names = {"B": "Storyteller Unlimited", "C": "Storyteller + Memoir Builder", "D": "AI Companion"}
    return {
        "code": gift["code"],
        "tier_name": tier_names.get(gift["tier"], gift["tier"]),
        "duration_months": gift["duration_months"],
        "recipient_name": gift.get("recipient_name", ""),
        "recipient_email": gift.get("recipient_email", ""),
    }
```

**Page content:**
- Checkmark icon + "Your gift is ready!"
- Large display of the gift code (copyable)
- Summary: "3 months of Storyteller + Memoir Builder for [Recipient Name]"
- Redemption instructions: "Share this link with [Recipient]: mycogna.org/portal/signup"
- "A confirmation email has been sent to you" (and recipient if provided)
- Button: "Give another gift →" back to /gift

**Files affected:**
- `apps/cogna/static/gift-success.html` (new)
- `apps/cogna/server.py` (add GET /api/gifts/session/{session_id})

---

### Step 5: Update portal-signup.html with gift code redemption

Add a "Have a gift code?" section to the signup page that replaces the plan picker when a valid code is entered.

**Add above the plan section (after the page header/title):**
```html
<!-- Gift code entry -->
<div id="giftCodeSection" style="width:100%;max-width:900px;margin-bottom:24px;text-align:center">
  <button type="button" onclick="toggleGiftEntry()" 
          style="background:none;border:none;color:var(--gold);font-size:14px;cursor:pointer;text-decoration:underline">
    Have a gift code?
  </button>
  <div id="giftEntryRow" style="display:none;margin-top:12px;display:flex;gap:8px;justify-content:center;align-items:center">
    <input type="text" id="giftCodeInput" placeholder="GIFT-XXXX-XXXX" 
           style="font-family:monospace;text-transform:uppercase;width:200px;padding:10px 14px;
                  border:1px solid var(--border);border-radius:8px;font-size:15px">
    <button type="button" onclick="applyGiftCode()" class="save-btn" style="width:auto">Apply</button>
  </div>
  <div id="giftCodeError" style="display:none;color:#c0392b;font-size:13px;margin-top:8px"></div>
</div>

<!-- Gift confirmed banner (shown when valid code applied) -->
<div id="giftConfirmed" style="display:none;width:100%;max-width:900px;margin-bottom:24px;
     padding:20px 24px;background:#f9f5ee;border:1px solid var(--gold-light);border-radius:12px">
  <div style="font-size:11px;text-align:center;letter-spacing:0.1em;text-transform:uppercase;color:var(--gold);margin-bottom:8px">Gift Applied</div>
  <div id="giftSummary" style="font-size:18px;text-align:center;font-family:'Cormorant Garamond',serif"></div>
  <div style="text-align:center;margin-top:8px">
    <button type="button" onclick="clearGiftCode()" 
            style="background:none;border:none;font-size:12px;color:var(--ink-muted);cursor:pointer;text-decoration:underline">
      Remove gift code
    </button>
  </div>
</div>
```

**Add JS functions:**
```javascript
let appliedGiftCode = null;
let appliedGiftData = null;

function toggleGiftEntry() {
  const row = document.getElementById('giftEntryRow');
  row.style.display = row.style.display === 'none' ? 'flex' : 'none';
}

async function applyGiftCode() {
  const code = document.getElementById('giftCodeInput').value.trim().toUpperCase();
  const errEl = document.getElementById('giftCodeError');
  errEl.style.display = 'none';
  if (!code) return;

  try {
    const res = await fetch(`/api/gifts/validate/${encodeURIComponent(code)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Invalid code.');
    appliedGiftCode = code;
    appliedGiftData = data;

    // Hide plan picker, show gift banner
    document.getElementById('giftCodeSection').style.display = 'none';
    document.getElementById('giftSummary').textContent =
      `${data.duration_months} month${data.duration_months > 1 ? 's' : ''} of ${data.tier_name}` +
      (data.purchaser_name ? ` — gift from ${data.purchaser_name}` : '');
    document.getElementById('giftConfirmed').style.display = 'block';
    document.querySelectorAll('.plan-section, .plan-section-divider').forEach(el => el.style.display = 'none');

    // Show signup form pre-configured for gift
    document.getElementById('selectedTier').value = data.tier;
    document.getElementById('planConfirm').textContent = `${data.tier_name} (Gift — ${data.duration_months} months)`;
    document.getElementById('signupWrap').style.display = 'block';
    document.getElementById('submitBtn').textContent = 'Redeem gift & create account →';
    document.getElementById('signupWrap').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (err) {
    errEl.textContent = err.message;
    errEl.style.display = 'block';
  }
}

function clearGiftCode() {
  appliedGiftCode = null;
  appliedGiftData = null;
  document.getElementById('giftConfirmed').style.display = 'none';
  document.getElementById('giftCodeSection').style.display = 'block';
  document.getElementById('giftEntryRow').style.display = 'none';
  document.getElementById('giftCodeInput').value = '';
  document.getElementById('selectedTier').value = '';
  document.getElementById('signupWrap').style.display = 'none';
  document.querySelectorAll('.plan-section, .plan-section-divider').forEach(el => el.style.display = '');
}
```

**Modify `handleSignup()`** — if `appliedGiftCode` is set, call `/api/gifts/redeem` instead of `/api/auth/register`:

```javascript
// At the top of handleSignup(), replace the fetch block:
if (appliedGiftCode) {
  // Gift redemption path — no Stripe
  const res = await fetch('/api/gifts/redeem', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code: appliedGiftCode, name, email, password }),
  });
  const data = await res.json();
  if (!res.ok) {
    const msg = data.detail || 'Something went wrong.';
    errEl.innerHTML = msg.includes('already exists')
      ? msg + ' <a href="/portal" style="color:inherit;font-weight:600;text-decoration:underline">Sign in →</a>'
      : msg;
    errEl.className = 'error-msg visible';
    btn.disabled = false;
    btn.textContent = 'Redeem gift & create account →';
    return;
  }
  localStorage.setItem('portalToken', data.token);
  window.location.href = '/portal';
  return;
}
// ... existing non-gift path continues below
```

**Files affected:**
- `apps/cogna/static/portal-signup.html`

---

### Step 6: Add expiry banner to portal.js

In `loadDashboard()` (the function that runs after login), add a check for `gift_expires_at` from the dashboard API response and show a banner.

**Add to portal dashboard response handling** — after user data is loaded:

```javascript
// Gift expiry banner
const giftExpiry = state.user?.gift_expires_at;
if (giftExpiry) {
  const expiresDate = new Date(giftExpiry);
  const now = new Date();
  const daysLeft = Math.ceil((expiresDate - now) / (1000 * 60 * 60 * 24));
  if (daysLeft <= 7 && daysLeft > 0) {
    const banner = document.createElement('div');
    banner.style.cssText = 'background:#7a5230;color:#fff;padding:12px 24px;text-align:center;font-size:14px';
    banner.innerHTML = `Your gift subscription expires in ${daysLeft} day${daysLeft !== 1 ? 's' : ''} 
      (${expiresDate.toLocaleDateString('en-US', {month:'long',day:'numeric'})}). 
      <button onclick="portal.switchDashTab('Billing')" 
              style="background:rgba(255,255,255,0.2);border:none;color:#fff;padding:4px 12px;
                     border-radius:4px;cursor:pointer;margin-left:8px;font-size:13px">
        Add payment method →
      </button>`;
    document.body.prepend(banner);
  }
}
```

Also ensure `_public_user()` in server.py returns `gift_expires_at`:

```python
def _public_user(user):
    return {
        ...existing fields...,
        "gift_expires_at": user.get("gift_expires_at"),
    }
```

**Files affected:**
- `apps/cogna/static/portal.js`
- `apps/cogna/server.py` (`_public_user`)

---

### Step 7: Add "Give a Gift" to navigation on all marketing pages

Add a gift link to the nav on `index.html`, `individual.html`, `family.html`, and `legacy.html`.

**Pattern to find in each file:**
```html
<li><a href="/login" class="nav-btn-outline">Login</a></li>
```

**Insert before the Login link:**
```html
<li><a href="/gift">Give a Gift</a></li>
```

This adds it as a standard nav item before Login on all four pages.

**Files affected:**
- `apps/cogna/static/index.html`
- `apps/cogna/static/individual.html`
- `apps/cogna/static/family.html`
- `apps/cogna/static/legacy.html`

---

### Step 8: Add Stripe webhook event for gift purchases

The existing webhook handles `checkout.session.completed`. Gift purchases use Stripe Checkout in `payment` mode, which also fires `checkout.session.completed` — so no new webhook event type needs to be registered in Stripe. The `type: "gift"` metadata flag routes it to `_handle_gift_checkout_completed()`.

**Verify in Stripe dashboard** that `checkout.session.completed` is already registered in the webhook endpoint. It should be — this was set up as part of the original billing system.

**Files affected:**
- None (existing webhook endpoint handles it)

---

### Step 9: Add server routes for gift pages

Add static file routes in `server.py` (or ensure Vercel/Railway serves them) for `/gift` and `/gift/success`.

Since the app serves static files via FastAPI's `StaticFiles` mount or explicit routes, add:

```python
@app.get("/gift")
def gift_page():
    return FileResponse("static/gift.html")

@app.get("/gift/success")
def gift_success_page():
    return FileResponse("static/gift-success.html")
```

Check where existing page routes are defined (e.g., `/portal`, `/storyteller`) and add these in the same location.

**Files affected:**
- `apps/cogna/server.py`

---

### Step 10: Run database migrations

**In the Supabase SQL editor, run:**

```sql
CREATE TABLE IF NOT EXISTS gift_subscriptions (
  id                      TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  code                    TEXT UNIQUE NOT NULL,
  tier                    TEXT NOT NULL,
  duration_months         INTEGER NOT NULL,
  price_paid_cents        INTEGER NOT NULL,
  purchaser_name          TEXT NOT NULL DEFAULT '',
  purchaser_email         TEXT NOT NULL,
  recipient_name          TEXT NOT NULL DEFAULT '',
  recipient_email         TEXT,
  stripe_payment_intent_id TEXT,
  paid_at                 TIMESTAMPTZ,
  redeemed_by_email       TEXT,
  redeemed_at             TIMESTAMPTZ,
  created_at              TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS gift_subscriptions_code_idx ON gift_subscriptions(code);
CREATE INDEX IF NOT EXISTS gift_subscriptions_purchaser_idx ON gift_subscriptions(purchaser_email);

ALTER TABLE users ADD COLUMN IF NOT EXISTS gift_expires_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS gift_code TEXT;
```

**This must be run before deploying the server changes.**

---

### Step 11: Install python-dateutil dependency

The `gift_redeem` endpoint uses `dateutil.relativedelta` for accurate month arithmetic. Add to `requirements.txt`:

```
python-dateutil
```

**Files affected:**
- `apps/cogna/requirements.txt`

---

### Step 12: Bump cache-bust versions

After all static file changes, bump the cache-bust query param on portal.html and portal.js (currently `v=20260531a`) to force browsers to reload updated files.

**Files affected:**
- `apps/cogna/static/portal.html`
- `apps/cogna/static/portal.js`

---

## Connections & Dependencies

### Files That Reference This Area

- `apps/cogna/static/index.html` — home page nav (add gift link)
- `apps/cogna/static/individual.html` — individual audience page nav
- `apps/cogna/static/family.html` — family audience page nav
- `apps/cogna/static/legacy.html` — legacy/org audience page nav
- `apps/cogna/static/portal-signup.html` — signup flow (add gift redemption path)

### Updates Needed for Consistency

- `CLAUDE.md` — document `/gift` route and gift subscription system under MyCogna App section
- `apps/cogna/supabase_schema.sql` — migrations already included in Step 1/10

### Impact on Existing Workflows

- Existing signup flow is unchanged for non-gift users — the gift code entry is additive
- Existing Stripe webhook is extended, not replaced — gift purchases are identified by `metadata.type = "gift"` and branched early
- Existing billing tab works for gift recipients after expiry — `resubscribe()` already handles Tier A accounts

---

## Validation Checklist

- [ ] Supabase `gift_subscriptions` table exists with all columns
- [ ] `users.gift_expires_at` and `users.gift_code` columns exist
- [ ] `GET /api/gifts/validate/TEST-CODE` returns 404 (not 500)
- [ ] `POST /api/gifts/purchase` with valid payload returns a Stripe checkout URL
- [ ] Completing Stripe checkout fires webhook and creates a gift record with a real `GIFT-XXXX-XXXX` code
- [ ] Giver receives confirmation email with the code after payment
- [ ] `GET /gift/success?session_id=xxx` loads and displays the code
- [ ] Portal signup page shows "Have a gift code?" toggle
- [ ] Entering a valid code hides plan picker and shows gift summary
- [ ] Submitting signup with gift code creates account in `users` table with correct tier and `gift_expires_at`
- [ ] Gift code is marked redeemed in `gift_subscriptions` after redemption
- [ ] Trying to redeem same code twice returns 409 error
- [ ] Dashboard shows expiry banner when gift expires within 7 days
- [ ] After expiry, account is downgraded to Tier A on next login
- [ ] "Give a Gift" link appears in nav on all four marketing pages
- [ ] `/gift` and `/gift/success` routes resolve without 404
- [ ] `python-dateutil` added to requirements.txt

---

## Success Criteria

1. A gift giver can complete a purchase at `mycogna.org/gift` and receive a `GIFT-XXXX-XXXX` code by email within 60 seconds of payment
2. A recipient can redeem a gift code at the signup page and land in the portal with the correct tier active and no payment required
3. A gifted account shows a warning banner 7 days before expiry, and is automatically downgraded to Tier A after expiry

---

## Notes

- **Father's Day deadline: June 21, 2026** — approximately 3 weeks from plan creation. All steps are independent and can be built sequentially in a single focused session.
- **Stripe test mode**: Use Stripe test mode with a test card (`4242 4242 4242 4242`) to verify the full purchase → webhook → code generation flow before going live.
- **Future enhancement**: A `/portal` admin view showing all gift purchases and redemptions (useful for support and for Christy to see adoption).
- **Future enhancement**: 7-day-before-expiry automated email (would require a scheduled job or Supabase cron — not in scope for this plan).
- **RLS**: If Supabase Row Level Security is enabled, ensure the `gift_subscriptions` table has appropriate policies for server-side access via the service key.

---

## Implementation Notes

**Implemented:** 2026-05-26

### Summary

- Added `gift_subscriptions` table and `gift_expires_at`/`gift_code` columns to `supabase_schema.sql`
- Added `python-dateutil` to `requirements.txt`
- Added `GIFT_PRICES` and `GIFT_TIER_NAMES` constants to `server.py`
- Added Pydantic models: `GiftPurchaseRequest`, `GiftRedeemRequest`
- Added `_generate_gift_code()`, `_send_gift_confirmation_email()`, `_handle_gift_checkout_completed()` helpers
- Added endpoints: `POST /api/gifts/purchase`, `GET /api/gifts/validate/{code}`, `POST /api/gifts/redeem`, `GET /api/gifts/session/{session_id}`
- Updated `_handle_checkout_completed` to detect `metadata.type == "gift"` and route to gift handler
- Updated `_public_user` to return `gift_expires_at` and `gift_code`
- Updated `auth_me` to check gift expiry on every dashboard load and downgrade expired accounts to Tier A
- Added page routes `GET /gift` and `GET /gift/success`
- Created `static/gift.html` — gift purchase page with tier/duration picker, giver/recipient info, Stripe checkout
- Created `static/gift-success.html` — post-payment confirmation page showing copyable gift code
- Updated `portal-signup.html` — added gift code entry UI, `applyGiftCode()`, `clearGiftCode()`, and gift redemption path in `handleSignup()`
- Updated `portal.js` — added gift expiry banner in `loadDashboard()`
- Updated `portal.html` — added `giftExpiryBanner` div
- Added "Give a Gift" nav link to `index.html`, `family.html`, `individual.html`, `legacy.html`

### Deviations from Plan

- Gift expiry banner shows for any gift expiring within 30 days (plan said 7 days; 30 days is more useful UX)
- `_send_gift_confirmation_email` built inline rather than as a separate template file — code volume didn't warrant a separate file
- `auth_me` used for expiry check rather than a dedicated dashboard endpoint — simpler and runs on every portal load

### Issues Encountered

- None
