from marshmallow import Schema, fields, validate


class PaymentCreateSchema(Schema):
    order_id = fields.Int(required=True, strict=True, validate=validate.Range(min=1))


class PaymentVerifySchema(Schema):
    order_id = fields.Int(required=True, strict=True, validate=validate.Range(min=1))
    razorpay_order_id = fields.Str(required=True, validate=validate.Length(min=5, max=200))
    razorpay_payment_id = fields.Str(required=True, validate=validate.Length(min=5, max=200))
    razorpay_signature = fields.Str(required=True, validate=validate.Length(min=5, max=255))
