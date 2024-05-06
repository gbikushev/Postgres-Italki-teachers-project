BEGIN;

DROP TABLE IF EXISTS teachers_languages;
DROP TABLE IF EXISTS languages;
DROP TABLE IF EXISTS teachers;
DROP TYPE IF EXISTS language_type;


CREATE TYPE language_type as ENUM
(
	'English', 'Spanish', 'Russian',
	'Japanese', 'Italian'
);

CREATE TABLE languages
(
    language_id VARCHAR(10) PRIMARY KEY,
    language language_type NOT NULL
);

CREATE TABLE teachers
(
    teacher_id bigint PRIMARY KEY,
    name text NOT NULL,
	rating numeric(2, 1) CHECK (rating>= 0.0 AND rating<= 5.0) NOT NULL,
	students integer NOT NULL,
    lessons integer NOT NULL,
    attendance smallint NOT NULL,
    response smallint NOT NULL,
    reviews integer NOT NULL,
    price numeric(5, 2) CHECK (price > 0.00) NOT NULL,
    link text NOT NULL UNIQUE
);

CREATE TABLE teachers_languages
(
	teachers_languages_id bigserial PRIMARY KEY,
    teacher_id bigint NOT NULL,
    language_id VARCHAR(10) NOT NULL,
	FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id),
	FOREIGN KEY (language_id) REFERENCES languages(language_id)
);

END;