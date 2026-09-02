from django.db.models import Count, F, Q
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import Perm
from apps.core.viewsets import AuditedModelViewSet
from apps.library.models import ResourceCategory, ResourceLink
from apps.library.serializers import ResourceCategorySerializer, ResourceLinkSerializer


class ResourceCategoryViewSet(AuditedModelViewSet):
    queryset = ResourceCategory.objects.all()
    serializer_class = ResourceCategorySerializer
    required_permission = Perm.LIBRARY_VIEW
    required_write_permission = Perm.LIBRARY_MANAGE
    pagination_class = None
    audit_object_type = "resource category"

    def get_queryset(self):
        return super().get_queryset().annotate(resource_count=Count("resources"))


class ResourceLinkViewSet(AuditedModelViewSet):
    queryset = ResourceLink.objects.select_related("category", "department").all()
    serializer_class = ResourceLinkSerializer
    required_permission = Perm.LIBRARY_VIEW
    required_write_permission = Perm.LIBRARY_MANAGE
    filterset_fields = ["category", "access_type", "department", "is_active"]
    search_fields = ["title", "description"]
    audit_object_type = "e-resource"
    # Following a link is a reader action.
    action_permissions = {"visit": Perm.LIBRARY_VIEW}

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.has_perm_code(Perm.LIBRARY_MANAGE):
            qs = qs.filter(is_active=True).filter(
                Q(department__isnull=True) | Q(department=user.department)
            )
        return qs

    @action(detail=True, methods=["post"], url_path="visit")
    def visit(self, request, pk=None):
        resource = self.get_object()
        ResourceLink.objects.filter(pk=resource.pk).update(click_count=F("click_count") + 1)
        return Response({"url": resource.url})
