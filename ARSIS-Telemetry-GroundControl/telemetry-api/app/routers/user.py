from fastapi import APIRouter, Request, status, Depends
from sqlalchemy.orm import Session
from ..db.database import get_db

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/")
def get_all_users(request: Request):
    return request.app.user_cache.get_all()


@router.get("/{user}")
async def get_user(request: Request, user: str):

    to_return = request.app.user_cache.get(user)
    to_return = to_return if to_return is not None else status.HTTP_404_NOT_FOUND
    return to_return


@router.put("/{user}")
async def put_user(request: Request, user: str, db: Session = Depends(get_db)):
    user_id = request.app.user_cache.register(user, db)
    to_return = status.HTTP_201_CREATED
    if user_id is None:
        to_return = status.HTTP_409_CONFLICT
    return to_return