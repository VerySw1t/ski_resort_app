-- ski_resort.sql
-- База данных «Горнолыжный курорт с прокатом». PostgreSQL 14 или новее.
-- Запуск (подключившись к служебной базе postgres):
--   psql -h localhost -U postgres -d postgres -f ski_resort.sql
-- Повторный запуск стирает базу ski_resort и собирает её заново.

DROP DATABASE IF EXISTS ski_resort;

CREATE DATABASE ski_resort
    TEMPLATE template0
    ENCODING 'UTF8'
    LC_COLLATE 'ru_RU.UTF-8'
    LC_CTYPE 'ru_RU.UTF-8';

\connect ski_resort

-- Расширение нужно для запрета пересекающихся броней одного номера.
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ---------------------------------------------------------------
-- Справочники
-- ---------------------------------------------------------------

CREATE TABLE guests (
    id    integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name  varchar(100) NOT NULL,
    phone varchar(20)  NOT NULL UNIQUE,
    email varchar(100) NOT NULL UNIQUE
);

CREATE TABLE room_categories (
    id              integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title           varchar(40)   NOT NULL UNIQUE,
    rooms_count     integer       NOT NULL CHECK (rooms_count > 0),
    capacity        integer       NOT NULL CHECK (capacity > 0),
    price_per_night numeric(10,2) NOT NULL CHECK (price_per_night > 0)
);

CREATE TABLE rooms (
    id          integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    number      integer NOT NULL UNIQUE,
    category_id integer NOT NULL
        REFERENCES room_categories (id) ON DELETE RESTRICT
);

CREATE TABLE packages (
    id    integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title varchar(40) NOT NULL UNIQUE,
    meal  varchar(20) NOT NULL,
    CONSTRAINT known_meal
        CHECK (meal IN ('без питания', 'завтрак', 'полупансион', 'всё включено'))
);

CREATE TABLE spa_services (
    id   integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name varchar(60) NOT NULL UNIQUE
);

CREATE TABLE equipment (
    id            integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          varchar(60)   NOT NULL UNIQUE,
    price_per_day numeric(10,2) NOT NULL CHECK (price_per_day > 0)
);

CREATE TABLE ski_passes (
    id    integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    days  integer       NOT NULL UNIQUE CHECK (days > 0),
    price numeric(10,2) NOT NULL CHECK (price > 0)
);

-- ---------------------------------------------------------------
-- Брони и связи
-- ---------------------------------------------------------------

CREATE TABLE package_spa (
    package_id integer NOT NULL REFERENCES packages (id)     ON DELETE RESTRICT,
    spa_id     integer NOT NULL REFERENCES spa_services (id) ON DELETE RESTRICT,
    PRIMARY KEY (package_id, spa_id)
);

CREATE TABLE bookings (
    id         integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    room_id    integer NOT NULL REFERENCES rooms (id)    ON DELETE RESTRICT,
    package_id integer NOT NULL REFERENCES packages (id) ON DELETE RESTRICT,
    check_in   date    NOT NULL,
    check_out  date    NOT NULL,
    CONSTRAINT booking_dates CHECK (check_out > check_in),
    -- Один номер не бронируют на пересекающиеся даты.
    -- Интервал [заезд, выезд): день выезда одной брони может быть днём заезда другой.
    CONSTRAINT no_room_overlap EXCLUDE USING gist (
        room_id WITH =,
        daterange(check_in, check_out) WITH &&
    )
);

CREATE TABLE booking_guests (
    booking_id  integer     NOT NULL REFERENCES bookings (id)   ON DELETE RESTRICT,
    guest_id    integer     NOT NULL REFERENCES guests (id)     ON DELETE RESTRICT,
    role        varchar(20) NOT NULL,
    ski_pass_id integer     NOT NULL REFERENCES ski_passes (id) ON DELETE RESTRICT,
    PRIMARY KEY (booking_id, guest_id),
    CONSTRAINT known_role CHECK (role IN ('плательщик', 'гость'))
);

CREATE TABLE rentals (
    booking_id   integer NOT NULL,
    guest_id     integer NOT NULL,
    equipment_id integer NOT NULL REFERENCES equipment (id) ON DELETE RESTRICT,
    rent_from    date    NOT NULL,
    rent_to      date    NOT NULL,
    PRIMARY KEY (booking_id, guest_id, equipment_id, rent_from),
    -- Снаряжение выдают только тому, кто записан в этой брони.
    FOREIGN KEY (booking_id, guest_id)
        REFERENCES booking_guests (booking_id, guest_id) ON DELETE RESTRICT,
    CONSTRAINT rental_dates CHECK (rent_to >= rent_from)
);

-- ---------------------------------------------------------------
-- Вместимость: число гостей в брони не больше вместимости категории номера.
-- Обычным CHECK это не записать, потому что нужны данные из других таблиц.
-- ---------------------------------------------------------------

CREATE FUNCTION check_booking_capacity() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_booking integer;
    v_guests  integer;
    v_max     integer;
BEGIN
    IF TG_TABLE_NAME = 'bookings' THEN
        v_booking := NEW.id;
    ELSE
        v_booking := NEW.booking_id;
    END IF;

    SELECT COUNT(*) INTO v_guests
    FROM booking_guests
    WHERE booking_id = v_booking;

    SELECT room_categories.capacity INTO v_max
    FROM bookings
    JOIN rooms           ON rooms.id = bookings.room_id
    JOIN room_categories ON room_categories.id = rooms.category_id
    WHERE bookings.id = v_booking;

    IF v_guests > v_max THEN
        RAISE EXCEPTION 'В брони % гостей: %, вместимость номера: %',
            v_booking, v_guests, v_max
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$;

CREATE TRIGGER capacity_on_guest
    AFTER INSERT OR UPDATE ON booking_guests
    FOR EACH ROW EXECUTE FUNCTION check_booking_capacity();

CREATE TRIGGER capacity_on_room
    AFTER UPDATE OF room_id ON bookings
    FOR EACH ROW EXECUTE FUNCTION check_booking_capacity();

-- ---------------------------------------------------------------
-- Учебные данные. Столбец id в INSERT не пишут: его ставит база.
-- Цены условные.
-- ---------------------------------------------------------------

INSERT INTO guests (name, phone, email) VALUES
    ('Иван Петров',    '+7 900 111-22-33', 'ivan@mail.ru'),
    ('Анна Петрова',   '+7 900 111-22-44', 'anna@mail.ru'),
    ('Дмитрий Орлов',  '+7 900 111-22-55', 'dmitry@mail.ru'),
    ('Ольга Смирнова', '+7 900 111-22-66', 'olga@mail.ru');

INSERT INTO room_categories (title, rooms_count, capacity, price_per_night) VALUES
    ('Класс A', 1, 2,  6000),
    ('Класс B', 2, 4, 10000),
    ('Класс C', 3, 6, 15000);

INSERT INTO rooms (number, category_id) VALUES
    (2, (SELECT id FROM room_categories WHERE title = 'Класс A')),
    (5, (SELECT id FROM room_categories WHERE title = 'Класс B')),
    (7, (SELECT id FROM room_categories WHERE title = 'Класс C'));

INSERT INTO packages (title, meal) VALUES
    ('Стандарт', 'завтрак'),
    ('Комфорт',  'полупансион'),
    ('Премиум',  'всё включено');

INSERT INTO spa_services (name) VALUES ('Сауна'), ('Массаж');

INSERT INTO package_spa (package_id, spa_id) VALUES
    ((SELECT id FROM packages     WHERE title = 'Комфорт'), (SELECT id FROM spa_services WHERE name = 'Сауна')),
    ((SELECT id FROM packages     WHERE title = 'Премиум'), (SELECT id FROM spa_services WHERE name = 'Сауна')),
    ((SELECT id FROM packages     WHERE title = 'Премиум'), (SELECT id FROM spa_services WHERE name = 'Массаж'));

INSERT INTO equipment (name, price_per_day) VALUES
    ('Лыжи',     1200),
    ('Сноуборд', 1500),
    ('Шлем',      300);

INSERT INTO ski_passes (days, price) VALUES (2, 6000), (7, 18000);

INSERT INTO bookings (room_id, package_id, check_in, check_out) VALUES
    ((SELECT id FROM rooms WHERE number = 5),
     (SELECT id FROM packages WHERE title = 'Премиум'),  '2026-12-20', '2026-12-27'),
    ((SELECT id FROM rooms WHERE number = 2),
     (SELECT id FROM packages WHERE title = 'Стандарт'), '2027-01-05', '2027-01-07');

-- Брони получили номера 1 и 2 в порядке вставки.
INSERT INTO booking_guests (booking_id, guest_id, role, ski_pass_id) VALUES
    (1, (SELECT id FROM guests WHERE name = 'Иван Петров'),   'плательщик', (SELECT id FROM ski_passes WHERE days = 7)),
    (1, (SELECT id FROM guests WHERE name = 'Анна Петрова'),  'гость',      (SELECT id FROM ski_passes WHERE days = 7)),
    (2, (SELECT id FROM guests WHERE name = 'Дмитрий Орлов'), 'плательщик', (SELECT id FROM ski_passes WHERE days = 2));

INSERT INTO rentals (booking_id, guest_id, equipment_id, rent_from, rent_to) VALUES
    (1, (SELECT id FROM guests WHERE name = 'Иван Петров'),
        (SELECT id FROM equipment WHERE name = 'Лыжи'),     '2026-12-20', '2026-12-26'),
    (1, (SELECT id FROM guests WHERE name = 'Анна Петрова'),
        (SELECT id FROM equipment WHERE name = 'Сноуборд'), '2026-12-20', '2026-12-26');
