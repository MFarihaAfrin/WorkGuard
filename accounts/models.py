from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinValueValidator


class User(AbstractUser):
    class Role(models.TextChoices):
        EMPLOYEE = "EMP", "Employee"
        MANAGER = "MGR", "Manager"
        HR_FINANCE = "HRF", "HR/Finance Admin"

    role = models.CharField(
        max_length=3,
        choices=Role.choices,
        default=Role.EMPLOYEE
    )


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    manager = models.ForeignKey('EmployeeRecord', null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_department', limit_choices_to={'role': 'MGR'})
    created_at = models.DateTimeField(auto_now_add=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=10000, validators=[MinValueValidator(0)])
    budget_used = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return self.name


class EmployeeRecord(models.Model):
    class Role(models.TextChoices):
        EMPLOYEE = "EMP", "Employee"
        MANAGER = "MGR", "Manager"
        HR_FINANCE = "HRF", "HR/Finance Admin"

    employee_id = models.CharField(max_length=20, unique=True)
    company_email = models.EmailField(unique=True)
    role = models.CharField(max_length=3, choices=Role.choices, default=Role.EMPLOYEE)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name='employees')
    temp_password = models.CharField(max_length=128, default='')
    is_registered = models.BooleanField(default=False)
    added_at = models.DateTimeField(auto_now_add=True)
    registered_at = models.DateTimeField(null=True, blank=True)

    full_name = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    blood_group = models.CharField(max_length=5, blank=True)
    address = models.CharField(max_length=255, blank=True)

    leave_balance = models.IntegerField(default=20)

    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.employee_id} - {self.company_email}"


class Notification(models.Model):
    employee = models.ForeignKey(EmployeeRecord, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee.employee_id}: {self.message}"


def notify(employee, message):
    Notification.objects.create(employee=employee, message=message)

def notify_hr(message):
    hr_users = EmployeeRecord.objects.filter(role='HRF')
    for hr_person in hr_users:
        Notification.objects.create(employee=hr_person, message=message)