from django.contrib import admin

from .models import (
    Course,
    Lecturer,
    LecturerAvailability,
    Room,
    StudentGroup,
    TimeSlot,
    TimetableEntry,
    TimetableRun,
)


@admin.register(Lecturer)
class LecturerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'department')
    search_fields = ('name', 'email')


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'capacity', 'room_type')
    list_filter = ('room_type',)


@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'size')
    list_filter = ('level',)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'level', 'lecturer', 'sessions_per_week')
    list_filter = ('level', 'department', 'requires_lab')
    search_fields = ('code', 'title')
    filter_horizontal = ('student_groups',)


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('label', 'day', 'period', 'start_time', 'end_time')
    list_filter = ('day',)


@admin.register(LecturerAvailability)
class LecturerAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('lecturer', 'time_slot', 'is_preferred')
    list_filter = ('is_preferred',)


class TimetableEntryInline(admin.TabularInline):
    model = TimetableEntry
    extra = 0
    readonly_fields = (
        'course',
        'lecturer',
        'room',
        'time_slot',
        'student_group',
        'session_index',
    )


@admin.register(TimetableRun)
class TimetableRunAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'status',
        'hard_violations',
        'soft_violations',
        'generations_run',
        'execution_seconds',
        'is_active',
        'created_at',
    )
    list_filter = ('status', 'is_active')
    inlines = [TimetableEntryInline]


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = (
        'run',
        'course',
        'lecturer',
        'room',
        'time_slot',
        'student_group',
    )
    list_filter = ('run',)
