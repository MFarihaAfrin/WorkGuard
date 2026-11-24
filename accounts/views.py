from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import User, EmployeeRecord
from django.utils import timezone
from django.db import models

#       ---Header---
def faq_view(request):
    return render(request, 'accounts/faq.html')

def contact_view(request):
    return render(request, 'accounts/contact.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'accounts/login.html', {
                'error': 'Invalid username or password'
            })

    return render(request, 'accounts/login.html')


def landing_view(request):
    return render(request, 'accounts/landing.html')


def register_view(request):
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        company_email = request.POST.get('company_email')
        temp_password = request.POST.get('temp_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        try:
            record = EmployeeRecord.objects.get(
                employee_id=employee_id,
                company_email=company_email
            )
        except EmployeeRecord.DoesNotExist:
            return render(request, 'accounts/register.html', {
                'error': 'Registration failed. Employee ID or email not recognized.'
            })

        if record.is_registered:
            return render(request, 'accounts/register.html', {
                'error': 'This Employee ID has already been registered.'
            })

        if record.temp_password != temp_password:
            return render(request, 'accounts/register.html', {
                'error': 'Incorrect temporary password.'
            })

        if new_password != confirm_password:
            return render(request, 'accounts/register.html', {
                'error': 'New passwords do not match.'
            })

        if User.objects.filter(username=employee_id).exists():
            return render(request, 'accounts/register.html', {
                'error': 'An account with this Employee ID already exists. Please contact HR.'
            })

        user = User.objects.create_user(
            username=employee_id,
            email=company_email,
            password=new_password,
            role=record.role
        )

        from django.utils import timezone
        record.is_registered = True
        record.registered_at = timezone.now()
        record.save()

        return redirect('login')

    return render(request, 'accounts/register.html')



@login_required
def reset_password_view(request, pk):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    record = EmployeeRecord.objects.filter(pk=pk).first()

    if request.method == 'POST':
        new_temp = request.POST.get('temp_password')
        record.temp_password = new_temp
        record.is_registered = False
        record.save()

        User.objects.filter(username=record.employee_id).delete()

        return redirect('view_employee', pk=pk)

    return render(request, 'accounts/reset_password.html', {'record': record, 'user': request.user})



@login_required
def dashboard_view(request):
    role = request.user.role

    if role == 'EMP':
        from attendance.models import Attendance
        from expenses.models import ExpenseClaim

        emp_record = EmployeeRecord.objects.filter(employee_id=request.user.username).first()
        today_record = Attendance.objects.filter(employee=emp_record, date=timezone.localdate()).first()
        today_status = today_record.get_status_display() if today_record else "Not Checked In"

        pending_claims_count = ExpenseClaim.objects.filter(employee=emp_record).exclude(status__in=['APPROVED', 'REJECTED']).count()

        department = emp_record.department
        manager = department.manager if department else None

        return render(request, 'accounts/dashboard_employee.html', {
            'user': request.user,
            'today_status': today_status,
            'leave_balance': emp_record.leave_balance,
            'pending_claims_count': pending_claims_count,
            'department': department,
            'manager': manager,
        })
    elif role == 'MGR':
        manager = EmployeeRecord.objects.filter(employee_id=request.user.username).first()
        from attendance.models import Attendance
        from leave.models import Leave
        from expenses.models import ExpenseClaim

        present_count = Attendance.objects.filter(
            employee__department__manager=manager,
            date=timezone.localdate()
        ).exclude(status='ABSENT').count()

        pending_leave_count = Leave.objects.filter(
            employee__department__manager=manager, status='PENDING'
        ).count()

        pending_claims_count = ExpenseClaim.objects.filter(
            employee__department__manager=manager, status='PENDING'
        ).count()

        team_members = EmployeeRecord.objects.filter(
            department__manager=manager
        ).exclude(pk=manager.pk).order_by('employee_id')

        return render(request, 'accounts/dashboard_manager.html', {
            'user': request.user,
            'present_count': present_count,
            'pending_leave_count': pending_leave_count,
            'pending_claims_count': pending_claims_count,
            'team_members': team_members,
        })
    elif role == 'HRF':
        from attendance.models import Attendance
        from leave.models import Leave
        from expenses.models import ExpenseClaim

        total_employees = EmployeeRecord.objects.exclude(role='HRF').count()
        pending_registrations = EmployeeRecord.objects.exclude(role='HRF').filter(is_registered=False).count()
        total_departments = Department.objects.count()
        departments_budget = []
        for dept in Department.objects.all():
            percent = round((dept.budget_used / dept.budget) * 100) if dept.budget > 0 else 0
            departments_budget.append({
                'name': dept.name,
                'percent': min(percent, 100),
                'budget': dept.budget,
                'budget_used': dept.budget_used,
            })

        today = timezone.localdate()

        # --- Attendance overview (today), grouped by status ---
        today_counts = Attendance.objects.filter(date=today).values('status').annotate(count=models.Count('id'))
        status_map = {row['status']: row['count'] for row in today_counts}

        present_count = status_map.get('PRESENT', 0)
        late_count = status_map.get('LATE', 0)
        overtime_count = status_map.get('OVERTIME', 0)
        early_leave_count = status_map.get('EARLY_LEAVE', 0)
        marked_count = present_count + late_count + overtime_count + early_leave_count
        absent_count = max(total_employees - marked_count, 0)

        present_today = marked_count
        attendance_percent = round((present_today / total_employees) * 100) if total_employees > 0 else 0

        pending_leave_count = Leave.objects.filter(status='PENDING').count()

        # --- Employees by department ---
        dept_counts = EmployeeRecord.objects.exclude(role='HRF').values('department__name').annotate(count=models.Count('id')).order_by('-count')
        dept_chart_labels = [row['department__name'] or 'Unassigned' for row in dept_counts]
        dept_chart_data = [row['count'] for row in dept_counts]

        # --- Expense overview (by status) ---
        expense_status_labels = dict(ExpenseClaim.Status.choices)
        expense_counts = ExpenseClaim.objects.values('status').annotate(count=models.Count('id'))
        expense_chart_labels = [expense_status_labels.get(row['status'], row['status']) for row in expense_counts]
        expense_chart_data = [row['count'] for row in expense_counts]
        pending_claims_count = ExpenseClaim.objects.filter(status__in=['PENDING', 'MANAGER_APPROVED']).count()
        total_expense_amount = ExpenseClaim.objects.filter(status='APPROVED').aggregate(models.Sum('amount'))['amount__sum'] or 0

        # --- Risk alerts (only claims still awaiting a decision) ---
        high_risk_claims = ExpenseClaim.objects.filter(
            risk_level='High', status__in=['PENDING', 'MANAGER_APPROVED']
        ).order_by('-submitted_at')[:5]
        high_risk_count = ExpenseClaim.objects.filter(
            risk_level='High', status__in=['PENDING', 'MANAGER_APPROVED']
        ).count()
        medium_risk_count = ExpenseClaim.objects.filter(
            risk_level='Medium', status__in=['PENDING', 'MANAGER_APPROVED']
        ).count()

        # --- Recent activity feed (merged from Leave, ExpenseClaim, and new registrations) ---
        activity = []

        for lv in Leave.objects.select_related('employee').order_by('-applied_at')[:5]:
            activity.append({
                'icon': 'calendar-days',
                'text': f"{lv.employee.employee_id} applied for {lv.get_leave_type_display()}",
                'timestamp': lv.applied_at,
            })

        for claim in ExpenseClaim.objects.select_related('employee').order_by('-submitted_at')[:5]:
            activity.append({
                'icon': 'receipt',
                'text': f"{claim.employee.employee_id} submitted a {claim.get_category_display()} claim",
                'timestamp': claim.submitted_at,
            })

        for rec in EmployeeRecord.objects.exclude(registered_at__isnull=True).order_by('-registered_at')[:5]:
            activity.append({
                'icon': 'user-check',
                'text': f"{rec.employee_id} completed registration",
                'timestamp': rec.registered_at,
            })

        activity.sort(key=lambda a: a['timestamp'], reverse=True)
        recent_activity = activity[:8]

        recent_claims = ExpenseClaim.objects.all().order_by('-submitted_at')[:5]

        return render(request, 'accounts/dashboard_hr.html', {
            'user': request.user,
            'total_employees': total_employees,
            'pending_registrations': pending_registrations,
            'total_departments': total_departments,
            'attendance_percent': attendance_percent,
            'recent_claims': recent_claims,
            'present_today': present_today,
            'departments_budget': departments_budget,
            'pending_leave_count': pending_leave_count,

            

            'dept_chart_labels': dept_chart_labels,
            'dept_chart_data': dept_chart_data,

            'expense_chart_labels': expense_chart_labels,
            'expense_chart_data': expense_chart_data,
            'pending_claims_count': pending_claims_count,
            'total_expense_amount': total_expense_amount,

            'high_risk_claims': high_risk_claims,
            'high_risk_count': high_risk_count,
            'medium_risk_count': medium_risk_count,

            'recent_activity': recent_activity,
        })

@login_required
def employees_view(request):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    managers = EmployeeRecord.objects.filter(role='MGR').order_by('employee_id')
    staff = EmployeeRecord.objects.filter(role='EMP').order_by('employee_id')

    return render(request, 'accounts/employees.html', {
        'managers': managers,
        'staff': staff,
        'user': request.user
    })


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def add_employee_view(request):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        company_email = request.POST.get('company_email')
        role = request.POST.get('role')
        temp_password = request.POST.get('temp_password')
        department_id = request.POST.get('department')

        if EmployeeRecord.objects.filter(employee_id=employee_id).exists():
            return render(request, 'accounts/add_employee.html', {
                'error': 'This Employee ID already exists.',
                'user': request.user,
                'departments': Department.objects.all()
            })

        if EmployeeRecord.objects.filter(company_email=company_email).exists():
            return render(request, 'accounts/add_employee.html', {
                'error': 'This email is already used.',
                'user': request.user,
                'departments': Department.objects.all()
            })

        department = Department.objects.filter(pk=department_id).first() if department_id else None

        EmployeeRecord.objects.create(
            employee_id=employee_id,
            company_email=company_email,
            role=role,
            temp_password=temp_password,
            department=department
        )

        return redirect('employees')

    return render(request, 'accounts/add_employee.html', {
        'user': request.user,
        'departments': Department.objects.all()
    })


from django.shortcuts import get_object_or_404


@login_required
def view_employee_view(request, pk):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    record = get_object_or_404(EmployeeRecord, pk=pk)
    return render(request, 'accounts/view_employee.html', {
        'record': record,
        'user': request.user
    })


@login_required
def edit_employee_view(request, pk):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    record = get_object_or_404(EmployeeRecord, pk=pk)

    if request.method == 'POST':
        record.employee_id = request.POST.get('employee_id')
        record.company_email = request.POST.get('company_email')
        record.role = request.POST.get('role')
        department_id = request.POST.get('department')
        record.department = Department.objects.filter(pk=department_id).first() if department_id else None
        record.save()
        return redirect('employees')

    return render(request, 'accounts/edit_employee.html', {
        'record': record,
        'user': request.user,
        'departments': Department.objects.all()
    })


@login_required
def delete_employee_view(request, pk):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    record = get_object_or_404(EmployeeRecord, pk=pk)

    if request.method == 'POST':
        User.objects.filter(username=record.employee_id).delete()
        record.delete()
        return redirect('employees')

    return render(request, 'accounts/delete_employee.html', {
        'record': record,
        'user': request.user
    })


from .models import Department


@login_required
def departments_view(request):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    departments = Department.objects.all().order_by('name')
    return render(request, 'accounts/departments.html', {
        'departments': departments,
        'user': request.user
    })


@login_required
def add_department_view(request):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    if request.method == 'POST':
        name = request.POST.get('name')
        manager_id = request.POST.get('manager')
        manager = EmployeeRecord.objects.filter(pk=manager_id, role='MGR').first() if manager_id else None

        if Department.objects.filter(name=name).exists():
            return render(request, 'accounts/add_department.html', {
                'error': 'This department already exists.',
                'user': request.user,
                'managers': EmployeeRecord.objects.filter(role='MGR')
            })

        Department.objects.create(name=name, manager=manager)
        return redirect('departments')

    return render(request, 'accounts/add_department.html', {
        'user': request.user,
        'managers': EmployeeRecord.objects.filter(role='MGR')
    })


@login_required
def view_department_view(request, pk):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    department = get_object_or_404(Department, pk=pk)
    employees = department.employees.all()
    if department.manager:
        employees = employees.exclude(pk=department.manager.pk)
    employees = employees.order_by('employee_id')

    return render(request, 'accounts/view_department.html', {
        'department': department,
        'employees': employees,
        'user': request.user
    })


@login_required
def edit_department_view(request, pk):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    department = get_object_or_404(Department, pk=pk)

    if request.method == 'POST':
        department.name = request.POST.get('name')
        manager_id = request.POST.get('manager')
        department.manager = EmployeeRecord.objects.filter(pk=manager_id, role='MGR').first() if manager_id else None
        department.save()
        return redirect('departments')

    return render(request, 'accounts/edit_department.html', {
        'department': department,
        'user': request.user,
        'managers': EmployeeRecord.objects.filter(role='MGR')
    })


@login_required
def delete_department_view(request, pk):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    department = get_object_or_404(Department, pk=pk)

    if request.method == 'POST':
        department.delete()
        return redirect('departments')

    return render(request, 'accounts/delete_department.html', {
        'department': department,
        'user': request.user
    })


@login_required
def my_profile_view(request):
    record = EmployeeRecord.objects.filter(employee_id=request.user.username).first()

    if request.method == 'POST':
        record.full_name = request.POST.get('full_name')
        record.phone_number = request.POST.get('phone_number')
        record.blood_group = request.POST.get('blood_group')
        record.address = request.POST.get('address')
        record.bank_name = request.POST.get('bank_name')
        record.bank_account_number = request.POST.get('bank_account_number')
        record.save()
        return redirect('my_profile')

    return render(request, 'accounts/my_profile.html', {
        'record': record,
        'user': request.user
    })


@login_required
def notifications_view(request):
    employee = EmployeeRecord.objects.filter(employee_id=request.user.username).first()
    notifications = employee.notifications.order_by('-created_at')
    notifications.filter(is_read=False).update(is_read=True)

    return render(request, 'accounts/notifications.html', {
        'notifications': notifications,
        'user': request.user
    })


@login_required
def reports_view(request):
    if request.user.role != 'HRF':
        return redirect('dashboard')

    from expenses.models import ExpenseClaim
    from leave.models import Leave

    total_claims = ExpenseClaim.objects.count()
    approved_claims = ExpenseClaim.objects.filter(status='APPROVED').count()
    rejected_claims = ExpenseClaim.objects.filter(status='REJECTED').count()
    approval_rate = round((approved_claims / total_claims) * 100) if total_claims > 0 else 0

    total_amount = ExpenseClaim.objects.filter(status='APPROVED').aggregate(models.Sum('amount'))['amount__sum'] or 0
    avg_amount = ExpenseClaim.objects.filter(status='APPROVED').aggregate(models.Avg('amount'))['amount__avg'] or 0

    total_leave = Leave.objects.count()
    approved_leave = Leave.objects.filter(status='APPROVED').count()

    return render(request, 'accounts/reports.html', {
        'user': request.user,
        'total_claims': total_claims,
        'approved_claims': approved_claims,
        'rejected_claims': rejected_claims,
        'approval_rate': approval_rate,
        'total_amount': total_amount,
        'avg_amount': round(avg_amount, 2),
        'total_leave': total_leave,
        'approved_leave': approved_leave,
    })