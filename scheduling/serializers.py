from rest_framework import serializers

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


class LecturerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lecturer
        fields = ['id', 'name', 'email', 'department']


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ['id', 'name', 'capacity', 'room_type']


class StudentGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentGroup
        fields = ['id', 'name', 'level', 'size']


class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = ['id', 'day', 'period', 'start_time', 'end_time', 'label']


class LecturerAvailabilitySerializer(serializers.ModelSerializer):
    lecturer_name = serializers.CharField(source='lecturer.name', read_only=True)
    time_slot_label = serializers.CharField(source='time_slot.__str__', read_only=True)

    class Meta:
        model = LecturerAvailability
        fields = [
            'id',
            'lecturer',
            'lecturer_name',
            'time_slot',
            'time_slot_label',
            'is_preferred',
        ]


class CourseSerializer(serializers.ModelSerializer):
    lecturer_name = serializers.CharField(source='lecturer.name', read_only=True)
    student_group_names = serializers.SerializerMethodField()
    class_size = serializers.IntegerField(read_only=True)

    class Meta:
        model = Course
        fields = [
            'id',
            'code',
            'title',
            'unit_load',
            'department',
            'level',
            'sessions_per_week',
            'requires_lab',
            'lecturer',
            'lecturer_name',
            'student_groups',
            'student_group_names',
            'class_size',
        ]

    def get_student_group_names(self, obj):
        return [g.name for g in obj.student_groups.all()]


class TimetableEntrySerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source='course.code', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    lecturer_name = serializers.CharField(source='lecturer.name', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)
    day = serializers.CharField(source='time_slot.day', read_only=True)
    period = serializers.IntegerField(source='time_slot.period', read_only=True)
    slot_label = serializers.CharField(source='time_slot.label', read_only=True)
    group_name = serializers.CharField(
        source='student_group.name', read_only=True, default=None
    )

    class Meta:
        model = TimetableEntry
        fields = [
            'id',
            'run',
            'course',
            'course_code',
            'course_title',
            'lecturer',
            'lecturer_name',
            'room',
            'room_name',
            'time_slot',
            'day',
            'period',
            'slot_label',
            'student_group',
            'group_name',
            'session_index',
        ]


class TimetableRunSerializer(serializers.ModelSerializer):
    entry_count = serializers.IntegerField(source='entries.count', read_only=True)

    class Meta:
        model = TimetableRun
        fields = [
            'id',
            'name',
            'status',
            'population_size',
            'max_generations',
            'crossover_prob',
            'mutation_prob',
            'generations_run',
            'best_fitness',
            'hard_violations',
            'soft_violations',
            'execution_seconds',
            'fitness_history',
            'message',
            'is_active',
            'entry_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'status',
            'generations_run',
            'best_fitness',
            'hard_violations',
            'soft_violations',
            'execution_seconds',
            'fitness_history',
            'message',
            'created_at',
            'updated_at',
        ]


class GenerateTimetableSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    population_size = serializers.IntegerField(min_value=20, max_value=300, default=80)
    max_generations = serializers.IntegerField(min_value=10, max_value=1000, default=200)
    crossover_prob = serializers.FloatField(min_value=0.1, max_value=1.0, default=0.7)
    mutation_prob = serializers.FloatField(min_value=0.01, max_value=1.0, default=0.2)
    publish = serializers.BooleanField(default=True)
