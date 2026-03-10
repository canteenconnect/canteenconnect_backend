from marshmallow import Schema, fields, validate


class OrderItemSchema(Schema):
    menu_item_id = fields.Int(required=True, strict=True)
    quantity = fields.Int(required=True, strict=True, validate=validate.Range(min=1, max=50))


class OrderCreateSchema(Schema):
    outlet_id = fields.Int(required=True, strict=True, validate=validate.Range(min=1))
    items = fields.List(fields.Nested(OrderItemSchema), required=True, validate=validate.Length(min=1))
