from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import Perm, Roles
from apps.core.viewsets import AuditedModelViewSet
from apps.courses.models import Enrollment
from apps.feedback.models import (
    FeedbackAnswer,
    FeedbackForm,
    FeedbackParticipation,
    FeedbackQuestion,
    FeedbackResponse,
)
from apps.feedback.serializers import (
    FeedbackFormSerializer,
    FeedbackQuestionSerializer,
    FeedbackSubmissionSerializer,
)

#: Aggregated results are hidden below this many responses so individual
#: answers on an anonymous form cannot be inferred.
MIN_RESPONSES_FOR_RESULTS = 3


class FeedbackFormViewSet(AuditedModelViewSet):
    queryset = FeedbackForm.objects.select_related("section__course", "department").prefetch_related(
        "questions", "responses"
    )
    serializer_class = FeedbackFormSerializer
    required_permission = Perm.FEEDBACK_SUBMIT
    required_write_permission = Perm.FEEDBACK_MANAGE
    filterset_fields = ["form_type", "status", "section", "department"]
    search_fields = ["title", "description"]
    audit_object_type = "feedback form"
    # Respondents submit to forms only staff can author.
    action_permissions = {"submit": Perm.FEEDBACK_SUBMIT}

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.has_perm_code(Perm.FEEDBACK_MANAGE):
            return qs
        now = timezone.now()
        section_ids = Enrollment.objects.filter(
            student=user, status=Enrollment.Status.ACTIVE
        ).values_list("section_id", flat=True)
        role_ids = [
            row_id
            for row_id, roles in qs.values_list("id", "target_roles")
            if not roles or user.role in roles
        ]
        return (
            qs.filter(status=FeedbackForm.Status.OPEN, id__in=role_ids)
            .filter(Q(opens_at__isnull=True) | Q(opens_at__lte=now))
            .filter(Q(closes_at__isnull=True) | Q(closes_at__gte=now))
            .filter(
                Q(section__isnull=True, department__isnull=True)
                | Q(section_id__in=section_ids)
                | Q(department=user.department)
            )
            .distinct()
        )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Submit a response. Anonymous forms store no link to the respondent."""
        form = self.get_object()
        now = timezone.now()
        if form.status != FeedbackForm.Status.OPEN:
            return Response(
                {"error": {"code": "conflict", "message": "This form is not open."}},
                status=status.HTTP_409_CONFLICT,
            )
        if form.closes_at and form.closes_at < now:
            return Response(
                {"error": {"code": "conflict", "message": "This form has closed."}},
                status=status.HTTP_409_CONFLICT,
            )
        if FeedbackParticipation.objects.filter(form=form, user=request.user).exists():
            return Response(
                {"error": {"code": "conflict", "message": "You have already responded to this form."}},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = FeedbackSubmissionSerializer(
            data={"form": str(form.id), "answers": request.data.get("answers", [])}
        )
        serializer.is_valid(raise_exception=True)

        questions = {str(q.id): q for q in form.questions.all()}
        required = {str(q.id) for q in form.questions.filter(is_required=True)}
        answered = {str(row.get("question")) for row in serializer.validated_data["answers"]}
        missing = required - answered
        if missing:
            return Response(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "Answer every required question.",
                        "details": {"missing": sorted(missing)},
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            response = FeedbackResponse.objects.create(
                form=form, respondent=None if form.is_anonymous else request.user
            )
            for row in serializer.validated_data["answers"]:
                question = questions.get(str(row.get("question")))
                if question is None:
                    continue
                FeedbackAnswer.objects.create(
                    response=response,
                    question=question,
                    rating_value=row.get("rating_value"),
                    text_value=str(row.get("text_value", ""))[:5000],
                    choice_value=row.get("choice_value", []),
                )
            FeedbackParticipation.objects.create(form=form, user=request.user)

        return Response({"detail": "Thank you - your feedback has been recorded."}, status=201)

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        """Aggregated results only, with a minimum-response floor for privacy."""
        if not request.user.has_perm_code(Perm.FEEDBACK_MANAGE):
            return Response(
                {"error": {"code": "permission_denied", "message": "Feedback results are restricted."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        form = self.get_object()
        total = form.responses.count()
        if form.is_anonymous and total < MIN_RESPONSES_FOR_RESULTS:
            return Response(
                {
                    "form": FeedbackFormSerializer(form, context={"request": request}).data,
                    "response_count": total,
                    "results": [],
                    "notice": "Results stay hidden until at least %s responses are received, so "
                    "individual answers cannot be identified." % MIN_RESPONSES_FOR_RESULTS,
                }
            )

        results = []
        for question in form.questions.all():
            answers = FeedbackAnswer.objects.filter(question=question)
            entry = {
                "question_id": str(question.id),
                "text": question.text,
                "question_type": question.question_type,
                "response_count": answers.count(),
            }
            if question.question_type == FeedbackQuestion.QuestionType.RATING:
                stats = answers.aggregate(average=Avg("rating_value"))
                entry["average"] = round(float(stats["average"] or 0), 2)
                entry["distribution"] = list(
                    answers.values("rating_value").annotate(count=Count("id")).order_by("rating_value")
                )
            elif question.question_type in (
                FeedbackQuestion.QuestionType.CHOICE,
                FeedbackQuestion.QuestionType.MULTI_CHOICE,
                FeedbackQuestion.QuestionType.YES_NO,
            ):
                tally = {}
                for value in answers.values_list("choice_value", flat=True):
                    for choice in value or []:
                        tally[choice] = tally.get(choice, 0) + 1
                entry["distribution"] = [
                    {"choice": key, "count": count} for key, count in sorted(tally.items())
                ]
            else:
                entry["responses"] = [
                    text for text in answers.values_list("text_value", flat=True) if text
                ]
            results.append(entry)

        return Response(
            {
                "form": FeedbackFormSerializer(form, context={"request": request}).data,
                "response_count": total,
                "results": results,
            }
        )


class FeedbackQuestionViewSet(AuditedModelViewSet):
    queryset = FeedbackQuestion.objects.select_related("form").all()
    serializer_class = FeedbackQuestionSerializer
    required_permission = Perm.FEEDBACK_MANAGE
    required_write_permission = Perm.FEEDBACK_MANAGE
    filterset_fields = ["form"]
    pagination_class = None
    audit_object_type = "feedback question"
