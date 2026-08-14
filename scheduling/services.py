"""Service layer: run the genetic algorithm and persist results."""

from __future__ import annotations

from django.db import transaction

from .genetic_algorithm import TimetableGA, build_sessions_from_queryset
from .models import (
    Course,
    LecturerAvailability,
    Room,
    TimeSlot,
    TimetableEntry,
    TimetableRun,
)


def generate_timetable(
    *,
    name: str = '',
    population_size: int = 80,
    max_generations: int = 200,
    crossover_prob: float = 0.7,
    mutation_prob: float = 0.2,
    publish: bool = True,
) -> TimetableRun:
    run = TimetableRun.objects.create(
        name=name or '',
        status=TimetableRun.Status.RUNNING,
        population_size=population_size,
        max_generations=max_generations,
        crossover_prob=crossover_prob,
        mutation_prob=mutation_prob,
    )
    if not run.name:
        run.name = f'Timetable Run #{run.pk}'
        run.save(update_fields=['name'])

    try:
        courses = Course.objects.all()
        rooms_qs = list(Room.objects.all())
        slots_qs = list(TimeSlot.objects.all())

        sessions = build_sessions_from_queryset(courses)
        rooms = [
            {'id': r.id, 'name': r.name, 'capacity': r.capacity, 'room_type': r.room_type}
            for r in rooms_qs
        ]
        timeslots = [
            {'id': s.id, 'day': s.day, 'period': s.period, 'label': s.label}
            for s in slots_qs
        ]

        # Map DB ids → indices used by the GA
        slot_id_to_idx = {s['id']: i for i, s in enumerate(timeslots)}

        preferred: dict[int, set[int]] = {}
        unavailable: dict[int, set[int]] = {}
        for pref in LecturerAvailability.objects.select_related('time_slot'):
            idx = slot_id_to_idx.get(pref.time_slot_id)
            if idx is None:
                continue
            if pref.is_preferred:
                preferred.setdefault(pref.lecturer_id, set()).add(idx)
            else:
                unavailable.setdefault(pref.lecturer_id, set()).add(idx)

        ga = TimetableGA(
            sessions=sessions,
            rooms=rooms,
            timeslots=timeslots,
            preferred_slots=preferred,
            unavailable_slots=unavailable,
            population_size=population_size,
            max_generations=max_generations,
            crossover_prob=crossover_prob,
            mutation_prob=mutation_prob,
        )
        result = ga.run()

        with transaction.atomic():
            entries = []
            for i, (room_idx, slot_idx) in enumerate(result.best_chromosome):
                session = sessions[i]
                entries.append(
                    TimetableEntry(
                        run=run,
                        course_id=session.course_id,
                        lecturer_id=session.lecturer_id,
                        room_id=rooms[room_idx]['id'],
                        time_slot_id=timeslots[slot_idx]['id'],
                        student_group_id=session.group_id,
                        session_index=session.session_index,
                    )
                )
            TimetableEntry.objects.bulk_create(entries)

            run.status = TimetableRun.Status.COMPLETED
            run.generations_run = result.generations
            run.best_fitness = result.best_fitness
            run.hard_violations = result.hard_violations
            run.soft_violations = result.soft_violations
            run.execution_seconds = result.execution_seconds
            run.fitness_history = result.fitness_history
            run.message = result.message
            run.is_active = publish and result.success
            run.save()

        return run

    except Exception as exc:  # noqa: BLE001 — surface failure on the run record
        run.status = TimetableRun.Status.FAILED
        run.message = str(exc)
        run.save(
            update_fields=['status', 'message', 'updated_at']
        )
        raise
