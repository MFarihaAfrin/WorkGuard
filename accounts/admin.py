from django.contrib import admin
from .models import User, EmployeeRecord, Department

admin.site.register(User)
admin.site.register(EmployeeRecord)
admin.site.register(Department)