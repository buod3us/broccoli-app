from aiogram import Router

from handlers.admin import router as admin_router
from handlers.ai import router as ai_router
from handlers.menu import router as menu_router
from handlers.onboarding import router as onboarding_router
from handlers.orders import router as orders_router


def setup_routers() -> list[Router]:
    return [
        onboarding_router,
        orders_router,
        menu_router,
        ai_router,
        admin_router,
    ]
