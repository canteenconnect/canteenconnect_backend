"""Menu listing and admin menu management routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select

from app.api.deps import DbSession, require_roles
from app.models import MenuItem, Outlet, User
from app.schemas.menu import MenuItemCreate, MenuItemRead, MenuItemUpdate
from app.schemas.outlet import OutletRead

router = APIRouter()
MENU_MANAGEMENT_ROLES = ("admin", "super_admin", "campus_admin", "vendor_manager")


@router.get("/outlets", response_model=list[OutletRead], summary="List active outlets")
def list_outlets(
    db: DbSession,
    active_only: bool = Query(default=True),
) -> list[OutletRead]:
    """List available outlets for browsing or admin management."""

    statement = select(Outlet).order_by(Outlet.name.asc())
    if active_only:
        statement = statement.where(Outlet.is_active.is_(True))
    return list(db.scalars(statement).all())


@router.get("", response_model=list[MenuItemRead], summary="List menu items")
def list_menu_items(
    db: DbSession,
    outlet_id: int | None = Query(default=None),
    available_only: bool = Query(default=True),
) -> list[MenuItemRead]:
    """Return menu items, optionally filtered by outlet or availability."""

    statement = select(MenuItem).order_by(MenuItem.name.asc())
    if outlet_id is not None:
        statement = statement.where(MenuItem.outlet_id == outlet_id)
    if available_only:
        statement = statement.where(MenuItem.is_available.is_(True))
    return list(db.scalars(statement).all())


@router.get("/{item_id}", response_model=MenuItemRead, summary="Get a single menu item")
def get_menu_item(db: DbSession, item_id: int) -> MenuItemRead:
    """Return one menu item."""

    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found.")
    return item


@router.post(
    "",
    response_model=MenuItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a menu item",
)
def create_menu_item(
    db: DbSession,
    payload: MenuItemCreate,
    _: Annotated[User, Depends(require_roles(*MENU_MANAGEMENT_ROLES))],
) -> MenuItemRead:
    """Create a new menu item for an outlet."""

    outlet = db.get(Outlet, payload.outlet_id)
    if outlet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outlet not found.")

    item = MenuItem(
        outlet_id=payload.outlet_id,
        name=payload.name.strip(),
        description=payload.description,
        price=payload.price,
        stock_quantity=payload.stock_quantity,
        is_available=payload.is_available,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{item_id}", response_model=MenuItemRead, summary="Update a menu item")
def update_menu_item(
    db: DbSession,
    item_id: int,
    payload: MenuItemUpdate,
    _: Annotated[User, Depends(require_roles(*MENU_MANAGEMENT_ROLES))],
) -> MenuItemRead:
    """Update a menu item in place."""

    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found.")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is not None:
        updates["name"] = updates["name"].strip()

    if "outlet_id" in updates and updates["outlet_id"] is not None:
        outlet = db.get(Outlet, updates["outlet_id"])
        if outlet is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outlet not found.")

    for field, value in updates.items():
        setattr(item, field, value)

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a menu item")
def delete_menu_item(
    db: DbSession,
    item_id: int,
    _: Annotated[User, Depends(require_roles(*MENU_MANAGEMENT_ROLES))],
) -> Response:
    """Delete a menu item."""

    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found.")

    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

