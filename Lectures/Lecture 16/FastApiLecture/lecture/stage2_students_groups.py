# Этап 2: FastAPI — связанные ресурсы (студенты + группы, in-memory)
#
# Запуск:
#   uvicorn stage2_students_groups:app --reload
#
# Документация: http://127.0.0.1:8000/docs
import uvicorn
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Студенты + Группы (in-memory)")

# ── Данные ────────────────────────────────────────────────────────────────────

groups: list[dict] = [
    {"id": 1, "name": "ГГ-22-1"},
    {"id": 2, "name": "ГГ-22-2"},
]

students: list[dict] = [
    {"id": 1, "surname": "Иванов",  "name": "Иван",    "age": 20, "group_id": 1},
    {"id": 2, "surname": "Петрова", "name": "Мария",   "age": 22, "group_id": 1},
    {"id": 3, "surname": "Сидоров", "name": "Алексей", "age": 21, "group_id": 2},
]

_next_student_id = 4
_next_group_id   = 3


# ── Вспомогательные функции ───────────────────────────────────────────────────

def find_group(group_id: int) -> dict | None:
    return next((g for g in groups if g["id"] == group_id), None)

def find_student(student_id: int) -> dict | None:
    return next((s for s in students if s["id"] == student_id), None)


# ── Группы: CRUD ──────────────────────────────────────────────────────────────

@app.get("/groups")
def get_all_groups():
    """Все группы."""
    return groups


@app.get("/groups/{group_id}")
def get_group(group_id: int):
    """Группа по id."""
    group = find_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return group


@app.post("/groups", status_code=201)
def create_group(name: str):
    global _next_group_id
    group = {"id": _next_group_id, "name": name}
    groups.append(group)
    _next_group_id += 1
    return group


@app.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: int):
    group = find_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    # Запрещаем удалять группу, если в ней есть студенты
    if any(s["group_id"] == group_id for s in students):
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить группу: в ней есть студенты"
        )
    groups.remove(group)


# ── Студенты: CRUD ────────────────────────────────────────────────────────────

@app.get("/students")
def get_all_students(group_id: int | None = None):
    """Все студенты. Можно фильтровать по group_id: ?group_id=1"""
    if group_id is not None:
        return [s for s in students if s["group_id"] == group_id]
    return students


@app.get("/students/{student_id}")
def get_student(student_id: int):
    student = find_student(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Студент не найден")
    return student


@app.post("/students", status_code=201)
def create_student(surname: str, name: str, age: int, group_id: int):
    global _next_student_id
    if not find_group(group_id):
        raise HTTPException(status_code=404, detail="Группа не найдена")
    student = {
        "id": _next_student_id,
        "surname": surname,
        "name": name,
        "age": age,
        "group_id": group_id,
    }
    students.append(student)
    _next_student_id += 1
    return student


@app.put("/students/{student_id}")
def update_student(student_id: int, surname: str | None = None,
                   name: str | None = None, age: int | None = None,
                   group_id: int | None = None):
    student = find_student(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Студент не найден")
    if group_id is not None and not find_group(group_id):
        raise HTTPException(status_code=404, detail="Группа не найдена")
    if surname   is not None: student["surname"]  = surname
    if name      is not None: student["name"]     = name
    if age       is not None: student["age"]      = age
    if group_id  is not None: student["group_id"] = group_id
    return student


@app.delete("/students/{student_id}", status_code=204)
def delete_student(student_id: int):
    student = find_student(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Студент не найден")
    students.remove(student)


# ── Вложенный маршрут: студенты конкретной группы ────────────────────────────

@app.get("/groups/{group_id}/students")
def get_students_of_group(group_id: int):
    """Все студенты конкретной группы (вложенный URL)."""
    if not find_group(group_id):
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return [s for s in students if s["group_id"] == group_id]


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)