from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError

from app import limiter
from app.middleware.role_required import role_required
from app.models import (
    Order,
    Payment,
    ROLE_STUDENT,
    PAYMENT_STATUS_CREATED,
    PAYMENT_STATUS_FAILED,
    PAYMENT_STATUS_PAID,
)
from app.schemas.payment import PaymentCreateSchema, PaymentVerifySchema
from app.services.audit_service import log_audit
from app.services.payment_service import (
    RazorpayService,
    record_payment_failure,
    record_payment_success,
)
from app.utils.api_error import APIError

payment_bp = Blueprint("payment", __name__, url_prefix="/payments")


@payment_bp.post("/create-order")
@role_required(ROLE_STUDENT)
@limiter.limit("10 per minute")
def create_payment_order():
    payload = request.get_json(silent=True) or {}
    schema = PaymentCreateSchema()
    try:
        data = schema.load(payload)
    except ValidationError as err:
        raise APIError("Invalid payment payload.", 400, "validation_error", err.messages)

    order = Order.query.filter_by(id=data["order_id"], user_id=current_user.id).first()
    if not order:
        raise APIError("Order not found.", 404, "not_found")

    existing_payment = Payment.query.filter_by(order_id=order.id).order_by(Payment.created_at.desc()).first()
    if existing_payment and existing_payment.status != PAYMENT_STATUS_FAILED:
        return jsonify({"payment": existing_payment.to_dict()}), 200

    service = RazorpayService()
    gateway_order = service.create_order(order)

    payment = Payment(
        order_id=order.id,
        user_id=current_user.id,
        amount=order.total_amount,
        currency="INR",
        gateway="RAZORPAY",
        gateway_order_id=gateway_order.get("id"),
        status=PAYMENT_STATUS_CREATED,
    )
    db.session.add(payment)
    db.session.commit()

    log_audit(current_user.id, "payment_order_created", "payment", payment.id)
    return jsonify({"payment": payment.to_dict(), "gateway_order": gateway_order}), 201


@payment_bp.post("/verify")
@role_required(ROLE_STUDENT)
@limiter.limit("20 per minute")
def verify_payment():
    payload = request.get_json(silent=True) or {}
    schema = PaymentVerifySchema()
    try:
        data = schema.load(payload)
    except ValidationError as err:
        raise APIError("Invalid payment verification payload.", 400, "validation_error", err.messages)

    order = Order.query.filter_by(id=data["order_id"], user_id=current_user.id).first()
    if not order:
        raise APIError("Order not found.", 404, "not_found")

    payment = Payment.query.filter_by(order_id=order.id, gateway_order_id=data["razorpay_order_id"]).first()
    if not payment:
        raise APIError("Payment record not found.", 404, "not_found")
    if payment.status == PAYMENT_STATUS_PAID:
        return jsonify({"payment": payment.to_dict(), "order": order.to_dict()}), 200

    service = RazorpayService()
    is_valid = service.verify_payment_signature(
        {
            "razorpay_order_id": data["razorpay_order_id"],
            "razorpay_payment_id": data["razorpay_payment_id"],
            "razorpay_signature": data["razorpay_signature"],
        }
    )

    if not is_valid:
        record_payment_failure(order, payment, data["razorpay_payment_id"])
        log_audit(current_user.id, "payment_failed", "payment", payment.id)
        raise APIError("Payment verification failed.", 400, "payment_failed")

    record_payment_success(order, payment, data["razorpay_payment_id"], data["razorpay_signature"])
    log_audit(current_user.id, "payment_success", "payment", payment.id)
    return jsonify({"payment": payment.to_dict(), "order": order.to_dict()}), 200


@payment_bp.post("/webhook")
@limiter.limit("60 per minute")
def webhook():
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature:
        raise APIError("Missing signature.", 400, "validation_error")

    service = RazorpayService()
    secret = current_app.config.get("RAZORPAY_WEBHOOK_SECRET")
    if not secret:
        raise APIError("Webhook secret not configured.", 500, "configuration_error")

    body = request.get_data()
    if not service.verify_webhook_signature(body, signature, secret):
        raise APIError("Invalid webhook signature.", 400, "invalid_signature")

    payload = request.get_json(silent=True) or {}
    event = payload.get("event")
    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = entity.get("order_id")
    payment_id = entity.get("id")
    status = entity.get("status")

    if not order_id:
        return jsonify({"status": "ignored"}), 200

    payment = Payment.query.filter_by(gateway_order_id=order_id).first()
    if not payment:
        return jsonify({"status": "ignored"}), 200

    order = Order.query.filter_by(id=payment.order_id).first()
    if not order:
        return jsonify({"status": "ignored"}), 200

    if payment.status == PAYMENT_STATUS_PAID:
        return jsonify({"status": "ok"}), 200

    if status == "captured":
        record_payment_success(order, payment, payment_id, None)
        log_audit(payment.user_id, "payment_success", "payment", payment.id)
    elif status == "failed":
        record_payment_failure(order, payment, payment_id)
        log_audit(payment.user_id, "payment_failed", "payment", payment.id)

    return jsonify({"status": "ok"}), 200
