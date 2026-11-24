from django.db import models
from accounts.models import EmployeeRecord


class ExpenseClaim(models.Model):
    class Category(models.TextChoices):
        TRAVEL = "TRAVEL", "Travel"
        MEALS = "MEALS", "Overtime Meal"
        SUPPLIES = "SUPPLIES", "Office Supplies"
        CLIENT = "CLIENT", "Client Meeting"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING = "PENDING", "Pending"
        MANAGER_APPROVED = "MANAGER_APPROVED", "Manager Approved"
        APPROVED = "APPROVED", "Approved (Final)"
        REJECTED = "REJECTED", "Rejected"

    employee = models.ForeignKey(EmployeeRecord, on_delete=models.CASCADE, related_name='claims')
    category = models.CharField(max_length=10, choices=Category.choices)
    expense_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    vendor = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=255)
    receipt = models.ImageField(upload_to='receipts/')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)
    flags = models.CharField(max_length=255, blank=True)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    ocr_detected_amount = models.CharField(max_length=20, blank=True)
    receipt_hash = models.CharField(max_length=64, blank=True)
    risk_level = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return f"{self.employee.employee_id} - {self.category} - {self.amount}"


class Payment(models.Model):
    class Method(models.TextChoices):
        BANK = "BANK", "Bank Transfer"
        CASH = "CASH", "Cash"
        CHEQUE = "CHEQUE", "Cheque"

    claim = models.OneToOneField(ExpenseClaim, on_delete=models.CASCADE, related_name='payment')
    method = models.CharField(max_length=10, choices=Method.choices)
    reference_number = models.CharField(max_length=100)
    paid_at = models.DateTimeField(auto_now_add=True)
    paid_to_account = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Payment for claim #{self.claim.id} - {self.method}"