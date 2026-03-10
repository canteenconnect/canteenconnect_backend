from django.db import models


class User(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=32)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "users"
        managed = False

    def __str__(self):
        return f"{self.name} ({self.role})"


class Student(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, models.DO_NOTHING, db_column="user_id", related_name="student")
    roll_number = models.CharField(max_length=64, unique=True)
    department = models.CharField(max_length=120)
    wallet_balance = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "students"
        managed = False

    def __str__(self):
        return self.roll_number


class Outlet(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=120, unique=True)
    location = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "outlets"
        managed = False

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    outlet = models.ForeignKey(Outlet, models.DO_NOTHING, db_column="outlet_id", related_name="menu_items")
    item_name = models.CharField(max_length=120)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    available_quantity = models.IntegerField(default=0)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "menu_items"
        managed = False

    def __str__(self):
        return self.item_name


class Order(models.Model):
    id = models.BigAutoField(primary_key=True)
    order_number = models.CharField(max_length=32, unique=True)
    student = models.ForeignKey(Student, models.DO_NOTHING, db_column="student_id", related_name="orders")
    outlet = models.ForeignKey(Outlet, models.DO_NOTHING, db_column="outlet_id", related_name="orders")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_mode = models.CharField(max_length=20)
    status = models.CharField(max_length=20)
    created_at = models.DateTimeField()
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "orders"
        managed = False

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(Order, models.DO_NOTHING, db_column="order_id", related_name="order_items")
    menu_item = models.ForeignKey(MenuItem, models.DO_NOTHING, db_column="menu_item_id", related_name="order_items")
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "order_items"
        managed = False


class Payment(models.Model):
    id = models.BigAutoField(primary_key=True)
    order = models.OneToOneField(Order, models.DO_NOTHING, db_column="order_id", related_name="payment")
    payment_status = models.CharField(max_length=32)
    transaction_id = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "payments"
        managed = False


class Setting(models.Model):
    id = models.BigAutoField(primary_key=True)
    key = models.CharField(max_length=120, unique=True)
    value = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "settings"
        managed = False

    def __str__(self):
        return self.key