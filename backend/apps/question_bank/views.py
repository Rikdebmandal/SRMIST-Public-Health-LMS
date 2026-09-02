import random

from django.db.models import Count, Q
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import Perm, Roles
from apps.core.viewsets import AuditedModelViewSet
from apps.courses.models import Enrollment
from apps.question_bank.models import Question, QuestionTopic
from apps.question_bank.serializers import QuestionSerializer, QuestionTopicSerializer


class QuestionTopicViewSet(AuditedModelViewSet):
    queryset = QuestionTopic.objects.select_related("course", "parent").all()
    serializer_class = QuestionTopicSerializer
    required_permission = Perm.QUESTION_VIEW
    required_write_permission = Perm.QUESTION_MANAGE
    filterset_fields = ["course", "parent"]
    search_fields = ["name"]
    audit_object_type = "question topic"

    def get_queryset(self):
        return super().get_queryset().annotate(question_count=Count("questions"))


class QuestionViewSet(AuditedModelViewSet):
    queryset = Question.objects.select_related("course", "topic", "created_by").prefetch_related(
        "options"
    )
    serializer_class = QuestionSerializer
    required_permission = Perm.QUESTION_VIEW
    required_write_permission = Perm.QUESTION_MANAGE
    filterset_fields = ["course", "topic", "question_type", "difficulty", "status"]
    search_fields = ["text", "explanation"]
    ordering_fields = ["created_at", "difficulty", "marks"]
    audit_object_type = "question"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == Roles.STUDENT:
            # Students may study approved questions for their own courses only,
            # and never see the answer key through the list endpoint.
            course_ids = Enrollment.objects.filter(
                student=user, status=Enrollment.Status.ACTIVE
            ).values_list("section__course_id", flat=True)
            qs = qs.filter(course_id__in=course_ids, status=Question.Status.APPROVED)
        elif user.role in (Roles.FACULTY, Roles.SCHOLAR):
            qs = qs.filter(
                Q(created_by=user) | Q(course__department=user.department)
            ).distinct()
        elif user.role == Roles.ADMIN and user.department_id:
            qs = qs.filter(course__department=user.department)
        return qs

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        # Hide answer keys from students.
        if self.request.user.role == Roles.STUDENT and hasattr(serializer, "fields"):
            serializer.fields.pop("correct_answer", None)
        return serializer

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        qs = self.get_queryset()
        return Response(
            {
                "total": qs.count(),
                "by_type": list(qs.values("question_type").annotate(count=Count("id"))),
                "by_difficulty": list(qs.values("difficulty").annotate(count=Count("id"))),
                "by_status": list(qs.values("status").annotate(count=Count("id"))),
            }
        )

    @action(detail=False, methods=["post"], url_path="generate-paper")
    def generate_paper(self, request):
        """Assemble a question paper by sampling the approved bank."""
        course_id = request.data.get("course")
        blueprint = request.data.get("blueprint", [])
        if not course_id or not blueprint:
            return Response(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "Provide a course and a blueprint of {difficulty, question_type, count} entries.",
                    }
                },
                status=400,
            )
        paper, shortfalls = [], []
        for entry in blueprint:
            pool = list(
                self.get_queryset().filter(
                    course_id=course_id,
                    status=Question.Status.APPROVED,
                    difficulty=entry.get("difficulty", Question.Difficulty.MEDIUM),
                    question_type=entry.get("question_type", Question.QuestionType.MCQ),
                )
            )
            wanted = int(entry.get("count", 1))
            if len(pool) < wanted:
                shortfalls.append(
                    {
                        "difficulty": entry.get("difficulty"),
                        "question_type": entry.get("question_type"),
                        "requested": wanted,
                        "available": len(pool),
                    }
                )
            picked = random.sample(pool, min(wanted, len(pool)))
            paper.extend(picked)

        from django.db.models import F

        Question.objects.filter(id__in=[question.id for question in paper]).update(
            times_used=F("times_used") + 1
        )

        return Response(
            {
                "questions": QuestionSerializer(paper, many=True).data,
                "total_marks": float(sum(q.marks for q in paper)),
                "count": len(paper),
                "shortfalls": shortfalls,
            }
        )
