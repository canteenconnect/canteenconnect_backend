from marshmallow import Schema, ValidationError, fields, validate


def _validate_phone(value: str | None):
    if value is None:
        return
    if not value.isdigit() or len(value) < 10 or len(value) > 15:
        raise ValidationError("Invalid phone number.")


class ProfileUpdateSchema(Schema):
    name = fields.Str(required=False, validate=validate.Length(min=1, max=120))
    phone = fields.Str(required=False, allow_none=True, validate=_validate_phone)
    roll_number = fields.Str(required=False, allow_none=True, validate=validate.Length(max=64))
    department = fields.Str(required=False, allow_none=True, validate=validate.Length(max=120))
    campus_id = fields.Int(required=False, allow_none=True)
