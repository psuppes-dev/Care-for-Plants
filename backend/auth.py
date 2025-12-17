from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

# ---- TEST ACCOUNTS (MS4) ----
USERS = {
    "student": "student123",
    "tutor": "tutor123"
}

SESSION_COOKIE = "care_for_plants_session"


@router.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...)
):
    if USERS.get(username) != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    response = JSONResponse({"message": "login successful"})
    response.set_cookie(
        key=SESSION_COOKIE,
        value=username,
        httponly=True,
        samesite="lax"
    )
    return response


@router.post("/logout")
async def logout():
    response = JSONResponse({"message": "logged out"})
    response.delete_cookie(SESSION_COOKIE)
    return response


def require_login(request: Request):
    user = request.cookies.get(SESSION_COOKIE)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

@router.get("/me")
def me(request: Request):
    user = request.cookies.get(SESSION_COOKIE)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"username": user}