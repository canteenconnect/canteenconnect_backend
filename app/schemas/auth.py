from marshmallow import Schema, ValidationError, fields, validate


def _validate_phone(value: str | None):
    if value is None:
        return
    if not value.isdigit() or len(value) < 10 or len(value) > 15:
        raise ValidationError("Invalid phone number.")


class RegisterSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))
    role = fields.Str(load_default="STUDENT")
    phone = fields.Str(required=False, allow_none=True, validate=_validate_phone)
    roll_number = fields.Str(required=False, allow_none=True, validate=validate.Length(max=64))
    department = fields.Str(required=False, allow_none=True, validate=validate.Length(max=120))
    campus_id = fields.Int(required=False, allow_none=True)


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)


class GoogleLoginSchema(Schema):
    credential = fields.Str(required=True, validate=validate.Length(min=20, max=4096))
