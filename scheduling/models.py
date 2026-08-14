from django.db import models


class DayOfWeek(models.TextChoices):
    MONDAY = 'Monday', 'Monday'
    TUESDAY = 'Tuesday', 'Tuesday'
    WEDNESDAY = 'Wednesday', 'Wednesday'
    THURSDAY = 'Thursday', 'Thursday'
    FRIDAY = 'Friday', 'Friday'


class RoomType(models.TextChoices):
    LECTURE = 'lecture', 'Lecture Hall'
    LAB = 'lab', 'Laboratory'
    SEMINAR = 'seminar', 'Seminar Room'


class Lecturer(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    department = models.CharField(max_length=100, default='Computer Science')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Room(models.Model):
    name = models.CharField(max_length=50, unique=True)
    capacity = models.PositiveIntegerField()
    room_type = models.CharField(
        max_length=20, choices=RoomType.choices, default=RoomType.LECTURE
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.capacity})'


class StudentGroup(models.Model):
    name = models.CharField(max_length=50, unique=True)
    level = models.PositiveIntegerField(help_text='e.g. 100, 200, 300, 400')
    size = models.PositiveIntegerField(help_text='Number of students in the group')

    class Meta:
        ordering = ['level', 'name']

    def __str__(self):
        return f'{self.name} (L{self.level}, n={self.size})'


class Course(models.Model):
    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=200)
    unit_load = models.PositiveIntegerField(default=2)
    department = models.CharField(max_length=100, default='Computer Science')
    level = models.PositiveIntegerField()
    sessions_per_week = models.PositiveIntegerField(
        default=1, help_text='Number of lecture periods needed per week'
    )
    requires_lab = models.BooleanField(default=False)
    lecturer = models.ForeignKey(
        Lecturer, on_delete=models.PROTECT, related_name='courses'
    )
    student_groups = models.ManyToManyField(
        StudentGroup, related_name='courses', blank=True
    )

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code} — {self.title}'

    @property
    def class_size(self):
        groups = self.student_groups.all()
        if not groups:
            return 0
        return sum(g.size for g in groups)


class TimeSlot(models.Model):
    day = models.CharField(max_length=10, choices=DayOfWeek.choices)
    period = models.PositiveIntegerField(help_text='Period number within the day (1–8)')
    start_time = models.TimeField()
    end_time = models.TimeField()
    label = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = [
            models.Case(
                models.When(day='Monday', then=0),
                models.When(day='Tuesday', then=1),
                models.When(day='Wednesday', then=2),
                models.When(day='Thursday', then=3),
                models.When(day='Friday', then=4),
                default=5,
            ),
            'period',
        ]
        unique_together = [('day', 'period')]

    def __str__(self):
        if self.label:
            return self.label
        return f'{self.day} P{self.period} ({self.start_time.strftime("%H:%M")}-{self.end_time.strftime("%H:%M")})'

    def save(self, *args, **kwargs):
        if not self.label:
            self.label = (
                f'{self.day[:3]} '
                f'{self.start_time.strftime("%H:%M")}-{self.end_time.strftime("%H:%M")}'
            )
        super().save(*args, **kwargs)


class LecturerAvailability(models.Model):
    """Soft constraint: lecturer prefers (or avoids) certain slots."""

    lecturer = models.ForeignKey(
        Lecturer, on_delete=models.CASCADE, related_name='availabilities'
    )
    time_slot = models.ForeignKey(
        TimeSlot, on_delete=models.CASCADE, related_name='lecturer_prefs'
    )
    is_preferred = models.BooleanField(
        default=True,
        help_text='True = preferred slot; False = unavailable / strongly disliked',
    )

    class Meta:
        unique_together = [('lecturer', 'time_slot')]
        verbose_name_plural = 'lecturer availabilities'

    def __str__(self):
        pref = 'prefers' if self.is_preferred else 'unavailable'
        return f'{self.lecturer} {pref} {self.time_slot}'


class TimetableRun(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    name = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    population_size = models.PositiveIntegerField(default=80)
    max_generations = models.PositiveIntegerField(default=200)
    crossover_prob = models.FloatField(default=0.7)
    mutation_prob = models.FloatField(default=0.2)
    generations_run = models.PositiveIntegerField(default=0)
    best_fitness = models.FloatField(null=True, blank=True)
    hard_violations = models.PositiveIntegerField(default=0)
    soft_violations = models.PositiveIntegerField(default=0)
    execution_seconds = models.FloatField(null=True, blank=True)
    fitness_history = models.JSONField(default=list, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(
        default=False, help_text='Currently published timetable'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        label = self.name or f'Run #{self.pk}'
        return f'{label} ({self.status})'

    def save(self, *args, **kwargs):
        if self.is_active:
            TimetableRun.objects.filter(is_active=True).exclude(pk=self.pk).update(
                is_active=False
            )
        if not self.name and self.pk:
            self.name = f'Timetable Run #{self.pk}'
        super().save(*args, **kwargs)


class TimetableEntry(models.Model):
    run = models.ForeignKey(
        TimetableRun, on_delete=models.CASCADE, related_name='entries'
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    lecturer = models.ForeignKey(Lecturer, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    student_group = models.ForeignKey(
        StudentGroup, on_delete=models.CASCADE, null=True, blank=True
    )
    session_index = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['time_slot__day', 'time_slot__period', 'course__code']
        verbose_name_plural = 'timetable entries'

    def __str__(self):
        return f'{self.course.code} @ {self.time_slot} in {self.room.name}'
