from fastapi import APIRouter, Response, status

from app.api.v1.endpoints import auth, images, users, feed

api_router = APIRouter()


@api_router.get("/health", status_code=status.HTTP_200_OK)
async def api_health_check() -> Response:
    return Response(status_code=status.HTTP_200_OK)


api_router.include_router(auth.router, prefix="/auth", tags=["login"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(images.router, prefix="/images", tags=["images"])
api_router.include_router(feed.router, prefix="/feed", tags=["feed"])
