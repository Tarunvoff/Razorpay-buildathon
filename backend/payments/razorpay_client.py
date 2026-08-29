"""
Razorpay Orders API integration and HMAC-signed ALLOW token verification.
Enforces the core invariant: downstream payment execution requires a valid,
short-lived (~30s TTL) server-issued ALLOW token minted immediately by RazorGate.
"""

import hashlib
import hmac
import time
from typing import Any, Dict, Optional

import razorpay
from backend.config import settings

class TokenInvalidError(PermissionError):
    pass

class TokenExpiredError(PermissionError):
    pass

# Initialize official Razorpay SDK client with credentials
client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def get_token_secret() -> str:
    """Returns the secret key used for minting and verifying ALLOW tokens."""
    return settings.razorpay_key_secret or "razorgate_default_signing_secret"


def mint_allow_token(
    agent_id: str,
    amount_paise: int,
    receipt: str,
    timestamp: Optional[float] = None,
) -> str:
    """
    Mints a cryptographically signed HMAC-SHA256 ALLOW token.
    Token format: "{unix_timestamp}.{hex_digest_signature}"
    """
    ts = int(timestamp if timestamp is not None else time.time())
    secret = get_token_secret().encode("utf-8")
    payload = f"{agent_id}:{amount_paise}:{receipt}:{ts}".encode("utf-8")
    sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return f"{ts}.{sig}"


def verify_allow_token(
    token: str,
    agent_id: str,
    amount_paise: int,
    receipt: str,
    max_age_seconds: float = 90.0,
    current_time: Optional[float] = None,
) -> bool:
    """
    Verifies that the ALLOW token:
    1. Has valid format {timestamp}.{signature}
    2. Matches HMAC signature over (agent_id, amount_paise, receipt, timestamp)
    3. Was generated within the allowable TTL window (default: 90s)
    """
    if not token or "." not in token:
        raise TokenInvalidError("Invalid token format")

    try:
        ts_str, sig = token.split(".", 1)
        ts = int(ts_str)
    except Exception:
        raise TokenInvalidError("Invalid token format")

    now = current_time if current_time is not None else time.time()

    secret = get_token_secret().encode("utf-8")
    payload = f"{agent_id}:{amount_paise}:{receipt}:{ts}".encode("utf-8")
    expected_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(sig, expected_sig):
        raise TokenInvalidError("Invalid token signature")

    # Check TTL and guard against clock skew (> 5s in the future)
    if (now - ts) > max_age_seconds or ts > (now + 5.0):
        raise TokenExpiredError("Token expired")

    return True


def create_order(
    amount_paise: int,
    receipt: str,
    currency: str = "INR",
    notes: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes real Razorpay Orders API call in test mode.
    """
    order_data: Dict[str, Any] = {
        "amount": amount_paise,
        "currency": currency,
        "receipt": receipt,
    }
    if notes:
        order_data["notes"] = notes
        
    kwargs = {}
    if idempotency_key:
        kwargs["headers"] = {"X-Idempotency-Key": idempotency_key}
        
    return client.order.create(order_data, **kwargs)


def create_gated_order(
    agent_id: str,
    amount_paise: int,
    receipt: str,
    allow_token: str,
    currency: str = "INR",
    notes: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Gated order creation: validates the server-issued ALLOW token before calling Razorpay.
    Raises TokenInvalidError or TokenExpiredError if token is invalid, forged, or expired.
    """
    verify_allow_token(
        token=allow_token,
        agent_id=agent_id,
        amount_paise=amount_paise,
        receipt=receipt,
    )

    return create_order(
        amount_paise=amount_paise,
        receipt=receipt,
        currency=currency,
        notes=notes,
        idempotency_key=idempotency_key,
    )


def fetch_order(order_id: str) -> Dict[str, Any]:
    """Fetches order details by order_id from Razorpay."""
    return client.order.fetch(order_id)


def verify_payment_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> bool:
    """
    Verifies Razorpay payment signature server-side using Razorpay Key Secret.
    Signature formula: HMAC-SHA256(order_id + "|" + payment_id, key_secret)
    """
    secret = settings.razorpay_key_secret or ""
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        })
        return True
    except Exception:
        msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
        expected = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, razorpay_signature)

