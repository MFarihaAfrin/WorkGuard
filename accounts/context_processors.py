from .models import EmployeeRecord

def unread_notifications(request):
    if request.user.is_authenticated:
        employee = EmployeeRecord.objects.filter(employee_id=request.user.username).first()
        if employee:
            return {'unread_count': employee.notifications.filter(is_read=False).count()}
    return {'unread_count': 0}

