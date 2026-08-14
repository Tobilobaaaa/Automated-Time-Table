from django.db import IntegrityError
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from openpyxl import Workbook
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .models import (
    Course,
    DayOfWeek,
    Lecturer,
    LecturerAvailability,
    Room,
    StudentGroup,
    TimeSlot,
    TimetableRun,
)
from .serializers import (
    CourseSerializer,
    GenerateTimetableSerializer,
    LecturerAvailabilitySerializer,
    LecturerSerializer,
    RoomSerializer,
    StudentGroupSerializer,
    TimeSlotSerializer,
    TimetableEntrySerializer,
    TimetableRunSerializer,
)
from .services import generate_timetable


def _safe_delete(request, model, pk, redirect_name, label='Item'):
    """Delete if the record exists; otherwise redirect with a notice (no 404 page)."""
    obj = model.objects.filter(pk=pk).first()
    if obj is None:
        messages.info(request, f'{label} was already removed or does not exist.')
        return redirect(redirect_name)
    try:
        obj.delete()
    except ProtectedError:
        messages.error(
            request,
            f'Cannot delete this {label.lower()}: it is still referenced by other records.',
        )
        return redirect(redirect_name)
    messages.success(request, f'{label} deleted.')
    return redirect(redirect_name)


# ---------------------------------------------------------------------------
# DRF API viewsets
# ---------------------------------------------------------------------------


class LecturerViewSet(viewsets.ModelViewSet):
    queryset = Lecturer.objects.all()
    serializer_class = LecturerSerializer


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer


class StudentGroupViewSet(viewsets.ModelViewSet):
    queryset = StudentGroup.objects.all()
    serializer_class = StudentGroupSerializer


class TimeSlotViewSet(viewsets.ModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.select_related('lecturer').prefetch_related('student_groups')
    serializer_class = CourseSerializer


class LecturerAvailabilityViewSet(viewsets.ModelViewSet):
    queryset = LecturerAvailability.objects.select_related('lecturer', 'time_slot')
    serializer_class = LecturerAvailabilitySerializer


class TimetableRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TimetableRun.objects.all()
    serializer_class = TimetableRunSerializer

    @action(detail=True, methods=['get'])
    def entries(self, request, pk=None):
        run = self.get_object()
        qs = run.entries.select_related(
            'course', 'lecturer', 'room', 'time_slot', 'student_group'
        )
        return Response(TimetableEntrySerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        run = self.get_object()
        run.is_active = True
        run.save()
        return Response(TimetableRunSerializer(run).data)


@api_view(['POST'])
def api_generate(request):
    serializer = GenerateTimetableSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        run = generate_timetable(**serializer.validated_data)
    except Exception as exc:  # noqa: BLE001
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(TimetableRunSerializer(run).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Browser UI views
# ---------------------------------------------------------------------------


def dashboard(request):
    active = TimetableRun.objects.filter(is_active=True).first()
    context = {
        'stats': {
            'lecturers': Lecturer.objects.count(),
            'courses': Course.objects.count(),
            'rooms': Room.objects.count(),
            'groups': StudentGroup.objects.count(),
            'slots': TimeSlot.objects.count(),
            'runs': TimetableRun.objects.count(),
        },
        'active_run': active,
        'recent_runs': TimetableRun.objects.all()[:5],
    }
    return render(request, 'scheduling/dashboard.html', context)


def lecturers_page(request):
    if request.method == 'POST':
        Lecturer.objects.create(
            name=request.POST.get('name', '').strip(),
            email=request.POST.get('email', '').strip(),
            department=request.POST.get('department', 'Computer Science').strip(),
        )
        messages.success(request, 'Lecturer added.')
        return redirect('lecturers')
    return render(
        request,
        'scheduling/lecturers.html',
        {'lecturers': Lecturer.objects.all()},
    )


def delete_lecturer(request, pk):
    lecturer = Lecturer.objects.filter(pk=pk).first()
    if lecturer is None:
        messages.info(request, 'Lecturer was already removed or does not exist.')
        return redirect('lecturers')
    courses = list(lecturer.courses.values_list('code', flat=True))
    try:
        lecturer.delete()
    except ProtectedError:
        codes = ', '.join(courses) if courses else 'assigned courses'
        messages.error(
            request,
            f'Cannot delete {lecturer.name}: still assigned to {codes}. '
            'Reassign or delete those courses first.',
        )
        return redirect('lecturers')
    messages.success(request, 'Lecturer deleted.')
    return redirect('lecturers')


def rooms_page(request):
    if request.method == 'POST':
        Room.objects.create(
            name=request.POST.get('name', '').strip(),
            capacity=int(request.POST.get('capacity', 40)),
            room_type=request.POST.get('room_type', 'lecture'),
        )
        messages.success(request, 'Room added.')
        return redirect('rooms')
    return render(request, 'scheduling/rooms.html', {'rooms': Room.objects.all()})


def delete_room(request, pk):
    return _safe_delete(request, Room, pk, 'rooms', 'Room')


def groups_page(request):
    if request.method == 'POST':
        StudentGroup.objects.create(
            name=request.POST.get('name', '').strip(),
            level=int(request.POST.get('level', 100)),
            size=int(request.POST.get('size', 40)),
        )
        messages.success(request, 'Student group added.')
        return redirect('groups')
    return render(
        request,
        'scheduling/groups.html',
        {'groups': StudentGroup.objects.all()},
    )


def delete_group(request, pk):
    return _safe_delete(request, StudentGroup, pk, 'groups', 'Student group')


def _apply_course_form(course, post):
    """Fill a Course from POST data. Returns an error message or None."""
    code = post.get('code', '').strip().upper()
    if not code:
        return 'Course code is required.'
    clash = Course.objects.filter(code=code)
    if course.pk:
        clash = clash.exclude(pk=course.pk)
    if clash.exists():
        return f'Course code "{code}" is already used. Choose a different code.'

    course.code = code
    course.title = post.get('title', '').strip()
    course.unit_load = int(post.get('unit_load', 2))
    course.level = int(post.get('level', 100))
    course.sessions_per_week = int(post.get('sessions_per_week', 1))
    course.requires_lab = post.get('requires_lab') == 'on'
    course.lecturer_id = int(post.get('lecturer'))
    course.department = post.get('department', 'Computer Science').strip()
    return None


def courses_page(request):
    if request.method == 'POST':
        course = Course()
        error = _apply_course_form(course, request.POST)
        if error:
            messages.error(request, error)
            return render(
                request,
                'scheduling/courses.html',
                _course_form_context(form_data=request.POST),
            )
        try:
            course.save()
        except IntegrityError:
            messages.error(
                request,
                f'Course code "{course.code}" is already used. Choose a different code.',
            )
            return render(
                request,
                'scheduling/courses.html',
                _course_form_context(form_data=request.POST),
            )
        course.student_groups.set(request.POST.getlist('student_groups'))
        messages.success(request, f'Course {course.code} added.')
        return redirect('courses')

    return render(request, 'scheduling/courses.html', _course_form_context())


def edit_course(request, pk):
    course = Course.objects.filter(pk=pk).select_related('lecturer').prefetch_related(
        'student_groups'
    ).first()
    if course is None:
        messages.info(request, 'Course was already removed or does not exist.')
        return redirect('courses')

    if request.method == 'POST':
        error = _apply_course_form(course, request.POST)
        if error:
            messages.error(request, error)
            return render(
                request,
                'scheduling/courses.html',
                _course_form_context(editing=course, form_data=request.POST),
            )
        try:
            course.save()
        except IntegrityError:
            messages.error(
                request,
                f'Course code "{course.code}" is already used. Choose a different code.',
            )
            return render(
                request,
                'scheduling/courses.html',
                _course_form_context(editing=course, form_data=request.POST),
            )
        course.student_groups.set(request.POST.getlist('student_groups'))
        messages.success(request, f'Course {course.code} updated.')
        return redirect('courses')

    return render(
        request,
        'scheduling/courses.html',
        _course_form_context(editing=course),
    )


def delete_course(request, pk):
    return _safe_delete(request, Course, pk, 'courses', 'Course')


def _course_form_context(editing=None, form_data=None):
    selected_ids = set()
    if form_data is not None:
        selected_ids = {int(x) for x in form_data.getlist('student_groups') if str(x).isdigit()}
    elif editing is not None:
        selected_ids = set(editing.student_groups.values_list('id', flat=True))
    return {
        'courses': Course.objects.select_related('lecturer').prefetch_related(
            'student_groups'
        ),
        'lecturers': Lecturer.objects.all(),
        'groups': StudentGroup.objects.all(),
        'editing': editing,
        'selected_group_ids': selected_ids,
        'form_data': form_data,
    }
def slots_page(request):
    if request.method == 'POST':
        from datetime import time as dtime

        day = request.POST.get('day')
        period = int(request.POST.get('period', 1))
        start = request.POST.get('start_time', '08:00')
        end = request.POST.get('end_time', '09:00')
        sh, sm = map(int, start.split(':'))
        eh, em = map(int, end.split(':'))
        TimeSlot.objects.create(
            day=day,
            period=period,
            start_time=dtime(sh, sm),
            end_time=dtime(eh, em),
        )
        messages.success(request, 'Time slot added.')
        return redirect('slots')

    return render(
        request,
        'scheduling/slots.html',
        {'slots': TimeSlot.objects.all(), 'days': DayOfWeek.choices},
    )


def delete_slot(request, pk):
    return _safe_delete(request, TimeSlot, pk, 'slots', 'Time slot')


def availability_page(request):
    if request.method == 'POST':
        LecturerAvailability.objects.update_or_create(
            lecturer_id=int(request.POST.get('lecturer')),
            time_slot_id=int(request.POST.get('time_slot')),
            defaults={'is_preferred': request.POST.get('is_preferred') == 'on'},
        )
        messages.success(request, 'Availability preference saved.')
        return redirect('availability')

    return render(
        request,
        'scheduling/availability.html',
        {
            'prefs': LecturerAvailability.objects.select_related(
                'lecturer', 'time_slot'
            ),
            'lecturers': Lecturer.objects.all(),
            'slots': TimeSlot.objects.all(),
        },
    )


def delete_availability(request, pk):
    return _safe_delete(
        request, LecturerAvailability, pk, 'availability', 'Preference'
    )

def generate_page(request):
    if request.method == 'POST':
        try:
            run = generate_timetable(
                name=request.POST.get('name', '').strip(),
                population_size=int(request.POST.get('population_size', 80)),
                max_generations=int(request.POST.get('max_generations', 200)),
                crossover_prob=float(request.POST.get('crossover_prob', 0.7)),
                mutation_prob=float(request.POST.get('mutation_prob', 0.2)),
                publish=request.POST.get('publish') == 'on',
            )
            if run.hard_violations == 0:
                messages.success(
                    request,
                    f'{run.name}: clash-free timetable in {run.generations_run} '
                    f'generations ({run.execution_seconds}s).',
                )
            else:
                messages.warning(
                    request,
                    f'{run.name}: finished with {run.hard_violations} hard and '
                    f'{run.soft_violations} soft violations.',
                )
            return redirect('timetable_detail', pk=run.pk)
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f'Generation failed: {exc}')
            return redirect('generate')

    return render(
        request,
        'scheduling/generate.html',
        {
            'course_count': Course.objects.count(),
            'room_count': Room.objects.count(),
            'slot_count': TimeSlot.objects.count(),
            'runs': TimetableRun.objects.all()[:10],
        },
    )


def _grid_for_run(run: TimetableRun):
    entries = list(
        run.entries.select_related(
            'course', 'lecturer', 'room', 'time_slot', 'student_group'
        )
    )
    days = [d[0] for d in DayOfWeek.choices]
    all_periods = sorted(set(TimeSlot.objects.values_list('period', flat=True)))
    if not all_periods:
        all_periods = sorted({e.time_slot.period for e in entries}) or list(range(1, 9))

    grid = {day: {p: [] for p in all_periods} for day in days}
    for e in entries:
        grid[e.time_slot.day][e.time_slot.period].append(e)

    period_labels = {}
    for slot in TimeSlot.objects.all():
        if slot.period not in period_labels:
            period_labels[slot.period] = (
                f'{slot.start_time.strftime("%H:%M")}–{slot.end_time.strftime("%H:%M")}'
            )

    return {
        'days': days,
        'periods': all_periods,
        'period_labels': period_labels,
        'grid': grid,
        'entries': entries,
    }


def timetable_list(request):
    return render(
        request,
        'scheduling/timetable_list.html',
        {'runs': TimetableRun.objects.all()},
    )


def timetable_detail(request, pk):
    run = get_object_or_404(TimetableRun, pk=pk)
    context = {'run': run, **_grid_for_run(run)}
    return render(request, 'scheduling/timetable_detail.html', context)


def timetable_active(request):
    run = TimetableRun.objects.filter(is_active=True).first()
    if not run:
        messages.info(request, 'No published timetable yet. Generate one first.')
        return redirect('generate')
    context = {'run': run, **_grid_for_run(run)}
    return render(request, 'scheduling/timetable_detail.html', context)


def export_timetable(request, pk):
    run = get_object_or_404(TimetableRun, pk=pk)
    entries = run.entries.select_related(
        'course', 'lecturer', 'room', 'time_slot', 'student_group'
    ).order_by('time_slot__day', 'time_slot__period')

    wb = Workbook()
    ws = wb.active
    ws.title = 'Timetable'
    ws.append(
        [
            'Day',
            'Period',
            'Time',
            'Course Code',
            'Course Title',
            'Lecturer',
            'Room',
            'Student Group',
            'Session',
        ]
    )
    for e in entries:
        ws.append(
            [
                e.time_slot.day,
                e.time_slot.period,
                e.time_slot.label,
                e.course.code,
                e.course.title,
                e.lecturer.name,
                e.room.name,
                e.student_group.name if e.student_group else '',
                e.session_index,
            ]
        )

    response = HttpResponse(
        content_type=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    )
    filename = (run.name or 'timetable').replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    wb.save(response)
    return response


def publish_run(request, pk):
    run = get_object_or_404(TimetableRun, pk=pk)
    run.is_active = True
    run.save()
    messages.success(request, f'{run.name} is now the published timetable.')
    return redirect('timetable_detail', pk=pk)
