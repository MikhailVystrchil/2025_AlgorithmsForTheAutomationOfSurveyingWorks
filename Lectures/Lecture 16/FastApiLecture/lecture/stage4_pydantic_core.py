# Этап 4: FastAPI + SQLite + Pydantic v2 + Annotated Form
#
# Здесь POST/PUT принимают данные не как JSON body, а как form-data.
# Это удобно для показа аннотированных форм в FastAPI.
#
# Запуск:
#   pip install fastapi uvicorn sqlalchemy pydantic faker python-multipart
#   uvicorn stage4_pydantic_form:app --reload
#
# Документация: http://127.0.0.1:8000/docs

from typing import Annotated

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Form
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import (
    create_engine, MetaData, Table, Column,
    Integer, String, ForeignKey,
    select, insert, update, delete, func,
)
from sqlalchemy.engine import Connection

# ── БД ────────────────────────────────────────────────────────────────────────

DATABASE_URL = "sqlite:///./university_pydantic_form.sqlite"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
metadata = MetaData()

groups_table = Table(
    "groups", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False),
)

students_table = Table(
    "students", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("surname", String),
    Column("name", String),
    Column("age", Integer),
    Column("group_id", Integer, ForeignKey("groups.id")),
)

metadata.create_all(engine)


def get_conn():
    with engine.connect() as conn:
        yield conn


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

app = FastAPI(title="Студенты + Группы (SQLite + Pydantic + Annotated Form)")


# ── Группы ────────────────────────────────────────────────────────────────────

@app.get("/groups", response_model=list[GroupRead])
def list_groups(conn: Connection = Depends(get_conn)):
    rows = conn.execute(select(groups_table)).fetchall()
    return [row._asdict() for row in rows]


@app.get("/groups/{group_id}", response_model=GroupRead)
def get_group(group_id: int, conn: Connection = Depends(get_conn)):
    row = conn.execute(
        select(groups_table).where(groups_table.c.id == group_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return row._asdict()


@app.post("/groups", response_model=GroupRead, status_code=201)
def create_group(
    data: Annotated[GroupCreate, Depends(parse_group_create)],
    conn: Connection = Depends(get_conn),
):
    result = conn.execute(insert(groups_table).values(name=data.name))
    conn.commit()
    return {"id": result.inserted_primary_key[0], "name": data.name}


@app.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: int, conn: Connection = Depends(get_conn)):
    row = conn.execute(
        select(groups_table).where(groups_table.c.id == group_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    count = conn.execute(
        select(func.count()).select_from(students_table)
        .where(students_table.c.group_id == group_id)
    ).scalar()
    if count:
        raise HTTPException(status_code=400, detail="В группе есть студенты")

    conn.execute(delete(groups_table).where(groups_table.c.id == group_id))
    conn.commit()


# ── Студенты ──────────────────────────────────────────────────────────────────

@app.get("/students", response_model=list[StudentRead])
def list_students(group_id: int | None = None, conn: Connection = Depends(get_conn)):
    stmt = select(students_table)
    if group_id is not None:
        stmt = stmt.where(students_table.c.group_id == group_id)
    rows = conn.execute(stmt).fetchall()
    return [row._asdict() for row in rows]


@app.get("/students/{student_id}", response_model=StudentRead)
def get_student(student_id: int, conn: Connection = Depends(get_conn)):
    row = conn.execute(
        select(students_table).where(students_table.c.id == student_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Студент не найден")
    return row._asdict()


@app.post("/students", response_model=StudentRead, status_code=201)
def create_student(
    data: Annotated[StudentCreate, Depends(parse_student_create)],
    conn: Connection = Depends(get_conn),
):
    grp = conn.execute(
        select(groups_table).where(groups_table.c.id == data.group_id)
    ).fetchone()
    if not grp:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    result = conn.execute(insert(students_table).values(**data.model_dump()))
    conn.commit()
    new_id = result.inserted_primary_key[0]
    return {"id": new_id, **data.model_dump()}


@app.put("/students/{student_id}", response_model=StudentRead)
def update_student(
    student_id: int,
    data: Annotated[StudentUpdate, Depends(parse_student_update)],
    conn: Connection = Depends(get_conn),
):
    row = conn.execute(
        select(students_table).where(students_table.c.id == student_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Студент не найден")

    if data.group_id is not None:
        grp = conn.execute(
            select(groups_table).where(groups_table.c.id == data.group_id)
        ).fetchone()
        if not grp:
            raise HTTPException(status_code=404, detail="Группа не найдена")

    changes = data.model_dump(exclude_none=True)
    conn.execute(
        update(students_table)
        .where(students_table.c.id == student_id)
        .values(**changes)
    )
    conn.commit()

    updated = conn.execute(
        select(students_table).where(students_table.c.id == student_id)
    ).fetchone()
    return updated._asdict()


@app.delete("/students/{student_id}", status_code=204)
def delete_student(student_id: int, conn: Connection = Depends(get_conn)):
    row = conn.execute(
        select(students_table).where(students_table.c.id == student_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Студент не найден")

    conn.execute(delete(students_table).where(students_table.c.id == student_id))
    conn.commit()


@app.get("/groups/{group_id}/students", response_model=list[StudentRead])
def students_of_group(group_id: int, conn: Connection = Depends(get_conn)):
    grp = conn.execute(
        select(groups_table).where(groups_table.c.id == group_id)
    ).fetchone()
    if not grp:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    rows = conn.execute(
        select(students_table).where(students_table.c.group_id == group_id)
    ).fetchall()
    return [row._asdict() for row in rows]


@app.post("/seed", status_code=201, tags=["dev"])
def seed_data(conn: Connection = Depends(get_conn)):
    from faker import Faker
    import random

    faker = Faker("ru_RU")

    r1 = conn.execute(insert(groups_table).values(name="ГГ-22-1"))
    r2 = conn.execute(insert(groups_table).values(name="ГГ-22-2"))
    g1, g2 = r1.inserted_primary_key[0], r2.inserted_primary_key[0]

    rows = []
    for _ in range(20):
        parts = faker.name().split()
        while len(parts) < 2:
            parts.append("")
        rows.append({
            "surname": parts[0],
            "name": parts[1],
            "age": random.randint(18, 23),
            "group_id": random.choice([g1, g2]),
        })

    conn.execute(insert(students_table), rows)
    conn.commit()
    return {"message": "Данные загружены"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
