"""
Genetic Algorithm timetable generator.

Chromosome: list of (room_index, timeslot_index) genes — one per scheduled session.
Hard constraints are heavily penalised; soft constraints moderately.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any

from deap import base, creator, tools


# Penalty weights (hard >> soft so any hard-feasible solution beats infeasible ones)
HARD_WEIGHT = 1000
SOFT_WEIGHT = 10


@dataclass
class SessionSpec:
    """One lecture session that must appear on the timetable."""

    course_id: int
    lecturer_id: int
    group_id: int | None
    group_size: int
    session_index: int
    requires_lab: bool


@dataclass
class GAResult:
    best_chromosome: list[tuple[int, int]]
    best_fitness: float
    hard_violations: int
    soft_violations: int
    generations: int
    execution_seconds: float
    fitness_history: list[float] = field(default_factory=list)
    success: bool = False
    message: str = ''


class TimetableGA:
    """Evolves clash-free departmental timetables with DEAP."""

    def __init__(
        self,
        sessions: list[SessionSpec],
        rooms: list[dict[str, Any]],
        timeslots: list[dict[str, Any]],
        preferred_slots: dict[int, set[int]] | None = None,
        unavailable_slots: dict[int, set[int]] | None = None,
        population_size: int = 80,
        max_generations: int = 200,
        crossover_prob: float = 0.7,
        mutation_prob: float = 0.2,
        tournament_size: int = 3,
        seed: int | None = None,
    ):
        self.sessions = sessions
        self.rooms = rooms
        self.preferred_slots = preferred_slots or {}
        self.unavailable_slots = unavailable_slots or {}
        self.population_size = population_size
        self.max_generations = max_generations
        self.crossover_prob = crossover_prob
        self.mutation_prob = mutation_prob
        self.tournament_size = tournament_size

        if seed is not None:
            random.seed(seed)

        self.n_rooms = len(rooms)
        self.n_slots = len(timeslots)
        self.n_sessions = len(sessions)

        self.slot_day = [ts['day'] for ts in timeslots]
        self.slot_period = [ts['period'] for ts in timeslots]

        self._setup_deap()

    def _setup_deap(self):
        # Recreate fitness/individual types safely across repeated runs
        if hasattr(creator, 'FitnessMax'):
            del creator.FitnessMax
        if hasattr(creator, 'Individual'):
            del creator.Individual

        creator.create('FitnessMax', base.Fitness, weights=(1.0,))
        creator.create('Individual', list, fitness=creator.FitnessMax)

        self.toolbox = base.Toolbox()
        self.toolbox.register('individual', self._init_individual)
        self.toolbox.register('population', tools.initRepeat, list, self.toolbox.individual)
        self.toolbox.register('evaluate', self._evaluate)
        self.toolbox.register('mate', self._crossover)
        self.toolbox.register('mutate', self._mutate)
        self.toolbox.register('select', tools.selTournament, tournsize=self.tournament_size)

    def _random_gene(self, session_index: int) -> tuple[int, int]:
        session = self.sessions[session_index]
        rooms = self._eligible_rooms(session)
        return (random.choice(rooms), random.randrange(self.n_slots))

    def _init_individual(self):
        ind = creator.Individual()
        for i in range(self.n_sessions):
            ind.append(self._random_gene(i))
        return ind

    def _evaluate(self, individual: list[tuple[int, int]]) -> tuple[float]:
        hard, soft = self._count_violations(individual)
        # Higher is better: start from 0 and subtract penalties
        fitness = -(hard * HARD_WEIGHT + soft * SOFT_WEIGHT)
        return (fitness,)

    def _count_violations(self, individual: list[tuple[int, int]]) -> tuple[int, int]:
        hard = 0
        soft = 0

        lecturer_slots: dict[tuple[int, int], int] = {}
        room_slots: dict[tuple[int, int], int] = {}
        group_slots: dict[tuple[int, int], int] = {}
        day_loads: dict[str, int] = {}
        group_day_periods: dict[tuple[int, str], list[int]] = {}

        for i, (room_idx, slot_idx) in enumerate(individual):
            session = self.sessions[i]
            room = self.rooms[room_idx]
            day = self.slot_day[slot_idx]
            period = self.slot_period[slot_idx]

            # --- Hard: room capacity ---
            if room['capacity'] < session.group_size:
                hard += 1

            # --- Hard: lab requirement ---
            if session.requires_lab and room['room_type'] != 'lab':
                hard += 1

            # --- Hard: lecturer clash ---
            lk = (session.lecturer_id, slot_idx)
            if lk in lecturer_slots:
                hard += 1
            else:
                lecturer_slots[lk] = i

            # --- Hard: room clash ---
            rk = (room_idx, slot_idx)
            if rk in room_slots:
                hard += 1
            else:
                room_slots[rk] = i

            # --- Hard: student group clash ---
            if session.group_id is not None:
                gk = (session.group_id, slot_idx)
                if gk in group_slots:
                    hard += 1
                else:
                    group_slots[gk] = i
                group_day_periods.setdefault((session.group_id, day), []).append(period)

            # --- Soft: unavailable slots (strong soft penalty) ---
            unavailable = self.unavailable_slots.get(session.lecturer_id, set())
            if slot_idx in unavailable:
                soft += 3

            # --- Soft: preferred slots ---
            preferred = self.preferred_slots.get(session.lecturer_id, set())
            if preferred and slot_idx not in preferred:
                soft += 1

            day_loads[day] = day_loads.get(day, 0) + 1

        # --- Soft: even distribution across the week ---
        if day_loads:
            values = list(day_loads.values())
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            soft += int(variance)  # larger spread → higher soft cost

        # --- Soft: minimise gaps in a group's daily schedule ---
        for periods in group_day_periods.values():
            if len(periods) < 2:
                continue
            periods = sorted(periods)
            span = periods[-1] - periods[0] + 1
            gaps = span - len(periods)
            soft += gaps

        return hard, soft

    def _crossover(self, ind1, ind2):
        """Session-based two-point crossover."""
        if self.n_sessions < 2:
            return ind1, ind2
        tools.cxTwoPoint(ind1, ind2)
        return ind1, ind2

    def _mutate(self, individual, indpb: float = 0.15):
        """Randomly reassign room and/or timeslot for some sessions."""
        for i in range(len(individual)):
            if random.random() < indpb:
                room_idx, slot_idx = individual[i]
                if random.random() < 0.5:
                    room_idx = random.choice(self._eligible_rooms(self.sessions[i]))
                else:
                    slot_idx = random.randrange(self.n_slots)
                individual[i] = (room_idx, slot_idx)
        return (individual,)

    def _eligible_rooms(self, session: SessionSpec) -> list[int]:
        rooms = []
        for idx, room in enumerate(self.rooms):
            if room['capacity'] < session.group_size:
                continue
            if session.requires_lab and room['room_type'] != 'lab':
                continue
            rooms.append(idx)
        return rooms or list(range(self.n_rooms))

    def _greedy_repair(self, individual: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """
        Hybrid greedy refinement (inspired by Akinola 2024):
        reassign conflicting sessions across eligible rooms/slots.
        """
        chrom = [tuple(g) for g in individual]
        hard, _ = self._count_violations(chrom)
        if hard == 0:
            return chrom

        # Multiple passes help when fixing one session unlocks another
        for _ in range(3):
            improved = False
            for i in range(self.n_sessions):
                session = self.sessions[i]
                best_gene = chrom[i]
                best_hard, best_soft = self._count_violations(chrom)
                eligible = self._eligible_rooms(session)
                # Sample slot/room pairs if the space is large
                candidates = [
                    (r, s) for r in eligible for s in range(self.n_slots)
                ]
                if len(candidates) > 120:
                    candidates = random.sample(candidates, 120)
                for gene in candidates:
                    trial = list(chrom)
                    trial[i] = gene
                    h, soft = self._count_violations(trial)
                    if h < best_hard or (h == best_hard and soft < best_soft):
                        best_hard, best_soft = h, soft
                        best_gene = gene
                        improved = True
                        if h == 0 and soft == 0:
                            break
                chrom[i] = best_gene
                hard = best_hard
                if hard == 0:
                    return chrom
            if not improved:
                break
        return chrom

    def run(self) -> GAResult:
        if self.n_sessions == 0:
            return GAResult(
                best_chromosome=[],
                best_fitness=0,
                hard_violations=0,
                soft_violations=0,
                generations=0,
                execution_seconds=0,
                success=False,
                message='No sessions to schedule. Add courses with student groups first.',
            )
        if self.n_rooms == 0 or self.n_slots == 0:
            return GAResult(
                best_chromosome=[],
                best_fitness=0,
                hard_violations=0,
                soft_violations=0,
                generations=0,
                execution_seconds=0,
                success=False,
                message='Rooms and time slots are required before generation.',
            )

        start = time.perf_counter()
        population = self.toolbox.population(n=self.population_size)

        fitnesses = list(map(self.toolbox.evaluate, population))
        for ind, fit in zip(population, fitnesses):
            ind.fitness.values = fit

        best = tools.selBest(population, 1)[0]
        history = [best.fitness.values[0]]
        generations_run = 0

        for gen in range(1, self.max_generations + 1):
            generations_run = gen
            offspring = self.toolbox.select(population, len(population))
            offspring = list(map(self.toolbox.clone, offspring))

            for c1, c2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < self.crossover_prob:
                    self.toolbox.mate(c1, c2)
                    del c1.fitness.values
                    del c2.fitness.values

            for mutant in offspring:
                if random.random() < self.mutation_prob:
                    self.toolbox.mutate(mutant)
                    del mutant.fitness.values

            invalid = [ind for ind in offspring if not ind.fitness.valid]
            fits = map(self.toolbox.evaluate, invalid)
            for ind, fit in zip(invalid, fits):
                ind.fitness.values = fit

            population[:] = offspring
            best = tools.selBest(population, 1)[0]
            history.append(best.fitness.values[0])

            hard, _ = self._count_violations(best)
            if hard == 0:
                break

        # Hybrid greedy refinement if hard violations remain
        best_chrom = [tuple(g) for g in best]
        hard, soft = self._count_violations(best_chrom)
        if hard > 0:
            best_chrom = self._greedy_repair(best_chrom)
            hard, soft = self._count_violations(best_chrom)

        fitness = -(hard * HARD_WEIGHT + soft * SOFT_WEIGHT)
        elapsed = time.perf_counter() - start

        return GAResult(
            best_chromosome=best_chrom,
            best_fitness=fitness,
            hard_violations=hard,
            soft_violations=soft,
            generations=generations_run,
            execution_seconds=round(elapsed, 3),
            fitness_history=history,
            success=hard == 0,
            message=(
                'Clash-free timetable found.'
                if hard == 0
                else f'Terminated with {hard} hard and {soft} soft violations remaining.'
            ),
        )


def build_sessions_from_queryset(courses) -> list[SessionSpec]:
    """Expand each course into SessionSpec entries (one per session × group)."""
    sessions: list[SessionSpec] = []
    for course in courses.select_related('lecturer').prefetch_related('student_groups'):
        groups = list(course.student_groups.all())
        if not groups:
            # Schedule once with size 0 if no group linked (capacity check skipped via size 0)
            for s_idx in range(1, course.sessions_per_week + 1):
                sessions.append(
                    SessionSpec(
                        course_id=course.id,
                        lecturer_id=course.lecturer_id,
                        group_id=None,
                        group_size=0,
                        session_index=s_idx,
                        requires_lab=course.requires_lab,
                    )
                )
        else:
            for group in groups:
                for s_idx in range(1, course.sessions_per_week + 1):
                    sessions.append(
                        SessionSpec(
                            course_id=course.id,
                            lecturer_id=course.lecturer_id,
                            group_id=group.id,
                            group_size=group.size,
                            session_index=s_idx,
                            requires_lab=course.requires_lab,
                        )
                    )
    return sessions
