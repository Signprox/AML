from fastapi import APIRouter

from app.api.v2.routers.user_router import router as user_router


router = APIRouter(prefix="/api/v2")
router.include_router(user_router)
