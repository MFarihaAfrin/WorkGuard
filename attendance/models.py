from django.db import models
from accounts.models import EmployeeRecord
from datetime import time, datetime, timedelta


WORK_START = time(9, 30)           # official start time
WORK_END = time(18, 0)             # official end time (6:00 PM)
OVERTIME_THRESHOLD = time(19, 0)   # must stay past this to count as real overtime
EARLIEST_CHECKIN = time(7, 0)      # check-in not allowed before this
LATEST_CHECKIN = time(17, 0)       # check-in not allowed after this (5:00 PM)


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        LATE = "LATE", "Late"
        EARLY_LEAVE = "EARLY_LEAVE", "Early Leave"
        OVERTIME = "OVERTIME", "Overtime"
        ABSENT = "ABSENT", "Absent"

    employee = models.ForeignKey(EmployeeRecord, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.ABSENT)

    class Meta:
        unique_together = ('employee', 'date')

    def __str__(self):
        return f"{self.employee.employee_id} - {self.date} - {self.status}"


def is_valid_checkin_time(check_in_time):
    return EARLIEST_CHECKIN <= check_in_time <= LATEST_CHECKIN


def calculate_checkin_status(check_in_time, grace_minutes=0):
    if check_in_time is None:
        return Attendance.Status.ABSENT

    cutoff_dt = datetime.combine(datetime.today(), WORK_START) + timedelta(minutes=grace_minutes)
    cutoff = cutoff_dt.time()

    if check_in_time <= cutoff:
        return Attendance.Status.PRESENT
    else:
        return Attendance.Status.LATE


def calculate_checkout_status(check_in_status, check_out_time):
    if check_out_time is None:
        return check_in_status

    if check_out_time >= OVERTIME_THRESHOLD:
        return Attendance.Status.OVERTIME
    elif check_out_time < WORK_END:
        return Attendance.Status.EARLY_LEAVE
    else:
        return check_in_status