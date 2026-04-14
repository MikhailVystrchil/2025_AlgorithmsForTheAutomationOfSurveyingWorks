# Этап 3: FastAPI + SQLite (SQLAlchemy ORM, синхронный режим)
#
# Запуск:
#   pip install fastapi uvicorn sqlalchemy faker
#   uvicorn stage3_sqlite_orm:app --reload
#
# Документация: http://127.0.0.1:8000/docs

import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# ── Настройка БД ──────────────────────────────────────────────────────────────

DATABASE_URL = "sqlite:///./university_orm.sqlite"
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


# ── Зависимость: получить сессию ─────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Приложение ────────────────────────────────────────────────────────────────

app = FastAPI(title="Студенты + Группы (SQLite, ORM)")


# ── Группы ────────────────────────────────────────────────────────────────────

@app.get("/groups")
def list_groups(db: Session = Depends(get_db)):
    groups = db.query(Group).all()
    return [{"id": g.id, "name": g.name} for g in groups]


@app.get("/groups/{group_id}")
def get_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return {"id": group.id, "name": group.name}


@app.post("/groups", status_code=201)
def create_group(name: str, db: Session = Depends(get_db)):
    group = Group(name=name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return {"id": group.id, "name": group.name}


@app.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    count = db.query(func.count(Student.id)).filter(Student.group_id == group_id).scalar()
    if count:
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить группу: в ней есть студенты"
        )

    db.delete(group)
    db.commit()


# ── Студенты ──────────────────────────────────────────────────────────────────

@app.get("/students")
def list_students(group_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Student)
    if group_id is not None:
        query = query.filter(Student.group_id == group_id)
    students = query.all()
    return [
        {
            "id": s.id,
            "surname": s.surname,
            "name": s.name,
            "age": s.age,
            "group_id": s.group_id,
        }
        for s in students
    ]


@app.get("/students/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Студент не найден")
    return {
        "id": student.id,
        "surname": student.surname,
        "name": student.name,
        "age": student.age,
        "group_id": student.group_id,
    }


@app.post("/students", status_code=201)
def create_student(surname: str, name: str, age: int, group_id: int,
                   db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    student = Student(surname=surname, name=name, age=age, group_id=group_id)
    db.add(student)
    db.commit()
    db.refresh(student)

    return {
        "id": student.id,
        "surname": student.surname,
        "name": student.name,
        "age": student.age,
        "group_id": student.group_id,
    }


@app.put("/students/{student_id}")
def update_student(student_id: int, surname: str | None = None,
                   name: str | None = None, age: int | None = None,
                   group_id: int | None = None,
                   db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Студент не найден")

    if group_id is not None:
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Группа не найдена")

    if surname is not None:
        student.surname = surname
    if name is not None:
        student.name = name
    if age is not None:
        student.age = age
    if group_id is not None:
        student.group_id = group_id

    db.commit()
    db.refresh(student)

    return {
        "id": student.id,
        "surname": student.surname,
        "name": student.name,
        "age": student.age,
        "group_id": student.group_id,
    }


@app.delete("/students/{student_id}", status_code=204)
def delete_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Студент не найден")

    db.delete(student)
    db.commit()


# ── Вложенный маршрут ────────────────────────────────────────────────────────

@app.get("/groups/{group_id}/students")
def students_of_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    students = db.query(Student).filter(Student.group_id == group_id).all()
    return [
        {
            "id": s.id,
            "surname": s.surname,
            "name": s.name,
            "age": s.age,
            "group_id": s.group_id,
        }
        for s in students
    ]


# ── Seed-данные (для демонстрации) ────────────────────────────────────────────

@app.post("/seed", status_code=201, tags=["dev"])
def seed_data(db: Session = Depends(get_db)):
    """Заполнить БД тестовыми данными (вызывать один раз)."""
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
