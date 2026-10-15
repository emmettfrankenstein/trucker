import contextlib

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LogoutSerializer, RegisterSerializer, UserSerializer


def _tokens_for(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


@extend_schema(request=RegisterSerializer, responses={201: UserSerializer})
@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    """Create an account and return a JWT pair so the client is signed in straight away."""
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response({"user": UserSerializer(user).data, **_tokens_for(user)}, status=status.HTTP_201_CREATED)


@extend_schema(responses=UserSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)


@extend_schema(request=LogoutSerializer, responses={205: None})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    """Blacklist the refresh token so it can't mint new access tokens."""
    serializer = LogoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    # An already expired or blacklisted token gives the same outcome, so ignore it.
    with contextlib.suppress(TokenError):
        RefreshToken(serializer.validated_data["refresh"]).blacklist()
    return Response(status=status.HTTP_205_RESET_CONTENT)
