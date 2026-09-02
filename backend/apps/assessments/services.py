"""Gradebook computation - the only place results are derived."""
from decimal import Decimal

from apps.assessments.models import (
    AssessmentComponent,
    ComponentScore,
    CourseResult,
    ExternalMark,
    GradeBand,
    GradeScale,
)
from apps.core.calculations import (
    grade_point_average,
    percentage as pct,
    resolve_grade,
    round2,
    scaled_score,
)


def grade_bands_for(department=None):
    scale = GradeScale.resolve_for(department)
    if scale is None:
        return []
    return list(GradeBand.objects.filter(scale=scale).order_by("-min_percentage"))


def recompute_result(student, section, save=True):
    """Recalculate one student's result for a section from its component scores."""
    components = AssessmentComponent.objects.filter(section=section, is_active=True)
    scores = {
        score.component_id: score
        for score in ComponentScore.objects.filter(component__section=section, student=student)
    }

    internal_total = Decimal("0.00")
    internal_max = Decimal("0.00")
    breakdown = []
    for component in components:
        internal_max += Decimal(str(component.weight))
        score = scores.get(component.id)
        obtained = Decimal("0.00")
        if score and score.marks_obtained is not None and not score.is_absent:
            obtained = scaled_score(score.marks_obtained, component.max_marks, component.weight)
        internal_total += obtained
        breakdown.append(
            {
                "component_id": str(component.id),
                "name": component.name,
                "kind": component.kind,
                "max_marks": float(component.max_marks),
                "weight": float(component.weight),
                "raw": float(score.marks_obtained) if score and score.marks_obtained is not None else None,
                "scaled": float(obtained),
                "status": score.status if score else "DRAFT",
                "is_absent": bool(score.is_absent) if score else False,
            }
        )

    external = ExternalMark.objects.filter(student=student, section=section)
    external_total = sum((Decimal(str(mark.marks_obtained)) for mark in external), Decimal("0.00"))
    external_max = sum((Decimal(str(mark.max_marks)) for mark in external), Decimal("0.00"))

    total = round2(internal_total + external_total)
    maximum = round2(internal_max + external_max)
    percentage = pct(total, maximum)

    band = resolve_grade(percentage, grade_bands_for(section.course.department))
    letter = band.letter if band else ""
    grade_point = Decimal(str(band.grade_point)) if band else Decimal("0")
    is_pass = bool(band.is_pass) if band else False

    if not save:
        return {
            "internal_total": float(round2(internal_total)),
            "internal_max": float(round2(internal_max)),
            "external_total": float(round2(external_total)),
            "external_max": float(round2(external_max)),
            "total_marks": float(total),
            "percentage": float(percentage),
            "grade_letter": letter,
            "grade_point": float(grade_point),
            "is_pass": is_pass,
            "breakdown": breakdown,
        }

    result, _ = CourseResult.objects.update_or_create(
        student=student,
        section=section,
        defaults={
            "internal_total": round2(internal_total),
            "internal_max": round2(internal_max),
            "external_total": round2(external_total),
            "external_max": round2(external_max),
            "total_marks": total,
            "percentage": percentage,
            "grade_letter": letter,
            "grade_point": grade_point,
            "credits": section.course.credits,
            "is_pass": is_pass,
        },
    )
    return result


def recompute_section(section):
    """Recalculate every enrolled student's result in a section."""
    from apps.courses.models import Enrollment

    results = []
    enrollments = section.enrollments.filter(status=Enrollment.Status.ACTIVE).select_related(
        "student"
    )
    for enrollment in enrollments:
        results.append(recompute_result(enrollment.student, section))
    return results


def gradebook(section):
    """The full gradebook grid for a section."""
    from apps.courses.models import Enrollment

    components = list(
        AssessmentComponent.objects.filter(section=section, is_active=True).order_by(
            "display_order", "name"
        )
    )
    enrollments = (
        section.enrollments.filter(status=Enrollment.Status.ACTIVE)
        .select_related("student", "student__student_profile")
        .order_by("student__full_name")
    )
    score_map = {}
    for score in ComponentScore.objects.filter(component__section=section).select_related(
        "component"
    ):
        score_map[(score.student_id, score.component_id)] = score

    rows = []
    for enrollment in enrollments:
        student = enrollment.student
        cells = []
        for component in components:
            score = score_map.get((student.id, component.id))
            cells.append(
                {
                    "component_id": str(component.id),
                    "score_id": str(score.id) if score else None,
                    "marks_obtained": float(score.marks_obtained)
                    if score and score.marks_obtained is not None
                    else None,
                    "is_absent": bool(score.is_absent) if score else False,
                    "status": score.status if score else "DRAFT",
                    "is_locked": score.is_locked if score else False,
                }
            )
        computed = recompute_result(student, section, save=False)
        rows.append(
            {
                "student_id": str(student.id),
                "full_name": student.full_name,
                "enrollment_number": getattr(
                    getattr(student, "student_profile", None), "enrollment_number", ""
                ),
                "cells": cells,
                "internal_total": computed["internal_total"],
                "internal_max": computed["internal_max"],
                "external_total": computed["external_total"],
                "total_marks": computed["total_marks"],
                "percentage": computed["percentage"],
                "grade_letter": computed["grade_letter"],
                "grade_point": computed["grade_point"],
                "is_pass": computed["is_pass"],
            }
        )

    return {
        "section": {
            "id": str(section.id),
            "course_code": section.course.code,
            "course_name": section.course.name,
            "name": section.name,
            "credits": float(section.course.credits),
        },
        "components": [
            {
                "id": str(component.id),
                "name": component.name,
                "kind": component.kind,
                "max_marks": float(component.max_marks),
                "weight": float(component.weight),
                "is_auto_calculated": component.is_auto_calculated,
            }
            for component in components
        ],
        "students": rows,
        "internal_max": float(sum(Decimal(str(c.weight)) for c in components)) if components else 0.0,
    }


def student_transcript(student):
    """Semester-wise GPA plus the cumulative CGPA."""
    results = (
        CourseResult.objects.filter(student=student, is_published=True)
        .select_related("section__course", "section__semester", "section__semester__session")
        .order_by("section__semester__number")
    )
    semesters = {}
    for result in results:
        semester = result.section.semester
        key = str(semester.id)
        semesters.setdefault(
            key,
            {
                "semester_id": key,
                "semester_name": semester.name,
                "session": semester.session.name,
                "number": semester.number,
                "courses": [],
            },
        )
        semesters[key]["courses"].append(
            {
                "course_code": result.section.course.code,
                "course_name": result.section.course.name,
                "credits": float(result.credits),
                "total_marks": float(result.total_marks),
                "percentage": float(result.percentage),
                "grade_letter": result.grade_letter,
                "grade_point": float(result.grade_point),
                "is_pass": result.is_pass,
            }
        )

    output = []
    all_entries = []
    for data in sorted(semesters.values(), key=lambda item: item["number"]):
        entries = [(course["grade_point"], course["credits"]) for course in data["courses"]]
        all_entries.extend(entries)
        data["gpa"] = float(grade_point_average(entries))
        data["total_credits"] = float(sum(course["credits"] for course in data["courses"]))
        output.append(data)

    return {
        "semesters": output,
        "cgpa": float(grade_point_average(all_entries)),
        "total_credits": float(sum(credits for _, credits in all_entries)),
    }
