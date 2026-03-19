"""Composable API routers."""

from fastapi import APIRouter

from . import admin, auth, menu, orders, payments, token

api_router = APIRouter()
api_router.include_router(token.router, tags=["token"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(menu.router, prefix="/menu", tags=["menu"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

__all__ = ["api_router"]

