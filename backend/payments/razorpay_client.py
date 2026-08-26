import razorpay
from backend.config import settings

client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))

def create_order(amount_paise: int, receipt: str, currency: str = "INR") -> dict:
    return client.order.create({
        "amount": amount_paise,
        "currency": currency,
        "receipt": receipt,
    })

def fetch_order(order_id: str) -> dict:
    return client.order.fetch(order_id)
