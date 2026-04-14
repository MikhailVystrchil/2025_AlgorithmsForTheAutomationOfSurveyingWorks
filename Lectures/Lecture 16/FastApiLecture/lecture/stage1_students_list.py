# Этап 1: FastAPI — базовые HTTP-методы (GET, POST, PUT, DELETE)
# Данные хранятся в памяти (список словарей)
#
# Запуск:
#   pip install fastapi uvicorn
#   uvicorn stage1_students_list:app --reload
#
# Документация: http://127.0.0.1:8000/docs
import uvicorn
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Студенты (in-memory)")

# "База данных" — простой список
students: list[dict] = [
    {"id": 1, "surname": "Иванов",   "name": "Иван",   "age": 20},
    {"id": 2, "surname": "Петрова",  "name": "Мария",  "age": 22},
    {"id": 3, "surname": "Сидоров",  "name": "Алексей","age": 21},
]

_next_id = 4  # счётчик для новых записей


# ── GET /students ─────────────────────────────────────────────────────────────
@app.get("/students")
def get_all_students():
    """Вернуть список всех студентов."""
    return students


# ── GET /students/{student_id} ────────────────────────────────────────────────
@app.get("/students/{student_id}")
def get_student(student_id: int):
    """Вернуть студента по id."""
    for s in students:
        if s["id"] == student_id:
            return s
    raise HTTPException(status_code=404, detail="Студент не найден")


# ── POST /students ────────────────────────────────────────────────────────────
@app.post("/students", status_code=201)
def create_student(surname: str, name: str, age: int):
    """Добавить нового студента.
    Параметры передаются как query-параметры: ?surname=...&name=...&age=...
    """
    global _next_id
    student = {"id": _next_id, "surname": surname, "name": name, "age": age}
    students.append(student)
    _next_id += 1
    return student


# ── PUT /students/{student_id} ────────────────────────────────────────────────
@app.put("/students/{student_id}")
def update_student(student_id: int, surname: str | None = None,
                   name: str | None = None, age: int | None = None):
    """Обновить данные студента (только переданные поля)."""
    for s in students:
        if s["id"] == student_id:
            if surname is not None:
                s["surname"] = surname
            if name is not None:
                s["name"] = name
            if age is not None:
                s["age"] = age
            return s
    raise HTTPException(status_code=404, detail="Студент не найден")


# ── DELETE /students/{student_id} ─────────────────────────────────────────────
@app.delete("/students/{student_id}", status_code=204)
def delete_student(student_id: int):
    """Удалить студента по id."""
    for i, s in enumerate(students):
        if s["id"] == student_id:
            students.pop(i)
            return
    raise HTTPException(status_code=404, detail="Студент не найден")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
