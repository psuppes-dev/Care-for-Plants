from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from passlib.context import CryptContext

from database import SessionLocal  
from models import User            

router = APIRouter()
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_COOKIE = "care_for_plants_session"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
    db=Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_ctx.verify(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    resp = JSONResponse({"message": "login successful"})
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=str(user.id),   # << user_id in cookie
        httponly=True,
        samesite="lax"
    )
    return resp


@router.post("/logout")
def logout():
    resp = JSONResponse({"message": "logged out"})
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@router.get("/me")
def me(request: Request, db=Depends(get_db)):
    uid = request.cookies.get(SESSION_COOKIE)
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter(User.id == int(uid)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"id": user.id, "username": user.username}


def require_login(request: Request):
    uid = request.cookies.get(SESSION_COOKIE)
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return int(uid)