"""
Seed a realistic Computer Science departmental dataset for testing.

Usage:
    python manage.py seed_sample_data
"""

from datetime import time

from django.core.management.base import BaseCommand
from django.db import transaction

from scheduling.models import (
    Course,
    DayOfWeek,
    Lecturer,
    LecturerAvailability,
    Room,
    StudentGroup,
    TimeSlot,
)


class Command(BaseCommand):
    help = 'Load sample lecturers, rooms, groups, slots, courses and preferences.'

    @transaction.atomic
    def handle(self, *args, **options):
        if Course.objects.exists():
            self.stdout.write(self.style.WARNING('Data already present — clearing scheduling tables…'))
            Course.objects.all().delete()
            LecturerAvailability.objects.all().delete()
            TimeSlot.objects.all().delete()
            StudentGroup.objects.all().delete()
            Room.objects.all().delete()
            Lecturer.objects.all().delete()

        lecturers = [
            Lecturer.objects.create(name='Dr. Adebayo Okonkwo', email='adebayo@uni.edu', department='Computer Science'),
            Lecturer.objects.create(name='Prof. Chioma Eze', email='chioma@uni.edu', department='Computer Science'),
            Lecturer.objects.create(name='Dr. Ibrahim Musa', email='ibrahim@uni.edu', department='Computer Science'),
            Lecturer.objects.create(name='Mrs. Funke Adeyemi', email='funke@uni.edu', department='Computer Science'),
            Lecturer.objects.create(name='Dr. Ngozi Okafor', email='ngozi@uni.edu', department='Computer Science'),
        ]

        rooms = [
            Room.objects.create(name='LT1', capacity=120, room_type='lecture'),
            Room.objects.create(name='LT2', capacity=80, room_type='lecture'),
            Room.objects.create(name='SR3', capacity=50, room_type='seminar'),
            Room.objects.create(name='Lab A', capacity=55, room_type='lab'),
            Room.objects.create(name='Lab B', capacity=50, room_type='lab'),
        ]

        groups = {
            100: StudentGroup.objects.create(name='CSC 100', level=100, size=55),
            200: StudentGroup.objects.create(name='CSC 200', level=200, size=48),
            300: StudentGroup.objects.create(name='CSC 300', level=300, size=42),
            400: StudentGroup.objects.create(name='CSC 400', level=400, size=36),
        }

        # Mon–Fri, periods 1–6 (skip lunch as period 4 gap conceptually still numbered)
        period_times = [
            (1, time(8, 0), time(9, 0)),
            (2, time(9, 0), time(10, 0)),
            (3, time(10, 0), time(11, 0)),
            (4, time(11, 0), time(12, 0)),
            (5, time(13, 0), time(14, 0)),
            (6, time(14, 0), time(15, 0)),
        ]
        slots = []
        for day, _ in DayOfWeek.choices:
            for period, start, end in period_times:
                slots.append(
                    TimeSlot.objects.create(
                        day=day, period=period, start_time=start, end_time=end
                    )
                )

        course_defs = [
            ('CSC 101', 'Introduction to Computing', 100, lecturers[0], 2, False),
            ('CSC 102', 'Problem Solving', 100, lecturers[3], 2, False),
            ('CSC 201', 'Data Structures', 200, lecturers[1], 2, False),
            ('CSC 202', 'Computer Architecture', 200, lecturers[2], 1, False),
            ('CSC 203', 'Programming Lab', 200, lecturers[3], 1, True),
            ('CSC 301', 'Operating Systems', 300, lecturers[0], 2, False),
            ('CSC 302', 'Database Systems', 300, lecturers[1], 2, False),
            ('CSC 303', 'Software Engineering', 300, lecturers[4], 1, False),
            ('CSC 304', 'Networks Lab', 300, lecturers[2], 1, True),
            ('CSC 401', 'Artificial Intelligence', 400, lecturers[4], 2, False),
            ('CSC 402', 'Compiler Construction', 400, lecturers[1], 1, False),
            ('CSC 403', 'Project Seminar', 400, lecturers[0], 1, False),
        ]

        for code, title, level, lecturer, sessions, lab in course_defs:
            course = Course.objects.create(
                code=code,
                title=title,
                unit_load=3 if sessions > 1 else 2,
                level=level,
                sessions_per_week=sessions,
                requires_lab=lab,
                lecturer=lecturer,
                department='Computer Science',
            )
            course.student_groups.add(groups[level])

        # Soft prefs: Dr. Adebayo prefers mornings Mon/Tue; Prof. Chioma unavailable Friday P6
        morning = [s for s in slots if s.day in ('Monday', 'Tuesday') and s.period <= 2]
        for s in morning[:4]:
            LecturerAvailability.objects.create(
                lecturer=lecturers[0], time_slot=s, is_preferred=True
            )
        friday_late = next(s for s in slots if s.day == 'Friday' and s.period == 6)
        LecturerAvailability.objects.create(
            lecturer=lecturers[1], time_slot=friday_late, is_preferred=False
        )

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(lecturers)} lecturers, {len(rooms)} rooms, '
            f'{len(groups)} groups, {len(slots)} slots, {len(course_defs)} courses.'
        ))
