from django.contrib.auth import get_user_model
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView


class BorrowerListAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        User = get_user_model()
        users = User.objects.filter(is_active=True).order_by("username")
        return Response([{"id": user.id, "username": user.username, "name": user.get_full_name()} for user in users])
