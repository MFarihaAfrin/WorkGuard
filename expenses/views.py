from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from accounts.models import EmployeeRecord, notify, notify_hr
from .models import ExpenseClaim
from accounts.models import Department

from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Avg
from attendance.models import Attendance

import joblib
import os

RISK_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'risk_model.pkl')
risk_model = joblib.load(RISK_MODEL_PATH)
RISK_LABELS = {0: 'Low', 1: 'Medium', 2: 'High'}


def predict_risk(amount, num_flags):
    amount_ratio = min(float(amount) / 500.0, 1.0)
    prediction = risk_model.predict([[amount_ratio, num_flags]])[0]
    return RISK_LABELS[prediction]

import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

CATEGORY_LIMITS = {
    "TRAVEL": 500,
    "MEALS": 100,
    "SUPPLIES": 200,
    "CLIENT": 300,
    "OTHERS": 150,
}

ALLOWED_RECEIPT_EXTENSIONS = [".jpg", ".jpeg", ".png"]
MAX_RECEIPT_SIZE_MB = 5


def check_attendance_match(employee, category, expense_date):
    if category != "MEALS":
        return None
    record = Attendance.objects.filter(employee=employee, date=expense_date).first()
    if not record or record.status != "OVERTIME":
        return "Attendance mismatch: no overtime recorded that day"
    return None


def check_unusual_amount(employee, category, amount):
    past_avg = ExpenseClaim.objects.filter(
        employee=employee, category=category
    ).aggregate(Avg("amount"))["amount__avg"]
    if past_avg and amount > (past_avg * 2):
        return f"Unusually high (avg for this category: ${past_avg:.2f})"
    return None


def check_budget(employee, amount):
    department = employee.department
    if not department:
        return None
    remaining = department.budget - department.budget_used
    if amount > remaining:
        return f"Exceeds department budget (${remaining:.2f} remaining)"
    return None


def validate_receipt_file(receipt_file):

    import os

    ext = os.path.splitext(receipt_file.name)[1].lower()

    if ext not in ALLOWED_RECEIPT_EXTENSIONS:
        return (
            "Unsupported file type. Please upload a JPG or PNG photo of your receipt."
        )

    if receipt_file.size > MAX_RECEIPT_SIZE_MB * 1024 * 1024:
        return (
            f"File is too large. Please upload an image under {MAX_RECEIPT_SIZE_MB}MB."
        )

    try:
        img = Image.open(receipt_file)
        img.verify()
    except Exception:
        return "This file isn't a valid image. Please upload a clear photo of your receipt."
    finally:
        receipt_file.seek(0)

    return None


@login_required
def submit_claim_view(request):
    employee = EmployeeRecord.objects.filter(employee_id=request.user.username).first()

    if request.method == 'POST':
        category = request.POST.get('category')
        description = request.POST.get('description')
        receipt_file = request.FILES.get('receipt')

        file_error = validate_receipt_file(receipt_file)
        if file_error:
            return render(request, 'expenses/submit.html', {'error': file_error, 'limits': CATEGORY_LIMITS})

        ocr_text = extract_receipt_text(receipt_file)
        ocr_amount = guess_amount_from_text(ocr_text)
        ocr_vendor = guess_vendor_from_text(ocr_text)
        ocr_date = guess_date_from_text(ocr_text)
        receipt_file.seek(0)

        file_hash = hash_file(receipt_file)
        already_used = ExpenseClaim.objects.filter(
            receipt_hash=file_hash
        ).exclude(status=ExpenseClaim.Status.DRAFT).exists()

        if already_used:
            return render(request, 'expenses/submit.html', {
                'error': "This exact receipt photo has already been submitted in a previous claim.",
                'limits': CATEGORY_LIMITS,
            })

        draft = ExpenseClaim.objects.create(
            employee=employee,
            category=category,
            description=description,
            receipt=receipt_file,
            receipt_hash=file_hash,
            ocr_detected_amount=str(ocr_amount) if ocr_amount else "",
            amount=ocr_amount,
            expense_date=ocr_date,
            vendor=ocr_vendor,
            status=ExpenseClaim.Status.DRAFT,
        )
        return redirect('confirm_claim', pk=draft.id)

    return render(request, 'expenses/submit.html', {'limits': CATEGORY_LIMITS})


@login_required
def confirm_claim_view(request, pk):
    employee = EmployeeRecord.objects.filter(employee_id=request.user.username).first()
    claim = ExpenseClaim.objects.filter(
        pk=pk, employee=employee, status=ExpenseClaim.Status.DRAFT
    ).first()

    if not claim:
        return redirect('my_claims')

    if request.method == 'POST':
        vendor = request.POST.get('vendor', '').strip()
        amount_input = request.POST.get('amount')
        date_input = request.POST.get('expense_date')

        if not amount_input:
            return render(request, 'expenses/confirm.html', {'claim': claim, 'error': "Please enter the amount before confirming."})

        if not date_input:
            return render(request, 'expenses/confirm.html', {'claim': claim, 'error': "Please enter the expense date before confirming."})

        amount = Decimal(amount_input)
        expense_date = datetime.strptime(date_input, '%Y-%m-%d').date()

        if amount <= 0:
            return render(request, 'expenses/confirm.html', {'claim': claim, 'error': "Amount must be greater than zero."})

        if expense_date > timezone.localdate():
            return render(request, 'expenses/confirm.html', {'claim': claim, 'error': "Expense date cannot be in the future."})

        limit = CATEGORY_LIMITS.get(claim.category, 0)
        if amount > limit:
            return render(request, 'expenses/confirm.html', {'claim': claim, 'error': f"Amount exceeds the ${limit} limit for this category."})

        flags = []
        risk_flag_count = 0

        presence_flag = check_employee_present(employee, expense_date)
        if presence_flag:
            flags.append(presence_flag)
            risk_flag_count += 1

        mismatch = check_attendance_match(employee, claim.category, expense_date)
        if mismatch:
            flags.append(mismatch)
            risk_flag_count += 1

        unusual = check_unusual_amount(employee, claim.category, amount)
        if unusual:
            flags.append(unusual)
            risk_flag_count += 1

        budget_flag = check_budget(employee, amount)
        if budget_flag:
            flags.append(budget_flag)
            risk_flag_count += 1

        if claim.ocr_detected_amount:
            ocr_amount_decimal = Decimal(claim.ocr_detected_amount)
            if abs(ocr_amount_decimal - amount) > 5:
                flags.append(f"Receipt originally read as ${ocr_amount_decimal}, employee confirmed ${amount}")
                risk_flag_count += 1
        else:
            flags.append("OCR could not read an amount — employee entered it manually")

        risk = predict_risk(amount, risk_flag_count)

        claim.vendor = vendor
        claim.amount = amount
        claim.expense_date = expense_date
        claim.flags = ", ".join(flags)
        claim.risk_level = risk
        claim.status = ExpenseClaim.Status.PENDING
        claim.save()

        return redirect('my_claims')

    return render(request, 'expenses/confirm.html', {'claim': claim})


@login_required
def my_claims_view(request):
    employee = EmployeeRecord.objects.filter(employee_id=request.user.username).first()
    claims = ExpenseClaim.objects.filter(employee=employee).order_by("-submitted_at")

    return render(
        request, "expenses/my_claims.html", {"claims": claims, "user": request.user}
    )


@login_required
def team_claims_view(request):
    if request.user.role != "MGR":
        return redirect("dashboard")

    manager = EmployeeRecord.objects.filter(employee_id=request.user.username).first()
    claims = ExpenseClaim.objects.filter(
        employee__department__manager=manager
    ).order_by("-submitted_at")

    department = Department.objects.filter(manager=manager).first()
    remaining_budget = None
    if department:
        remaining_budget = department.budget - department.budget_used

    return render(
        request,
        "expenses/team.html",
        {
            "claims": claims,
            "user": request.user,
            "department": department,
            "remaining_budget": remaining_budget,
        },
    )


@login_required
def decide_claim_view(request, pk):
    if request.user.role != "MGR":
        return redirect("dashboard")

    claim = ExpenseClaim.objects.filter(pk=pk).first()

    if request.method == "POST" and claim.status == "PENDING":
        decision = request.POST.get("decision")

        if decision == 'approve':
            claim.status = 'MANAGER_APPROVED'
            notify(claim.employee, f"Your {claim.get_category_display()} claim (${claim.amount}) was approved by your manager, pending HR final approval.")
            notify_hr(f"{claim.employee.employee_id}'s {claim.get_category_display()} claim (${claim.amount}) is awaiting your final approval.")
        else:
            claim.status = "REJECTED"
            notify(
                claim.employee,
                f"Your {claim.get_category_display()} claim (${claim.amount}) was rejected.",
            )

        claim.save()

    return redirect("team_claims")


def check_employee_present(employee, expense_date):
    record = Attendance.objects.filter(employee=employee, date=expense_date).first()
    if not record or record.status == "ABSENT":
        return "Employee was not marked present on the expense date"
    return None


#             """  OCR Extraction  """
from PIL import Image
import re


def extract_receipt_text(receipt_file):
    try:
        receipt_file.seek(0)
        img = Image.open(receipt_file)
        text = pytesseract.image_to_string(img)
        return text
    except Exception:
        return ""


#           """guesses the total amount from that messy text"""

def guess_amount_from_text(text):
    
    if not text:
        return None

    #   Normalize common European comma decimals 
    normalized_text = re.sub(r',(\d{2})\b', r'.\1', text)
    
    lines = normalized_text.splitlines()
    total_pattern = re.compile(r'\b(grand total|amount due|total due|total)\b', re.IGNORECASE)
    
    for line in reversed(lines):
        if total_pattern.search(line):
            matches = re.findall(r'\d+\.\d{2}', line)

            if matches:
                return float(matches[-1])
            int_matches = re.findall(r'\b\d+\b', line)

            if int_matches:
                return float(int_matches[-1])

    cleaned_text_lines = [line for line in lines if "subtotal" not in line.lower()]
    cleaned_text = "\n".join(cleaned_text_lines)
    
    all_decimals = re.findall(r'\d+\.\d{2}', cleaned_text)
    if all_decimals:
        return max([float(m) for m in all_decimals])
        
    return None



def guess_vendor_from_text(text):
    
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    # Exclude common systemic headers if they appear at the top
    omit_keywords = ['invoice', 'receipt', 'bill', 'statement', 'tax']
    
    for line in lines[:3]:  
        if not any(kw in line.lower() for kw in omit_keywords):
            # Clean up trailing junk/symbols
            clean_name = re.sub(r'[^a-zA-Z0-9\s-]', '', line).strip()
            if clean_name:
                return clean_name
    return "Unknown Vendor"

def guess_date_from_text(text):
    if not text:
        return None
        
    date_pattern = re.compile(r'\b(\d{1,2})[-/\s]([A-Za-z]+|\d{1,2})[-/\s](\d{2,4})\b')
    match = date_pattern.search(text)
    
    if match:
        day, month, year = match.groups()
        try:
            if month.isalpha():
                dt = datetime.strptime(f"{day} {month[:3]} {year}", "%d %b %Y").date()
            else:
                dt = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d").date()
            return dt
        except Exception:
            pass
            
    return timezone.localdate()


import hashlib


def hash_file(file_obj):
    """
    Generates a unique SHA-256 string for duplicate submission validation checks.
    """
    hasher = hashlib.sha256()
    file_obj.seek(0)
    for chunk in file_obj.chunks():
        hasher.update(chunk)
    file_obj.seek(0)
    return hasher.hexdigest()


@login_required
def budget_overview_view(request):
    if request.user.role != "HRF":
        return redirect("dashboard")

    departments = Department.objects.all()
    for dept in departments:
        dept.remaining = dept.budget - dept.budget_used

    return render(
        request,
        "expenses/budgets.html",
        {"departments": departments, "user": request.user},
    )


@login_required
def final_approval_view(request):
    if request.user.role != "HRF":
        return redirect("dashboard")

    claims = ExpenseClaim.objects.all().order_by("-submitted_at")
    return render(
        request,
        "expenses/final_approval.html",
        {"claims": claims, "user": request.user},
    )


@login_required
def final_decide_view(request, pk):
    if request.user.role != "HRF":
        return redirect("dashboard")

    claim = ExpenseClaim.objects.filter(pk=pk).first()

    if request.method == "POST" and claim.status == "MANAGER_APPROVED":
        decision = request.POST.get("decision")

        if decision == "approve":
            department = claim.employee.department
            if department and claim.amount > (
                department.budget - department.budget_used
            ):
                notify(
                    claim.employee,
                    f"Your {claim.get_category_display()} claim could not be finalized — department budget exceeded.",
                )
            else:
                if department:
                    department.budget_used += claim.amount
                    department.save()
                claim.status = "APPROVED"
                notify(
                    claim.employee,
                    f"Your {claim.get_category_display()} claim (${claim.amount}) was fully approved for payment.",
                )
        else:
            claim.status = "REJECTED"
            notify(
                claim.employee,
                f"Your {claim.get_category_display()} claim (${claim.amount}) was rejected by HR.",
            )

        claim.save()

    return redirect("final_approval")


@login_required
def delete_claim_view(request, pk):
    claim = ExpenseClaim.objects.filter(pk=pk).first()
    if not claim or claim.status == "APPROVED":
        return redirect(request.META.get("HTTP_REFERER", "my_claims"))

    if request.user.role == "HRF":
        pass
    elif request.user.role == "MGR":
        manager = EmployeeRecord.objects.filter(
            employee_id=request.user.username
        ).first()
        if (
            not claim.employee.department
            or claim.employee.department.manager != manager
        ):
            return redirect("team_claims")
    elif request.user.role == "EMP":
        if claim.employee.employee_id != request.user.username:
            return redirect("my_claims")
    else:
        return redirect("dashboard")

    if request.method == "POST":
        claim.delete()

    return redirect(request.META.get("HTTP_REFERER", "my_claims"))


from .models import Payment


@login_required
def mark_paid_view(request, pk):
    if request.user.role != "HRF":
        return redirect("dashboard")

    claim = ExpenseClaim.objects.filter(pk=pk, status="APPROVED", is_paid=False).first()
    if not claim:
        return redirect("final_approval")

    if request.method == "POST":
        Payment.objects.create(
            claim=claim,
            method=request.POST.get("method"),
            reference_number=request.POST.get("reference_number"),
            paid_to_account=f"{claim.employee.bank_name} - {claim.employee.bank_account_number}",
        )
        claim.is_paid = True
        claim.save()
        notify(
            claim.employee,
            f"Your {claim.get_category_display()} claim (${claim.amount}) has been paid via {request.POST.get('method')}.",
        )
        return redirect("final_approval")

    return render(
        request, "expenses/mark_paid.html", {"claim": claim, "user": request.user}
    )


from workguard_project.utils import render_to_pdf

@login_required
def claim_pdf_view(request, pk):
    claim = ExpenseClaim.objects.filter(pk=pk).first()

    if not claim or claim.employee.employee_id != request.user.username:
        return redirect('my_claims')

    if not claim.is_paid:
        return redirect('my_claims')

    return render_to_pdf('expenses/claim_pdf.html', {'claim': claim}, f'claim_{claim.id}.pdf')