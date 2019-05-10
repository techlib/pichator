-- Database generated with pgModeler (PostgreSQL Database Modeler).
-- pgModeler  version: 0.9.1
-- PostgreSQL version: 10.0
-- Project Site: pgmodeler.io
-- Model Author: ---

-- object: pichator | type: ROLE --
-- DROP ROLE IF EXISTS pichator;
CREATE ROLE pichator WITH 
	INHERIT
	LOGIN
	ENCRYPTED PASSWORD '********';
-- ddl-end --


-- Database creation must be done outside a multicommand file.
-- These commands were put in this file only as a convenience.
-- -- object: pichator | type: DATABASE --
-- -- DROP DATABASE IF EXISTS pichator;
-- CREATE DATABASE pichator
-- 	ENCODING = 'UTF8'
-- 	LC_COLLATE = 'en_US.UTF-8'
-- 	LC_CTYPE = 'en_US.UTF-8'
-- 	TABLESPACE = pg_default
-- 	OWNER = postgres;
-- -- ddl-end --
-- 

-- -- object: public."EMPLOYEE_UID_seq" | type: SEQUENCE --
-- -- DROP SEQUENCE IF EXISTS public."EMPLOYEE_UID_seq" CASCADE;
-- CREATE SEQUENCE public."EMPLOYEE_UID_seq"
-- 	INCREMENT BY 1
-- 	MINVALUE 1
-- 	MAXVALUE 9223372036854775807
-- 	START WITH 1
-- 	CACHE 1
-- 	NO CYCLE
-- 	OWNED BY NONE;
-- -- ddl-end --
-- ALTER SEQUENCE public."EMPLOYEE_UID_seq" OWNER TO pichator;
-- -- ddl-end --
-- 
-- object: public.employee | type: TABLE --
-- DROP TABLE IF EXISTS public.employee CASCADE;
CREATE TABLE public.employee(
	first_name character varying NOT NULL,
	last_name character varying NOT NULL,
	emp_no smallint,
	username character varying NOT NULL,
	uid bigint NOT NULL,
	CONSTRAINT employee_pk PRIMARY KEY (uid)

);
-- ddl-end --
ALTER TABLE public.employee OWNER TO pichator;
-- ddl-end --

-- -- object: public."TIMETABLE_UID_seq" | type: SEQUENCE --
-- -- DROP SEQUENCE IF EXISTS public."TIMETABLE_UID_seq" CASCADE;
-- CREATE SEQUENCE public."TIMETABLE_UID_seq"
-- 	INCREMENT BY 1
-- 	MINVALUE 1
-- 	MAXVALUE 9223372036854775807
-- 	START WITH 1
-- 	CACHE 1
-- 	NO CYCLE
-- 	OWNED BY NONE;
-- -- ddl-end --
-- ALTER SEQUENCE public."TIMETABLE_UID_seq" OWNER TO pichator;
-- -- ddl-end --
-- 
-- object: public.timerange | type: TYPE --
-- DROP TYPE IF EXISTS public.timerange CASCADE;
CREATE TYPE public.timerange AS
RANGE (
SUBTYPE = time);
-- ddl-end --
ALTER TYPE public.timerange OWNER TO pichator;
-- ddl-end --

-- -- object: public."PRESENCE_UID_seq" | type: SEQUENCE --
-- -- DROP SEQUENCE IF EXISTS public."PRESENCE_UID_seq" CASCADE;
-- CREATE SEQUENCE public."PRESENCE_UID_seq"
-- 	INCREMENT BY 1
-- 	MINVALUE 1
-- 	MAXVALUE 9223372036854775807
-- 	START WITH 1
-- 	CACHE 1
-- 	NO CYCLE
-- 	OWNED BY NONE;
-- -- ddl-end --
-- ALTER SEQUENCE public."PRESENCE_UID_seq" OWNER TO postgres;
-- -- ddl-end --
-- 
-- object: public.presence_modes | type: TYPE --
-- DROP TYPE IF EXISTS public.presence_modes CASCADE;
CREATE TYPE public.presence_modes AS
 ENUM ('Doctor visit','Compensatory time off','Vacation','Sickday','Unpaid leave','Absence','Employer difficulties','Vacation 0.5','On call time','Sickness','Family member care','Personal trouble','Bussiness trip 4h-','Bussiness trip 4h+','Study','Training','Training -','Injury and disease from profession','Public benefit','Presence','Presence-');
-- ddl-end --
ALTER TYPE public.presence_modes OWNER TO pichator;
-- ddl-end --

-- object: public.presence | type: TABLE --
-- DROP TABLE IF EXISTS public.presence CASCADE;
CREATE TABLE public.presence(
	presid bigint NOT NULL GENERATED ALWAYS AS IDENTITY ,
	date date NOT NULL,
	presence boolean NOT NULL DEFAULT false,
	presence_mode public.presence_modes NOT NULL,
	uid_pv bigint NOT NULL,
	"from" time NOT NULL,
	"to" time NOT NULL,
	source character varying NOT NULL,
	CONSTRAINT presence_pk PRIMARY KEY (presid)

);
-- ddl-end --
ALTER TABLE public.presence OWNER TO postgres;
-- ddl-end --

-- object: public.pv | type: TABLE --
-- DROP TABLE IF EXISTS public.pv CASCADE;
CREATE TABLE public.pv(
	pvid character varying,
	occupancy decimal NOT NULL,
	department smallint NOT NULL,
	uid bigint NOT NULL GENERATED ALWAYS AS IDENTITY ,
	validity tsrange NOT NULL,
	uid_employee bigint NOT NULL,
	CONSTRAINT pv_pk PRIMARY KEY (uid)

);
-- ddl-end --
ALTER TABLE public.pv OWNER TO pichator;
-- ddl-end --

-- object: public.helper_variables | type: TABLE --
-- DROP TABLE IF EXISTS public.helper_variables CASCADE;
CREATE TABLE public.helper_variables(
	key character varying,
	value character varying
);
-- ddl-end --
ALTER TABLE public.helper_variables OWNER TO pichator;
-- ddl-end --

-- object: pv_fk | type: CONSTRAINT --
-- ALTER TABLE public.presence DROP CONSTRAINT IF EXISTS pv_fk CASCADE;
ALTER TABLE public.presence ADD CONSTRAINT pv_fk FOREIGN KEY (uid_pv)
REFERENCES public.pv (uid) MATCH FULL
ON DELETE RESTRICT ON UPDATE CASCADE;
-- ddl-end --

-- object: public.timetable | type: TABLE --
-- DROP TABLE IF EXISTS public.timetable CASCADE;
CREATE TABLE public.timetable(
	monday public.timerange,
	tuesday public.timerange,
	wedensday public.timerange,
	thursday public.timerange,
	friday public.timerange,
	timeid bigint NOT NULL GENERATED ALWAYS AS IDENTITY ,
	uid_pv bigint NOT NULL,
	CONSTRAINT timetable_pk PRIMARY KEY (timeid)

);
-- ddl-end --
ALTER TABLE public.timetable OWNER TO pichator;
-- ddl-end --

-- object: pv_fk | type: CONSTRAINT --
-- ALTER TABLE public.timetable DROP CONSTRAINT IF EXISTS pv_fk CASCADE;
ALTER TABLE public.timetable ADD CONSTRAINT pv_fk FOREIGN KEY (uid_pv)
REFERENCES public.pv (uid) MATCH FULL
ON DELETE RESTRICT ON UPDATE CASCADE;
-- ddl-end --

-- object: timetable_uq | type: CONSTRAINT --
-- ALTER TABLE public.timetable DROP CONSTRAINT IF EXISTS timetable_uq CASCADE;
ALTER TABLE public.timetable ADD CONSTRAINT timetable_uq UNIQUE (uid_pv);
-- ddl-end --

-- object: employee_fk | type: CONSTRAINT --
-- ALTER TABLE public.pv DROP CONSTRAINT IF EXISTS employee_fk CASCADE;
ALTER TABLE public.pv ADD CONSTRAINT employee_fk FOREIGN KEY (uid_employee)
REFERENCES public.employee (uid) MATCH FULL
ON DELETE RESTRICT ON UPDATE CASCADE;
-- ddl-end --


