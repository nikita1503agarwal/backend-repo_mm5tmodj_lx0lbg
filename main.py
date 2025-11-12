import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from bson import ObjectId
from passlib.context import CryptContext

from database import db, create_document, get_documents
from schemas import User as UserSchema, Roadmap as RoadmapSchema, AssessmentAttempt as AssessmentSchema

app = FastAPI(title="Lernify Road API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Utility helpers

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def objid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


# Request/Response models

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangeDomainRequest(BaseModel):
    domain: str


class ChangePasswordRequest(BaseModel):
    user_id: str
    old_password: str
    new_password: str


class AssessmentSubmitRequest(BaseModel):
    user_id: str
    domain: str
    step_index: int
    answer_index: int


# Seed roadmaps if empty
@app.on_event("startup")
def seed_data():
    if db is None:
        return
    if "roadmap" not in db.list_collection_names() or db["roadmap"].count_documents({}) == 0:
        roadmaps = [
            {
                "domain": "frontend",
                "title": "Frontend Developer Roadmap",
                "description": "Learn the essentials of building web UIs",
                "steps": [
                    {
                        "index": 0,
                        "title": "HTML & CSS Basics",
                        "description": "Learn structure and styling",
                        "youtube_url": "https://www.youtube.com/watch?v=mU6anWqZJcc",
                        "assessment_question": "Which tag creates a hyperlink?",
                        "assessment_options": ["<div>", "<a>", "<p>", "<span>"],
                        "assessment_answer_index": 1,
                    },
                    {
                        "index": 1,
                        "title": "JavaScript Fundamentals",
                        "description": "Variables, functions, arrays, objects",
                        "youtube_url": "https://www.youtube.com/watch?v=W6NZfCO5SIk",
                        "assessment_question": "Which keyword declares a block-scoped variable?",
                        "assessment_options": ["var", "let", "function", "class"],
                        "assessment_answer_index": 1,
                    },
                ],
                "is_active": True,
            },
            {
                "domain": "backend",
                "title": "Backend Developer Roadmap",
                "description": "APIs, databases, authentication",
                "steps": [
                    {
                        "index": 0,
                        "title": "REST APIs",
                        "description": "HTTP, endpoints, JSON",
                        "youtube_url": "https://www.youtube.com/watch?v=-MTSQjw5DrM",
                        "assessment_question": "Which HTTP verb is idempotent?",
                        "assessment_options": ["POST", "PUT", "PATCH", "HEAD"],
                        "assessment_answer_index": 1,
                    },
                ],
                "is_active": True,
            },
            {
                "domain": "ai",
                "title": "AI Roadmap",
                "description": "AI concepts and tooling",
                "steps": [
                    {
                        "index": 0,
                        "title": "Python for AI",
                        "description": "Syntax and libraries",
                        "youtube_url": "https://www.youtube.com/watch?v=kqtD5dpn9C8",
                        "assessment_question": "What library is primarily used for tensors?",
                        "assessment_options": ["NumPy", "Pandas", "TensorFlow", "Matplotlib"],
                        "assessment_answer_index": 2,
                    }
                ],
                "is_active": True,
            },
            {
                "domain": "ml",
                "title": "Machine Learning Roadmap",
                "description": "ML basics, models, evaluation",
                "steps": [
                    {
                        "index": 0,
                        "title": "Linear Regression",
                        "description": "Supervised learning basics",
                        "youtube_url": "https://www.youtube.com/watch?v=nk2CQITm_eo",
                        "assessment_question": "Which metric is common for regression?",
                        "assessment_options": ["Accuracy", "MSE", "Recall", "AUC"],
                        "assessment_answer_index": 1,
                    }
                ],
                "is_active": True,
            },
        ]
        db["roadmap"].insert_many(roadmaps)


@app.get("/")
def root():
    return {"message": "Lernify Road API running"}


@app.post("/auth/register")
def register(payload: RegisterRequest):
    if db["user"].find_one({"email": payload.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = hash_password(payload.password)
    user = {
        "name": payload.name,
        "email": str(payload.email),
        "password_hash": hashed,
        "domain": None,
        "progress": {},
        "role": "student",
        "is_active": True,
    }
    user_id = db["user"].insert_one(user).inserted_id
    return {"user_id": str(user_id), "name": user["name"], "email": user["email"]}


@app.post("/auth/login")
def login(payload: LoginRequest):
    user = db["user"].find_one({"email": str(payload.email)})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "user_id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "domain": user.get("domain"),
    }


@app.get("/roadmaps")
def list_roadmaps():
    items = list(db["roadmap"].find({"is_active": True}, {"steps.assessment_answer_index": 0}))
    for it in items:
        it["_id"] = str(it["_id"])
    return items


@app.get("/roadmaps/{domain}")
def get_roadmap(domain: str):
    rm = db["roadmap"].find_one({"domain": domain, "is_active": True}, {"steps.assessment_answer_index": 0})
    if not rm:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    rm["_id"] = str(rm["_id"])
    return rm


@app.post("/user/domain")
def choose_domain(req: ChangeDomainRequest, user_id: str):
    user = db["user"].find_one({"_id": objid(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db["user"].update_one({"_id": user["_id"]}, {"$set": {"domain": req.domain}})
    return {"message": "Domain updated", "domain": req.domain}


@app.get("/user/{user_id}/dashboard")
def user_dashboard(user_id: str):
    user = db["user"].find_one({"_id": objid(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    domain = user.get("domain")
    progress = user.get("progress", {})
    data: Dict[str, Any] = {"profile": {"name": user["name"], "email": user["email"], "domain": domain}}
    if domain:
        rm = db["roadmap"].find_one({"domain": domain})
        total_steps = len(rm.get("steps", [])) if rm else 0
        completed = progress.get(domain, {}).get("completed", [])
        scores = progress.get(domain, {}).get("scores", {})
        data["roadmap"] = {
            "title": rm.get("title") if rm else domain,
            "total_steps": total_steps,
            "completed_count": len(completed),
            "progress_percent": int((len(completed) / total_steps) * 100) if total_steps else 0,
            "scores": scores,
        }
    return data


@app.post("/auth/change-password")
def change_password(req: ChangePasswordRequest):
    user = db["user"].find_one({"_id": objid(req.user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(req.old_password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Old password incorrect")
    db["user"].update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(req.new_password)}})
    return {"message": "Password updated"}


@app.post("/assessment/submit")
def submit_assessment(req: AssessmentSubmitRequest):
    rm = db["roadmap"].find_one({"domain": req.domain})
    if not rm:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    steps = rm.get("steps", [])
    step = next((s for s in steps if s.get("index") == req.step_index), None)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    correct_index = step.get("assessment_answer_index")
    if correct_index is None:
        raise HTTPException(status_code=400, detail="Assessment not available for this step")

    score = 100 if req.answer_index == correct_index else 0
    attempt = {
        "user_id": req.user_id,
        "domain": req.domain,
        "step_index": req.step_index,
        "score": score,
        "total": 100,
    }
    db["assessmentattempt"].insert_one(attempt)

    # update user progress: enforce prerequisite (must complete previous step)
    user = db["user"].find_one({"_id": objid(req.user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    prog = user.get("progress", {})
    dom_prog = prog.get(req.domain, {"completed": [], "scores": {}})

    # Allow completing current step only if previous step is completed or it's the first step
    if req.step_index > 0 and (req.step_index - 1) not in dom_prog.get("completed", []):
        raise HTTPException(status_code=400, detail="You must complete previous step first")

    if score >= 50:  # pass threshold
        if req.step_index not in dom_prog["completed"]:
            dom_prog["completed"].append(req.step_index)
        dom_prog["scores"][str(req.step_index)] = score
        prog[req.domain] = dom_prog
        db["user"].update_one({"_id": user["_id"]}, {"$set": {"progress": prog}})

    return {"score": score, "passed": score >= 50}


@app.get("/user/{user_id}/progress/{domain}")
def get_progress(user_id: str, domain: str):
    user = db["user"].find_one({"_id": objid(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    prog = user.get("progress", {}).get(domain, {"completed": [], "scores": {}})
    return prog


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
