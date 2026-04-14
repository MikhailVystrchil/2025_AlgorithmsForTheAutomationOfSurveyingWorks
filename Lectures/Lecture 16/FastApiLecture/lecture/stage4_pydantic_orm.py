# Этап 4: FastAPI + SQLite + SQLAlchemy ORM + Pydantic v2 + Annotated Form
#
# Здесь POST/PUT принимают данные как form-data через Annotated + Form.
# Работа с БД ведётся через SQLAlchemy ORM.
#
# Запуск:
#   pip install fastapi uvicorn sqlalchemy pydantic faker python-multipart
#   uvicorn stage4_pydantic_orm_form:app --reload
#
# Документация: http://127.0.0.1:8000/docs

from typing import Annotated

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Form
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# ── БД ────────────────────────────────────────────────────────────────────────

DATABASE_URL = "sqlite:///./university_pydantic_orm_form.sqlite"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    surname = Column(String)
    name = Column(String)
    age = Column(Integer)
    group_id = Column(Integer, ForeignKey("groups.id"))


Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Pydantic-схемы ────────────────────────────────────────────────────────────

class GroupCreate(BaseModel):
    name: str


class GroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class StudentCreate(BaseModel):
    surname: str
    name: str
    age: int
    group_id: int

    @field_validator("age")
    @classmethod
    def age_must_be_valid(cls, v: int) -> int:
        if v < 16 or v > 60:
            raise ValueError("Возраст должен быть от 16 до 60 лет")
        return v


class StudentUpdate(BaseModel):
    surname: str | None = None
    name: str | None = None
    age: int | None = None
    group_id: int | None = None

    @field_validator("age")
    @classmethod
    def age_must_be_valid(cls, v: int | None) -> int | None:
        if v is not None and (v < 16 or v > 60):
            raise ValueError("Возраст должен быть от 16 до 60 лет")
        return v


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    surname: str
    name: str
    age: int
    group_id: int | None


# ── Функции-парсеры form-data через Annotated ────────────────────────────────


def parse_group_create(
    name: Annotated[str, Form(..., description="Название группы")],
) -> GroupCreate:
    return GroupCreate(name=name)



def parse_student_create(
    surname: Annotated[str, Form(..., description="Фамилия")],
    name: Annotated[str, Form(..., description="Имя")],
    age: Annotated[int, Form(..., description="Возраст")],
    group_id: Annotated[int, Form(..., description="ID группы")],
) -> StudentCreate:
    return StudentCreate(
        surname=surname,
        name=name,
        age=age,
        group_id=group_id,
    )



def parse_student_update(
    surname: Annotated[str | None, Form(description="Фамилия")] = None,
    name: Annotated[str | None, Form(description="Имя")] = None,
    age: Annotated[int | None, Form(description="Возраст")] = None,
    group_id: Annotated[int | None, Form(description="ID группы")] = None,
) -> StudentUpdate:
    return StudentUpdate(
        surname=surname,
        name=name,
        age=age,
        group_id=group_id,
    )


# ── Приложение ────────────────────────────────────────────────────────────────

app = FastAPI(title="Студенты + Группы (SQLite + ORM + Pydantic + Annotated Form)")


# ── Группы ────────────────────────────────────────────────────────────────────

@app.get("/groups", response_model=list[GroupRead])
def list_groups(db: Session = Depends(get_db)):
    groups = db.query(Group).all()
    return groups


@app.get("/groups/{group_id}", response_model=GroupRead)
def get_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return group


@app.post("/groups", response_model=GroupRead, status_code=201)
def create_group(
    data: Annotated[GroupCreate, Depends(parse_group_create)],
    db: Session = Depends(get_db),
):
    group = Group(name=data.name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@app.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    count = db.query(func.count(Student.id)).filter(Student.group_id == group_id).scalar()
    if count:
        raise HTTPException(status_code=400, detail="В группе есть студенты")

    db.delete(group)
    db.commit()


# ── Студенты ──────────────────────────────────────────────────────────────────

@app.get("/students", response_model=list[StudentRead])
def list_students(group_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Student)
    if group_id is not None:
        query = query.filter(Student.group_id == group_id)
    return query.all()


@app.get("/students/{student_id}", response_model=StudentRead)
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Студент не найден")
    return student


@app.post("/students", response_model=StudentRead, status_code=201)
def create_student(
    data: Annotated[StudentCreate, Depends(parse_student_create)],
    db: Session = Depends(get_db),
):
    group = db.query(Group).filter(Group.id == data.group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    student = Student(**data.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@app.put("/students/{student_id}", response_model=StudentRead)
def update_student(
    student_id: int,
    data: Annotated[StudentUpdate, Depends(parse_student_update)],
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Студент не найден")

    if data.group_id is not None:
        group = db.query(Group).filter(Group.id == data.group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Группа не найдена")

    changes = data.model_dump(exclude_none=True)
    for key, value in changes.items():
        setattr(student, key, value)

    db.commit()
    db.refresh(student)
    return student


@app.delete("/students/{student_id}", status_code=204)
def delete_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Студент не найден")

    db.delete(student)
    db.commit()


@app.get("/groups/{group_id}/students", response_model=list[StudentRead])
def students_of_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    return db.query(Student).filter(Student.group_id == group_id).all()


@app.post("/seed", status_code=201, tags=["dev"])
def seed_data(db: Session = Depends(get_db)):
    from faker import Faker
    import random

    faker = Faker("ru_RU")

    group1 = Group(name="ГГ-22-1")
    group2 = Group(name="ГГ-22-2")
    db.add(group1)
    db.add(group2)
    db.commit()
    db.refresh(group1)
    db.refresh(group2)

    for _ in range(20):
        parts = faker.name().split()
        while len(parts) < 2:
            parts.append("")

        student = Student(
            surname=parts[0],
            name=parts[1],
            age=random.randint(18, 23),
            group_id=random.choice([group1.id, group2.id]),
        )
        db.add(student)

    db.commit()
    return {"message": "Данные загружены"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
