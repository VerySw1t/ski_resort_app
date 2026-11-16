"""Описание таблиц: какие поля показывать, как проверять и откуда брать списки.

Имена таблиц и столбцов берутся только отсюда, из запроса пользователя
в SQL попадают одни значения (через параметры).
"""

MEALS = ["без питания", "завтрак", "полупансион", "всё включено"]
ROLES = ["плательщик", "гость"]


def _dates_order(a, b, strict, message):
    def check(v):
        if v.get(a) and v.get(b):
            bad = v[b] <= v[a] if strict else v[b] < v[a]
            if bad:
                return message
    return check


TABLES = {
    "guests": {
        "title": "Гости",
        "pk": ["id"],
        "fields": [
            {"name": "name", "label": "Имя", "kind": "text", "max": 100},
            {"name": "phone", "label": "Телефон", "kind": "text", "max": 20},
            {"name": "email", "label": "Почта", "kind": "text", "max": 100},
        ],
        "list_sql": "SELECT id, name, phone, email FROM guests ORDER BY name",
        "show": [("name", "Имя"), ("phone", "Телефон"), ("email", "Почта")],
    },
    "room_categories": {
        "title": "Категории номеров",
        "pk": ["id"],
        "fields": [
            {"name": "title", "label": "Название", "kind": "text", "max": 40},
            {"name": "rooms_count", "label": "Комнат", "kind": "int", "min": 1},
            {"name": "capacity", "label": "Вместимость", "kind": "int", "min": 1},
            {"name": "price_per_night", "label": "Цена за ночь", "kind": "number", "min": 0.01},
        ],
        "list_sql": "SELECT id, title, rooms_count, capacity, price_per_night "
                    "FROM room_categories ORDER BY title",
        "show": [("title", "Название"), ("rooms_count", "Комнат"),
                 ("capacity", "Вместимость"), ("price_per_night", "Цена за ночь")],
        "money": ["price_per_night"],
    },
    "rooms": {
        "title": "Номера",
        "pk": ["id"],
        "fields": [
            {"name": "number", "label": "Номер", "kind": "int", "min": 1},
            {"name": "category_id", "label": "Категория", "kind": "fk",
             "options": "SELECT id, title FROM room_categories ORDER BY title"},
        ],
        "list_sql": "SELECT rooms.id, rooms.number, room_categories.title AS category "
                    "FROM rooms JOIN room_categories ON room_categories.id = rooms.category_id "
                    "ORDER BY rooms.number",
        "show": [("number", "Номер"), ("category", "Категория")],
    },
    "packages": {
        "title": "Пакеты",
        "pk": ["id"],
        "fields": [
            {"name": "title", "label": "Название", "kind": "text", "max": 40},
            {"name": "meal", "label": "Питание", "kind": "choice", "choices": MEALS},
        ],
        "list_sql": "SELECT id, title, meal FROM packages ORDER BY title",
        "show": [("title", "Название"), ("meal", "Питание")],
    },
    "spa_services": {
        "title": "Спа-процедуры",
        "pk": ["id"],
        "fields": [{"name": "name", "label": "Название", "kind": "text", "max": 60}],
        "list_sql": "SELECT id, name FROM spa_services ORDER BY name",
        "show": [("name", "Название")],
    },
    "equipment": {
        "title": "Оборудование",
        "pk": ["id"],
        "fields": [
            {"name": "name", "label": "Название", "kind": "text", "max": 60},
            {"name": "price_per_day", "label": "Цена за день", "kind": "number", "min": 0.01},
        ],
        "list_sql": "SELECT id, name, price_per_day FROM equipment ORDER BY name",
        "show": [("name", "Название"), ("price_per_day", "Цена за день")],
        "money": ["price_per_day"],
    },
    "ski_passes": {
        "title": "Ски-пассы",
        "pk": ["id"],
        "fields": [
            {"name": "days", "label": "Срок, дней", "kind": "int", "min": 1},
            {"name": "price", "label": "Цена", "kind": "number", "min": 0.01},
        ],
        "list_sql": "SELECT id, days, price FROM ski_passes ORDER BY days",
        "show": [("days", "Срок, дней"), ("price", "Цена")],
        "money": ["price"],
    },
    "bookings": {
        "title": "Брони",
        "pk": ["id"],
        "fields": [
            {"name": "room_id", "label": "Номер", "kind": "fk",
             "options": "SELECT rooms.id, 'Номер ' || rooms.number || ' · ' || room_categories.title "
                        "FROM rooms JOIN room_categories ON room_categories.id = rooms.category_id "
                        "ORDER BY rooms.number"},
            {"name": "package_id", "label": "Пакет", "kind": "fk",
             "options": "SELECT id, title FROM packages ORDER BY title"},
            {"name": "check_in", "label": "Заезд", "kind": "date"},
            {"name": "check_out", "label": "Выезд", "kind": "date"},
        ],
        "validate": _dates_order("check_in", "check_out", True,
                                 "Дата выезда должна быть позже даты заезда."),
        "list_sql": "SELECT bookings.id, rooms.number AS room, room_categories.title AS category, "
                    "packages.title AS package, bookings.check_in, bookings.check_out, "
                    "(SELECT COUNT(*) FROM booking_guests "
                    " WHERE booking_guests.booking_id = bookings.id) AS guests "
                    "FROM bookings JOIN rooms ON rooms.id = bookings.room_id "
                    "JOIN room_categories ON room_categories.id = rooms.category_id "
                    "JOIN packages ON packages.id = bookings.package_id "
                    "ORDER BY bookings.check_in, bookings.id",
        "show": [("id", "Бронь"), ("room", "Номер"), ("category", "Категория"),
                 ("package", "Пакет"), ("check_in", "Заезд"), ("check_out", "Выезд"),
                 ("guests", "Гостей")],
    },
    "package_spa": {
        "title": "Состав пакета",
        "pk": ["package_id", "spa_id"],
        "fields": [
            {"name": "package_id", "label": "Пакет", "kind": "fk",
             "options": "SELECT id, title FROM packages ORDER BY title"},
            {"name": "spa_id", "label": "Процедура", "kind": "fk",
             "options": "SELECT id, name FROM spa_services ORDER BY name"},
        ],
        "list_sql": "SELECT package_spa.package_id, package_spa.spa_id, "
                    "packages.title AS package, spa_services.name AS spa "
                    "FROM package_spa JOIN packages ON packages.id = package_spa.package_id "
                    "JOIN spa_services ON spa_services.id = package_spa.spa_id "
                    "ORDER BY packages.title, spa_services.name",
        "show": [("package", "Пакет"), ("spa", "Процедура")],
    },
    "booking_guests": {
        "title": "Состав брони",
        "pk": ["booking_id", "guest_id"],
        "fields": [
            # Третий столбец списка: 1 — бронь заполнена, выбрать её нельзя.
            {"name": "booking_id", "label": "Бронь", "kind": "fk",
             "options": "SELECT bookings.id, 'Бронь ' || bookings.id || ' · номер ' || rooms.number "
                        "|| ' · ' || CAST(bookings.check_in AS text) || ' — ' "
                        "|| CAST(bookings.check_out AS text) || ' (гостей: ' "
                        "|| CAST((SELECT COUNT(*) FROM booking_guests bg "
                        "        WHERE bg.booking_id = bookings.id) AS text) "
                        "|| ' из ' || CAST(room_categories.capacity AS text) || ')', "
                        "CASE WHEN (SELECT COUNT(*) FROM booking_guests bg "
                        "           WHERE bg.booking_id = bookings.id) >= room_categories.capacity "
                        "     THEN 1 ELSE 0 END "
                        "FROM bookings JOIN rooms ON rooms.id = bookings.room_id "
                        "JOIN room_categories ON room_categories.id = rooms.category_id "
                        "ORDER BY bookings.id"},
            {"name": "guest_id", "label": "Гость", "kind": "fk",
             "options": "SELECT id, name FROM guests ORDER BY name"},
            {"name": "role", "label": "Роль", "kind": "choice", "choices": ROLES},
            {"name": "ski_pass_id", "label": "Ски-пасс", "kind": "fk",
             "options": "SELECT id, CAST(days AS text) || ' дн.' FROM ski_passes ORDER BY days"},
        ],
        "list_sql": "SELECT booking_guests.booking_id, booking_guests.guest_id, "
                    "rooms.number AS room, guests.name AS guest, booking_guests.role, "
                    "ski_passes.days AS pass_days "
                    "FROM booking_guests "
                    "JOIN bookings ON bookings.id = booking_guests.booking_id "
                    "JOIN rooms ON rooms.id = bookings.room_id "
                    "JOIN guests ON guests.id = booking_guests.guest_id "
                    "JOIN ski_passes ON ski_passes.id = booking_guests.ski_pass_id "
                    "ORDER BY booking_guests.booking_id, guests.name",
        "show": [("booking_id", "Бронь"), ("room", "Номер"), ("guest", "Гость"),
                 ("role", "Роль"), ("pass_days", "Ски-пасс, дней")],
    },
    "rentals": {
        "title": "Прокат",
        "pk": ["booking_id", "guest_id", "equipment_id", "rent_from"],
        "fields": [
            # Пара «бронь + гость»: в списке только те, кто записан в брони.
            {"name": "booking_guest", "label": "Бронь и гость", "kind": "pair",
             "cols": ["booking_id", "guest_id"],
             "options": "SELECT CAST(booking_guests.booking_id AS text) || ':' "
                        "|| CAST(booking_guests.guest_id AS text), "
                        "'Бронь ' || booking_guests.booking_id || ' · ' || guests.name "
                        "FROM booking_guests JOIN guests ON guests.id = booking_guests.guest_id "
                        "ORDER BY booking_guests.booking_id, guests.name"},
            {"name": "equipment_id", "label": "Оборудование", "kind": "fk",
             "options": "SELECT id, name FROM equipment ORDER BY name"},
            {"name": "rent_from", "label": "С даты", "kind": "date"},
            {"name": "rent_to", "label": "По дату", "kind": "date"},
        ],
        "validate": _dates_order("rent_from", "rent_to", False,
                                 "Дата окончания проката не может быть раньше начала."),
        "list_sql": "SELECT rentals.booking_id, rentals.guest_id, rentals.equipment_id, "
                    "rentals.rent_from, rentals.rent_to, guests.name AS guest, "
                    "equipment.name AS equipment "
                    "FROM rentals JOIN guests ON guests.id = rentals.guest_id "
                    "JOIN equipment ON equipment.id = rentals.equipment_id "
                    "ORDER BY rentals.booking_id, guests.name, rentals.rent_from",
        "show": [("booking_id", "Бронь"), ("guest", "Гость"), ("equipment", "Оборудование"),
                 ("rent_from", "С даты"), ("rent_to", "По дату")],
    },
}

# Запросы из раздела 4.4 отчёта.
REPORTS = [
    ("Состав брони в номере 5",
     "SELECT guests.name, booking_guests.role, ski_passes.days "
     "FROM booking_guests "
     "JOIN guests ON guests.id = booking_guests.guest_id "
     "JOIN bookings ON bookings.id = booking_guests.booking_id "
     "JOIN rooms ON rooms.id = bookings.room_id "
     "JOIN ski_passes ON ski_passes.id = booking_guests.ski_pass_id "
     "WHERE rooms.number = 5 ORDER BY guests.name",
     ["Гость", "Роль", "Ски-пасс, дней"]),
    ("Пакет, питание и процедуры (пакет без процедур остаётся в ответе)",
     "SELECT bookings.id, packages.title, packages.meal, spa_services.name "
     "FROM bookings JOIN packages ON packages.id = bookings.package_id "
     "LEFT JOIN package_spa ON package_spa.package_id = packages.id "
     "LEFT JOIN spa_services ON spa_services.id = package_spa.spa_id "
     "ORDER BY bookings.id, spa_services.name",
     ["Бронь", "Пакет", "Питание", "Процедура"]),
    ("Число гостей и стоимость проживания",
     "SELECT bookings.id, rooms.number, room_categories.title, "
     "COUNT(booking_guests.guest_id) AS guests, "
     "(bookings.check_out - bookings.check_in) * room_categories.price_per_night AS stay_cost "
     "FROM bookings JOIN rooms ON rooms.id = bookings.room_id "
     "JOIN room_categories ON room_categories.id = rooms.category_id "
     "JOIN booking_guests ON booking_guests.booking_id = bookings.id "
     "GROUP BY bookings.id, rooms.number, room_categories.title, room_categories.price_per_night "
     "ORDER BY bookings.id",
     ["Бронь", "Номер", "Категория", "Гостей", "Проживание"]),
    ("Номера, которые никто не бронировал",
     "SELECT rooms.number, room_categories.title FROM rooms "
     "JOIN room_categories ON room_categories.id = rooms.category_id "
     "LEFT JOIN bookings ON bookings.room_id = rooms.id WHERE bookings.id IS NULL",
     ["Номер", "Категория"]),
    ("Прокат и его цена (то, что не выдавали, остаётся в ответе)",
     "SELECT equipment.name, guests.name AS guest, "
     "rentals.rent_to - rentals.rent_from + 1 AS days, "
     "(rentals.rent_to - rentals.rent_from + 1) * equipment.price_per_day AS cost "
     "FROM equipment LEFT JOIN rentals ON rentals.equipment_id = equipment.id "
     "LEFT JOIN guests ON guests.id = rentals.guest_id ORDER BY equipment.id",
     ["Оборудование", "Гость", "Дней", "Стоимость"]),
]
