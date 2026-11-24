from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from accounts.models import EmployeeRecord
from .models import Leave
from accounts.models import EmployeeRecord, notify, notify_hr


from datetime import datetime
from django.utils import timezone

@login_required
def apply_leave_view(request):
    employee = EmployeeRecord.objects.filter(employee_id=request.user.username).first()
    if not employee:
        return redirect('dashboard')

    error = None

    if request.method == 'POST':
        start = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
        end = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%d').date()
        days = (end - start).days + 1
        leave_type = request.POST.get('leave_type')
        document = request.FILES.get('document')

        from datetime import timedelta

        if start < timezone.localdate():
            error = "Start date cannot be in the past."
        elif end < start:
            error = "End date cannot be before start date."
        elif days > 3:
            error = "Maximum 3 days can be requested through the portal. For longer leave, please contact HR directly."
        elif leave_type == 'SICK' and not document:
            error = "A medical document is required for Sick Leave requests."
        elif employee.leave_balance < days:
            error = f"Insufficient leave balance. You have {employee.leave_balance} day(s) remaining."
        elif Leave.objects.filter(
            employee=employee,
            status__in=['PENDING', 'APPROVED']
        ).filter(start_date__lte=end, end_date__gte=start).exists():
            error = "You already have a pending or approved leave request that overlaps with these dates."
        else:
            Leave.objects.create(
                employee=employee,
                leave_type=request.POST.get('leave_type'),
                start_date=start,
                end_date=end,
                reason=request.POST.get('reason'),
                document=document,
            )
            if employee.role == 'MGR':
                notify_hr(f"{employee.employee_id} (Manager) submitted a leave request awaiting your approval.")
            return redirect('leave_history')
        
    return render(request, 'leave/apply.html', {
        'user': request.user,
        'leave_balance': employee.leave_balance,
        'error': error,
        'today': timezone.localdate()
})

@login_required
def leave_history_view(request):
    employee = EmployeeRecord.objects.filter(employee_id=request.user.username).first()
    requests = Leave.objects.filter(employee=employee).order_by('-applied_at')

    return render(request, 'leave/history.html', {
        'requests': requests,
        'user': request.user,
        'leave_balance': employee.leave_balance
    })


@login_required
def team_leave_view(request):
    if request.user.role != 'MGR':
        return redirect('dashboard')

    manager = EmployeeRecord.objects.filter(employee_id=request.user.username).first()
    requests = Leave.objects.filter(employee__department__manager=manager).order_by('-applied_at')

    return render(request, 'leave/team.html', {'requests': requests, 'user': request.user})


@login_required
def decide_leave_view(request, pk):
    if request.user.role not in ['MGR', 'HRF']:
        return redirect('dashboard')

    leave_request = Leave.objects.filter(pk=pk).first()

    if request.method == 'POST':
        decision = request.POST.get('decision')

        if decision == 'approve' and leave_request.status == 'PENDING':
            days = leave_request.total_days()
            employee = leave_request.employee

            if employee.leave_balance >= days:
                employee.leave_balance -= days
                employee.save()
                leave_request.status = 'APPROVED'
                notify(employee, f"Your {leave_request.get_leave_type_display()} request was approved.")
            else:
                leave_request.status = 'REJECTED'
                notify(employee, f"Your {leave_request.get_leave_type_display()} request was rejected (insufficient balance).")

        elif decision == 'reject':
            leave_request.status = 'REJECTED'
            notify(leave_request.employee, f"Your {leave_request.get_leave_type_display()} request was rejected.")

        leave_request.save()
        return redirect('team_leave')

    return redirect('team_leave')


@login_required
def all_leave_view(request):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    requests = Leave.objects.filter(employee__role='MGR').order_by('-applied_at')

    return render(request, 'leave/all.html', {'requests': requests, 'user': request.user})