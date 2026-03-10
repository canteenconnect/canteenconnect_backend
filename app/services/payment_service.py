from __future__ import annotations

from decimal import Decimal

from flask import current_app

from app import db
from app.models import (
    ORDER_STATUS_FAILED,
    ORDER_STATUS_PENDING,
    PAYMENT_STATUS_FAILED,
    PAYMENT_STATUS_PAID,
    Order,
    Payment,
    Transaction,
)
from app.utils.api_error import APIError


class RazorpayService:
    def __init__(self):
        import razorpay

        key_id = current_app.config.get("RAZORPAY_KEY_ID")
        key_secret = current_app.config.get("RAZORPAY_KEY_SECRET")
        if not key_id or not key_secret:
            raise APIError("Razorpay credentials are not configured.", 500, "configuration_error")
        self.client = razorpay.Client(auth=(key_id, key_secret))

    def create_order(self, order: Order) -> dict:
        amount_paise = int(Decimal(order.total_amount) * 100)
        payload = {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": order.order_number,
            "payment_capture": 1,
        }
        try:
            return self.client.order.create(payload)
        except Exception as exc:  # noqa: BLE001
            raise APIError("Failed to create Razorpay order.", 502, "gateway_error") from exc

    def verify_payment_signature(self, payload: dict):
        import razorpay

        utility = razorpay.Utility()
        try:
            utility.verify_payment_signature(payload)
            return True
        except razorpay.errors.SignatureVerificationError:
            return False

    def verify_webhook_signature(self, body: bytes, signature: str, secret: str):
        import razorpay

        utility = razorpay.Utility()
        try:
            utility.verify_webhook_signature(body, signature, secret)
            return True
        except razorpay.errors.SignatureVerificationError:
            return False


def record_payment_success(order: Order, payment: Payment, gateway_payment_id: str, signature: str | None):
    payment.status = PAYMENT_STATUS_PAID
    payment.gateway_payment_id = gateway_payment_id
    payment.gateway_signature = signature
    order.payment_status = PAYMENT_STATUS_PAID
    order.status = ORDER_STATUS_PENDING
    db.session.add(
        Transaction(
            order_id=order.id,
            user_id=order.user_id,
            amount=order.total_amount,
            payment_gateway=payment.gateway,
            gateway_transaction_id=gateway_payment_id,
            status=PAYMENT_STATUS_PAID,
        )
    )
    db.session.commit()


def record_payment_failure(order: Order, payment: Payment, gateway_payment_id: str | None = None):
    payment.status = PAYMENT_STATUS_FAILED
    payment.gateway_payment_id = gateway_payment_id
    order.payment_status = PAYMENT_STATUS_FAILED
    order.status = ORDER_STATUS_FAILED
    db.session.add(
        Transaction(
            order_id=order.id,
            user_id=order.user_id,
            amount=order.total_amount,
            payment_gateway=payment.gateway,
            gateway_transaction_id=gateway_payment_id,
            status=PAYMENT_STATUS_FAILED,
        )
    )
    db.session.commit()
