CREATE TABLE student (
    student_id SERIAL PRIMARY KEY,
    student_name VARCHAR ( 100 ) NOT NULL,
    student_mail VARCHAR ( 100 ) UNIQUE NOT NULL,
    student_desc VARCHAR ( 1024 ),
    student_pass VARCHAR ( 256 ) NOT NULL,
    student_img VARCHAR ( 384 ),
    student_role VARCHAR ( 20 ) NOT NULL,
    active INT default 0,
    notification INT default 0,
    password_reset VARCHAR ( 100 ),
    created timestamp default current_timestamp,
    modified timestamp default current_timestamp
);

CREATE TABLE invitation (
    invitation_id SERIAL PRIMARY KEY,
    invitation_code VARCHAR ( 20 ) UNIQUE NOT NULL,
    invitation_role VARCHAR ( 20 ) NOT NULL,
    invitation_forever INT default 0,
    invitation_taken INT default 0,
    created timestamp default current_timestamp,
    modified timestamp default current_timestamp
);

CREATE TABLE campaign (
    campaign_id SERIAL PRIMARY KEY,
    student_id INT REFERENCES student ( student_id ) ON DELETE SET NULL,
    campaign_name VARCHAR ( 100 ) UNIQUE NOT NULL,
    campaign_desc VARCHAR ( 1024 ),
    campaign_img VARCHAR ( 384),
    public_ind INT default 0,
    created timestamp default current_timestamp,
    modified timestamp default current_timestamp
);

CREATE TABLE scenario (
    scenario_id SERIAL PRIMARY KEY,
    student_id INT REFERENCES student ( student_id ) ON DELETE SET NULL,
    campaign_id INT REFERENCES campaign ( campaign_id ) ON DELETE CASCADE,
    scenario_name VARCHAR ( 100 ) UNIQUE NOT NULL,
    scenario_desc VARCHAR ( 1024 ),
    scenario_brief VARCHAR ( 1024 ),
    scenario_img VARCHAR ( 384) NOT NULL,
    legitimate INT default 0,
    created timestamp default current_timestamp,
    modified timestamp default current_timestamp
);

CREATE TABLE area (
    area_id SERIAL PRIMARY KEY,
    student_id INT REFERENCES student ( student_id ) ON DELETE SET NULL,
    scenario_id INT REFERENCES scenario ( scenario_id ) ON DELETE CASCADE,
    start_x INT default 10,
    start_y INT default 10,
    end_x INT default 20,
    end_y INT default 20,
    points INT default 0,
    hover VARCHAR ( 384),
    created timestamp default current_timestamp,
    modified timestamp default current_timestamp
);

CREATE TABLE category (
    category_id SERIAL PRIMARY KEY,
    student_id INT REFERENCES student ( student_id ) ON DELETE SET NULL,
    category_name VARCHAR ( 100 ) UNIQUE NOT NULL,
    created timestamp default current_timestamp,
    modified timestamp default current_timestamp
);

CREATE TABLE language (
    language_id SERIAL PRIMARY KEY,
    student_id INT REFERENCES student ( student_id ) ON DELETE SET NULL,
    language_name VARCHAR ( 100 ) UNIQUE NOT NULL,
    created timestamp default current_timestamp,
    modified timestamp default current_timestamp
);

CREATE TABLE lesson (
    lesson_id SERIAL PRIMARY KEY,
    student_id INT REFERENCES student ( student_id ) ON DELETE SET NULL,
    lesson_cat INT REFERENCES category ( category_id ) ON DELETE SET NULL,
    lesson_lang INT REFERENCES language ( language_id ) ON DELETE SET NULL,
    lesson_name VARCHAR ( 100 ) NOT NULL,
    lesson_mov VARCHAR ( 384) NOT NULL,
    created timestamp default current_timestamp,
    modified timestamp default current_timestamp
);

CREATE UNIQUE INDEX idx_lesson_name
ON lesson ( lesson_name, lesson_lang );

CREATE TABLE quiz (
    quiz_id SERIAL PRIMARY KEY,
    student_id INT REFERENCES student ( student_id ) ON DELETE SET NULL,
    quiz_cat INT REFERENCES category ( category_id ) ON DELETE SET NULL,
    quiz_lang INT REFERENCES language ( language_id ) ON DELETE SET NULL,
    quiz_question VARCHAR ( 1024 ) NOT NULL,
    answer_first VARCHAR ( 256 ) NOT NULL,
    answer_second VARCHAR ( 256 ) NOT NULL,
    answer_third VARCHAR ( 256 ) NOT NULL,
    answer_fourth VARCHAR ( 256 ) NOT NULL,
    quiz_solution INT default 1,
    points INT default 0,
    created timestamp default current_timestamp,
    modified timestamp default current_timestamp
);

CREATE TABLE quiz_score (
    quiz_score_id SERIAL PRIMARY KEY,
    student_id INT REFERENCES student ( student_id ) ON DELETE CASCADE,
    quiz_id INT REFERENCES quiz ( quiz_id ) ON DELETE CASCADE,
    points INT default 0,
    created timestamp default current_timestamp,
    modified timestamp default current_timestamp
);

CREATE TABLE scenario_score (
    scenario_score_id SERIAL PRIMARY KEY,
    student_id INT REFERENCES student ( student_id ) ON DELETE CASCADE,
    scenario_id INT REFERENCES scenario ( scenario_id ) ON DELETE CASCADE,
    points INT default 0,
    created timestamp default current_timestamp,
    modified timestamp default current_timestamp
);


CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.modified = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_student_modtime BEFORE UPDATE ON student FOR EACH ROW EXECUTE PROCEDURE  update_modified_column();
CREATE TRIGGER update_invitation_modtime BEFORE UPDATE ON invitation FOR EACH ROW EXECUTE PROCEDURE  update_modified_column();
CREATE TRIGGER update_campaign_modtime BEFORE UPDATE ON campaign FOR EACH ROW EXECUTE PROCEDURE  update_modified_column();
CREATE TRIGGER update_scenario_modtime BEFORE UPDATE ON scenario FOR EACH ROW EXECUTE PROCEDURE  update_modified_column();
CREATE TRIGGER update_area_modtime BEFORE UPDATE ON area FOR EACH ROW EXECUTE PROCEDURE  update_modified_column();
CREATE TRIGGER update_category_modtime BEFORE UPDATE ON category FOR EACH ROW EXECUTE PROCEDURE  update_modified_column();
CREATE TRIGGER update_language_modtime BEFORE UPDATE ON language FOR EACH ROW EXECUTE PROCEDURE  update_modified_column();
CREATE TRIGGER update_lesson_modtime BEFORE UPDATE ON lesson FOR EACH ROW EXECUTE PROCEDURE  update_modified_column();
CREATE TRIGGER update_quiz_modtime BEFORE UPDATE ON quiz FOR EACH ROW EXECUTE PROCEDURE  update_modified_column();
CREATE TRIGGER update_quiz_score_modtime BEFORE UPDATE ON quiz_score FOR EACH ROW EXECUTE PROCEDURE  update_modified_column();
CREATE TRIGGER update_scenario_score_modtime BEFORE UPDATE ON scenario_score FOR EACH ROW EXECUTE PROCEDURE  update_modified_column();


-- Default credentials, need to be changed on production stage
INSERT INTO invitation(invitation_code, invitation_role, invitation_forever) VALUES ('heureka', 'student', 1);
INSERT INTO invitation(invitation_code, invitation_role, invitation_forever) VALUES ('sunshine', 'admin', 0);
