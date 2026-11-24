from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from accounts.models import EmployeeRecord
from .models import (
    Attendance,
    calculate_checkin_status,
    calculate_checkout_status,
    is_valid_checkin_time,
)


@login_required
def mark_attendance_view(request):
    if request.user.role == 'HRF':
        return redirect('dashboard')
    
    today = timezone.localdate()
    employee = EmployeeRecord.objects.filter(employee_id=request.user.username).first()

    record, created = Attendance.objects.get_or_create(
        employee=employee,
        date=today
    )

    error = None

    if request.method == 'POST':
        action = request.POST.get('action')
        now_time = timezone.localtime().time()

        if action == 'check_in' and not record.check_in_time:
            if is_valid_checkin_time(now_time):
                grace_minutes = get_overtime_grace(employee, today)
                record.check_in_time = now_time
                record.status = calculate_checkin_status(now_time, grace_minutes)
                record.save()
            else:
                error = "Check-in is only allowed between 7:00 AM and 5:00 PM."

        elif action == 'check_out' and record.check_in_time and not record.check_out_time:
            record.check_out_time = now_time
            record.status = calculate_checkout_status(record.status, now_time)
            record.save()

        if not error:
            return redirect('mark_attendance')

    return render(request, 'attendance/mark_attendance.html', {
        'record': record,
        'user': request.user,
        'error': error
    })


def get_overtime_grace(employee, today):
    """
    If the employee worked Overtime yesterday, give them 60 extra
    grace minutes today before marking them Late.
    """
    yesterday = today - timedelta(days=1)
    yesterday_record = Attendance.objects.filter(employee=employee, date=yesterday).first()

    if yesterday_record and yesterday_record.status == Attendance.Status.OVERTIME:
        return 60
    return 0


@login_required
def attendance_history_view(request):
    if request.user.role == 'HRF':
        return redirect('dashboard')
    
    employee = EmployeeRecord.objects.filter(employee_id=request.user.username).first()
    records = Attendance.objects.filter(employee=employee).order_by('-date')

    return render(request, 'attendance/history.html', {
        'records': records,
        'user': request.user
    })


@login_required
def team_attendance_view(request):
    if request.user.role != 'MGR':
        return redirect('dashboard')

    manager = EmployeeRecord.objects.filter(employee_id=request.user.username).first()
    selected_date = request.GET.get('date') or timezone.localdate()

    records = Attendance.objects.filter(
        employee__department__manager=manager,
        date=selected_date
    ).order_by('employee__employee_id')

    return render(request, 'attendance/team.html', {
        'records': records,
        'user': request.user,
        'selected_date': selected_date
    })


@login_required
def all_attendance_view(request):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    selected_date = request.GET.get('date') or timezone.localdate()
    records = Attendance.objects.filter(date=selected_date).order_by('employee__employee_id')

    return render(request, 'attendance/all.html', {
        'records': records,
        'user': request.user,
        'selected_date': selected_date
    })


@login_required
def edit_attendance_view(request, pk):
    if request.user.role not in ['HRF', 'MGR']:
        return redirect('dashboard')

    record = Attendance.objects.filter(pk=pk).first()

    if request.method == 'POST':
        check_in = request.POST.get('check_in_time') or None
        check_out = request.POST.get('check_out_time') or None
        status = request.POST.get('status')

        record.check_in_time = check_in
        record.check_out_time = check_out
        record.status = status
        record.save()
        return redirect('all_attendance')

    return render(request, 'attendance/edit_attendance.html', {
        'record': record,
        'statuses': Attendance.Status.choices,
        'user': request.user
    })


@login_required
def employee_history_view(request, pk):
    employee = EmployeeRecord.objects.filter(pk=pk).first()

    if request.user.role == 'HRF':
        pass
    elif request.user.role == 'MGR':
        manager = EmployeeRecord.objects.filter(employee_id=request.user.username).first()
        if not employee.department or employee.department.manager != manager:
            return redirect('dashboard')
    else:
        return redirect('dashboard')

    records = Attendance.objects.filter(employee=employee).order_by('-date')

    return render(request, 'attendance/employee_history.html', {
        'employee': employee,
        'records': records,
        'user': request.user
    })


@login_required
def attendance_report_view(request):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    employees = EmployeeRecord.objects.exclude(role='HRF').order_by('employee_id')
    report = []

    for emp in employees:
        records = Attendance.objects.filter(employee=emp)
        total = records.count()
        present = records.exclude(status='ABSENT').count()
        absent = records.filter(status='ABSENT').count()
        percent = round((present / total) * 100, 2) if total > 0 else 0

        report.append({
            'employee': emp,
            'total': total,
            'present': present,
            'absent': absent,
            'percent': percent,
        })

    return render(request, 'attendance/report.html', {
        'report': report,
        'user': request.user
    })


from workguard_project.utils import render_to_pdf

@login_required
def attendance_report_pdf_view(request):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    employees = EmployeeRecord.objects.exclude(role='HRF')
    report = []

    for emp in employees:
        records = Attendance.objects.filter(employee=emp)
        total = records.count()
        present = records.exclude(status='ABSENT').count()
        absent = records.filter(status='ABSENT').count()
        percent = round((present / total) * 100, 2) if total > 0 else 0

        report.append({
            'employee': emp, 'total': total, 'present': present,
            'absent': absent, 'percent': percent,
        })

    return render_to_pdf('attendance/report_pdf.html', {'report': report}, 'attendance_report.pdf')