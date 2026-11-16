"""Веб-приложение «Горнолыжный курорт с прокатом»: просмотр, добавление,
изменение и удаление строк по всем таблицам базы ski_resort."""
import os
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Flask, abort, flash, redirect, render_template, request, url_for

import db
from schema import REPORTS, TABLES

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

INT_MAX = 2147483647
MONEY_MAX = Decimal("99999999.99")

# Сообщения по именам ограничений из ski_resort.sql.
CONSTRAINT_MESSAGES = {
    "booking_dates": "Дата выезда должна быть позже даты заезда.",
    "rental_dates": "Дата окончания проката не может быть раньше начала.",
    "known_role": "Роль может быть только «плательщик» или «гость».",
    "known_meal": "Недопустимое значение питания.",
    "no_room_overlap": "Этот номер уже забронирован на пересекающиеся даты.",
    "guests_phone_key": "Гость с таким телефоном уже есть.",
    "guests_email_key": "Гость с такой почтой уже есть.",
    "rooms_number_key": "Номер с таким числом уже есть.",
    "room_categories_title_key": "Категория с таким названием уже есть.",
    "packages_title_key": "Пакет с таким названием уже есть.",
    "spa_services_name_key": "Процедура с таким названием уже есть.",
    "equipment_name_key": "Оборудование с таким названием уже есть.",
    "ski_passes_days_key": "Ски-пасс на такой срок уже есть.",
}


def explain_error(exc, action):
    """Переводит ошибку PostgreSQL в понятное сообщение. Чужие ошибки не глотает."""
    code = getattr(exc, "pgcode", None)
    if code is None:
        raise exc
    diag = getattr(exc, "diag", None)
    name = getattr(diag, "constraint_name", None) if diag else None
    text = getattr(diag, "message_primary", None) if diag else None
    if name in CONSTRAINT_MESSAGES:
        return CONSTRAINT_MESSAGES[name]
    if code == "23503":  # нарушен внешний ключ
        if action == "delete":
            return "Нельзя удалить: на эту строку есть ссылки из других таблиц."
        return "Выбранная связанная строка не найдена."
    if code == "23505":  # повтор значения
        return "Такая строка уже есть."
    if code == "23502":
        return "Не заполнено обязательное поле."
    if code == "23514" and text:  # триггер вместимости
        return text
    if code == "23P01":
        return "Строка конфликтует с уже существующей."
    return f"Ошибка базы данных: {text or code}"


def get_table(name):
    if name not in TABLES:
        abort(404)
    return TABLES[name]


def pk_from_request(table):
    pk = {}
    for col in table["pk"]:
        value = request.values.get(col)
        if value is None:
            abort(400)
        pk[col] = value
    return pk


def where_clause(table):
    return " AND ".join(f"{c} = %s" for c in table["pk"])


# ---------- фильтры шаблонов ----------

@app.template_filter("fdate")
def fdate(value):
    if value is None:
        return ""
    try:
        d = value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
        return d.strftime("%d.%m.%Y")
    except ValueError:
        return str(value)


@app.template_filter("money")
def money(value):
    if value is None:
        return ""
    return f"{Decimal(value):,.2f}".replace(",", "\u00a0").replace(".", ",")


# ---------- проверка формы ----------

def parse_form(table, form):
    """Возвращает (значения по столбцам БД, список ошибок)."""
    values, errors = {}, []
    for f in table["fields"]:
        label = f["label"]
        raw = (form.get(f["name"]) or "").strip()
        if not raw:
            errors.append(f"Поле «{label}» обязательно.")
            continue
        kind = f["kind"]
        try:
            if kind == "text":
                if len(raw) > f["max"]:
                    errors.append(f"Поле «{label}»: не больше {f['max']} символов.")
                    continue
                values[f["name"]] = raw
            elif kind in ("int", "fk"):
                v = int(raw)
                if v > INT_MAX or v < f.get("min", 0 if kind == "fk" else -INT_MAX):
                    errors.append(f"Поле «{label}»: число вне допустимых границ.")
                    continue
                values[f["name"]] = v
            elif kind == "number":
                v = Decimal(raw.replace(",", "."))
                if not v.is_finite() or v < Decimal(str(f["min"])) or v > MONEY_MAX:
                    errors.append(f"Поле «{label}»: сумма от {f['min']} до {MONEY_MAX}.")
                    continue
                values[f["name"]] = v
            elif kind == "date":
                values[f["name"]] = date.fromisoformat(raw)
            elif kind == "choice":
                if raw not in f["choices"]:
                    errors.append(f"Поле «{label}»: выберите значение из списка.")
                    continue
                values[f["name"]] = raw
            elif kind == "pair":
                a, b = raw.split(":")
                values[f["cols"][0]], values[f["cols"][1]] = int(a), int(b)
        except (ValueError, InvalidOperation):
            errors.append(f"Поле «{label}»: неверное значение.")
    if not errors and "validate" in table:
        message = table["validate"](values)
        if message:
            errors.append(message)
    return values, errors


def form_values_from_row(table, row):
    """Значения полей формы по строке из БД (при изменении)."""
    out = {}
    for f in table["fields"]:
        if f["kind"] == "pair":
            out[f["name"]] = ":".join(str(row[c]) for c in f["cols"])
        else:
            v = row[f["name"]]
            out[f["name"]] = str(v)[:10] if f["kind"] == "date" else str(v)
    return out


def load_options(table, current):
    """Списки выбора: {поле: [(значение, подпись, недоступно)]}."""
    result = {}
    for f in table["fields"]:
        if "options" not in f:
            continue
        opts = []
        for r in db.rows(f["options"]):
            value, label = str(r[0]), r[1]
            full = len(r) > 2 and bool(r[2])
            opts.append((value, label, full and value != current.get(f["name"])))
        result[f["name"]] = opts
    return result


def render_form(name, table, values, mode, pk=None):
    return render_template(
        "form.html", name=name, table=table, values=values, mode=mode, pk=pk,
        options=load_options(table, values),
    )


# ---------- страницы ----------

@app.route("/")
def index():
    cards = []
    for name, t in TABLES.items():
        n = db.query(f"SELECT COUNT(*) AS n FROM {name}")[0]["n"]
        cards.append((name, t["title"], n))
    return render_template("index.html", cards=cards)


@app.route("/t/<name>")
def table_view(name):
    table = get_table(name)
    rows = db.query(table["list_sql"])
    return render_template("table.html", name=name, table=table, rows=rows)


@app.route("/t/<name>/new", methods=["GET", "POST"])
def new_row(name):
    table = get_table(name)
    if request.method == "GET":
        return render_form(name, table, {}, "new")
    values, errors = parse_form(table, request.form)
    if not errors:
        cols = list(values)
        sql = f"INSERT INTO {name} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})"
        try:
            db.execute(sql, [values[c] for c in cols])
        except Exception as exc:
            errors.append(explain_error(exc, "save"))
    if errors:
        for e in errors:
            flash(e, "error")
        return render_form(name, table, request.form.to_dict(), "new")
    flash("Строка добавлена.", "ok")
    return redirect(url_for("table_view", name=name))


@app.route("/t/<name>/edit", methods=["GET", "POST"])
def edit_row(name):
    table = get_table(name)
    pk = pk_from_request(table)
    if request.method == "GET":
        cols = [c for f in table["fields"] for c in (f.get("cols") or [f["name"]])]
        found = db.query(f"SELECT {', '.join(cols)} FROM {name} WHERE {where_clause(table)}",
                         [pk[c] for c in table["pk"]])
        if not found:
            abort(404)
        return render_form(name, table, form_values_from_row(table, found[0]), "edit", pk)
    values, errors = parse_form(table, request.form)
    if not errors:
        cols = list(values)
        sql = (f"UPDATE {name} SET {', '.join(c + ' = %s' for c in cols)} "
               f"WHERE {where_clause(table)}")
        try:
            db.execute(sql, [values[c] for c in cols] + [pk[c] for c in table["pk"]])
        except Exception as exc:
            errors.append(explain_error(exc, "save"))
    if errors:
        for e in errors:
            flash(e, "error")
        return render_form(name, table, request.form.to_dict(), "edit", pk)
    flash("Изменения сохранены.", "ok")
    return redirect(url_for("table_view", name=name))


@app.route("/t/<name>/delete", methods=["POST"])
def delete_row(name):
    table = get_table(name)
    pk = pk_from_request(table)
    try:
        db.execute(f"DELETE FROM {name} WHERE {where_clause(table)}",
                   [pk[c] for c in table["pk"]])
        flash("Строка удалена.", "ok")
    except Exception as exc:
        flash(explain_error(exc, "delete"), "error")
    return redirect(url_for("table_view", name=name))


@app.route("/queries")
def queries():
    results = []
    for title, sql, headers in REPORTS:
        try:
            results.append((title, sql, headers, db.rows(sql), None))
        except Exception as exc:
            results.append((title, sql, headers, [], str(exc).splitlines()[0]))
    return render_template("queries.html", results=results)


@app.context_processor
def nav():
    return {"nav_tables": [(n, t["title"]) for n, t in TABLES.items()]}


if __name__ == "__main__":
    app.run(debug=True)
