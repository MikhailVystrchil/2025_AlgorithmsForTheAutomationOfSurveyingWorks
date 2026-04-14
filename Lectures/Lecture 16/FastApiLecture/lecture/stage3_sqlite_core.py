# Этап 3: FastAPI + SQLite (SQLAlchemy Core, синхронный режим)
#
# Запуск:
#   pip install fastapi uvicorn sqlalchemy faker
#   uvicorn stage3_sqlite:app --reload
#
# Документация: http://127.0.0.1:8000/docs
import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import (
    create_engine, MetaData, Table, Column,
    Integer, String, ForeignKey,
    select, insert, update, delete, func
)
from sqlalchemy.engine import Connection

# ── Настройка БД ──────────────────────────────────────────────────────────────

DATABASE_URL = "sqlite:///./university.sqlite"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
metadata = MetaData()

groups_table = Table(
    "groups", metadata,
    Column("id",   Integer, primary_key=True, autoincrement=True),
    Column("name", String,  nullable=False),
)

students_table = Table(
    "students", metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("surname",    String),
    Column("name",       String),
    Column("age",        Integer),
    Column("group_id",   Integer, ForeignKey("groups.id")),
)

metadata.create_all(engine)

# ── Зависимость: получить соединение ─────────────────────────────────────────

def get_conn():
    with engine.connect() as conn:
        yield conn

# ── Приложение ────────────────────────────────────────────────────────────────

app = FastAPI(title="Студенты + Группы (SQLite, Core)")


# ── Группы ────────────────────────────────────────────────────────────────────

@app.get("/groups")
def list_groups(conn: Connection = Depends(get_conn)):
    rows = conn.execute(select(groups_table)).fetchall()
    return [row._asdict() for row in rows]


@app.get("/groups/{group_id}")
def get_group(group_id: int, conn: Connection = Depends(get_conn)):
    row = conn.execute(
        select(groups_table).where(groups_table.c.id == group_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return row._asdict()


@app.post("/groups", status_code=201)
def create_group(name: str, conn: Connection = Depends(get_conn)):
    result = conn.execute(insert(groups_table).values(name=name))
    conn.commit()
    return {"id": result.inserted_primary_key[0], "name": name}


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
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить группу: в ней есть студенты"
        )
    conn.execute(delete(groups_table).where(groups_table.c.id == group_id))
    conn.commit()


# ── Студенты ──────────────────────────────────────────────────────────────────

@app.get("/students")
def list_students(group_id: int | None = None, conn: Connection = Depends(get_conn)):
    stmt = select(students_table)
    if group_id is not None:
        stmt = stmt.where(students_table.c.group_id == group_id)
    rows = conn.execute(stmt).fetchall()
    return [row._asdict() for row in rows]


@app.get("/students/{student_id}")
def get_student(student_id: int, conn: Connection = Depends(get_conn)):
    row = conn.execute(
        select(students_table).where(students_table.c.id == student_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Студент не найден")
    return row._asdict()


@app.post("/students", status_code=201)
def create_student(surname: str, name: str, age: int, group_id: int,
                   conn: Connection = Depends(get_conn)):
    grp = conn.execute(
        select(groups_table).where(groups_table.c.id == group_id)
    ).fetchone()
    if not grp:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    result = conn.execute(
        insert(students_table).values(
            surname=surname, name=name, age=age, group_id=group_id
        )
    )
    conn.commit()
    return {
        "id": result.inserted_primary_key[0],
        "surname": surname, "name": name, "age": age, "group_id": group_id
    }


@app.put("/students/{student_id}")
def update_student(student_id: int, surname: str | None = None,
                   name: str | None = None, age: int | None = None,
                   group_id: int | None = None,
                   conn: Connection = Depends(get_conn)):
    row = conn.execute(
        select(students_table).where(students_table.c.id == student_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Студент не найден")
    if group_id is not None:
        grp = conn.execute(
            select(groups_table).where(groups_table.c.id == group_id)
        ).fetchone()
        if not grp:
            raise HTTPException(status_code=404, detail="Группа не найдена")
    changes = {k: v for k, v in
               {"surname": surname, "name": name, "age": age, "group_id": group_id}.items()
               if v is not None}
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


# ── Вложенный маршрут ────────────────────────────────────────────────────────

@app.get("/groups/{group_id}/students")
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


# ── Seed-данные (для демонстрации) ────────────────────────────────────────────

@app.post("/seed", status_code=201, tags=["dev"])
def seed_data(conn: Connection = Depends(get_conn)):
    """Заполнить БД тестовыми данными (вызывать один раз)."""
    from faker import Faker
    faker = Faker("ru_RU")

    r1 = conn.execute(insert(groups_table).values(name="ГГ-22-1"))
    r2 = conn.execute(insert(groups_table).values(name="ГГ-22-2"))
    g1, g2 = r1.inserted_primary_key[0], r2.inserted_primary_key[0]

    import random
    rows = []
    for _ in range(20):
        parts = faker.name().split()
        while len(parts) < 2:
            parts.append("")
        rows.append({
            "surname":  parts[0],
            "name":     parts[1],
            "age":      random.randint(18, 23),
            "group_id": random.choice([g1, g2]),
        })
    conn.execute(insert(students_table), rows)
    conn.commit()
    return {"message": "Данные загружены"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
