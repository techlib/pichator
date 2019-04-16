-- Database generated with pgModeler (PostgreSQL Database Modeler).
-- pgModeler  version: 0.9.1
-- PostgreSQL version: 10.0
-- Project Site: pgmodeler.io
-- Model Author: ---

-- object: pichackator | type: ROLE --
-- DROP ROLE IF EXISTS pichackator;
CREATE ROLE pichackator WITH 
	INHERIT
	LOGIN
	ENCRYPTED PASSWORD '********';
-- ddl-end --


-- Database creation must be done outside a multicommand file.
-- These commands were put in this file only as a convenience.
-- -- object: pichackator | type: DATABASE --
-- -- DROP DATABASE IF EXISTS pichackator;
-- CREATE DATABASE pichackator
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
-- ALTER SEQUENCE public."EMPLOYEE_UID_seq" OWNER TO pichackator;
-- -- ddl-end --
-- 
-- object: public."EMPLOYEE" | type: TABLE --
-- DROP TABLE IF EXISTS public."EMPLOYEE" CASCADE;
CREATE TABLE public."EMPLOYEE"(
	"EMPID" bigint NOT NULL GENERATED ALWAYS AS IDENTITY ,
	"FIRST_NAME" character varying NOT NULL,
	"LAST_NAME" character varying NOT NULL,
	"EKV_ID" smallint NOT NULL,
	CONSTRAINT "EMPLOYEE_pk" PRIMARY KEY ("EMPID")

);
-- ddl-end --
ALTER TABLE public."EMPLOYEE" OWNER TO pichackator;
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
-- ALTER SEQUENCE public."TIMETABLE_UID_seq" OWNER TO pichackator;
-- -- ddl-end --
-- 
-- object: public."TIMETABLE" | type: TABLE --
-- DROP TABLE IF EXISTS public."TIMETABLE" CASCADE;
CREATE TABLE public."TIMETABLE"(
	"MONDAY" tsrange,
	"TUESDAY" tsrange,
	"WEDENSDAY" tsrange,
	"THURSDAY" tsrange,
	"FRIDAY" tsrange,
	"TIMEID" bigint NOT NULL GENERATED ALWAYS AS IDENTITY ,
	"VALIDITY" tsrange,
	"PVID_PV" smallint NOT NULL,
	CONSTRAINT "TIMETABLE_pk" PRIMARY KEY ("TIMEID")

);
-- ddl-end --
ALTER TABLE public."TIMETABLE" OWNER TO pichackator;
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
-- object: public."PRESENCE_MODES" | type: TYPE --
-- DROP TYPE IF EXISTS public."PRESENCE_MODES" CASCADE;
CREATE TYPE public."PRESENCE_MODES" AS
 ENUM ('Doctor visit','Compensatory time off','Vacation','Sickday','Unpaid leave','Absence','Employer difficulties','Vacation 0.5','On call time','Sickness','Family member care','Personal trouble','Bussiness trip 4h-','Bussiness trip 4h+','Study','Training','Training -','Injury and disease from profession','Public benefit','Presence','Presence-');
-- ddl-end --
ALTER TYPE public."PRESENCE_MODES" OWNER TO pichackator;
-- ddl-end --

-- object: public."PRESENCE" | type: TABLE --
-- DROP TABLE IF EXISTS public."PRESENCE" CASCADE;
CREATE TABLE public."PRESENCE"(
	"PRESID" bigint NOT NULL GENERATED ALWAYS AS IDENTITY ,
	"DATE" date NOT NULL,
	"PRESENCE" boolean NOT NULL DEFAULT false,
	"PRESENCE_MODE" public."PRESENCE_MODES" NOT NULL,
	"PVID_PV" smallint NOT NULL
);
-- ddl-end --
ALTER TABLE public."PRESENCE" OWNER TO postgres;
-- ddl-end --

-- object: public."PV" | type: TABLE --
-- DROP TABLE IF EXISTS public."PV" CASCADE;
CREATE TABLE public."PV"(
	"PVID" smallint NOT NULL GENERATED ALWAYS AS IDENTITY ,
	"VALIDITY" tsrange,
	"EMPID_EMPLOYEE" bigint NOT NULL,
	CONSTRAINT "PV_pk" PRIMARY KEY ("PVID")

);
-- ddl-end --
ALTER TABLE public."PV" OWNER TO pichackator;
-- ddl-end --

-- object: "EMPLOYEE_fk" | type: CONSTRAINT --
-- ALTER TABLE public."PV" DROP CONSTRAINT IF EXISTS "EMPLOYEE_fk" CASCADE;
ALTER TABLE public."PV" ADD CONSTRAINT "EMPLOYEE_fk" FOREIGN KEY ("EMPID_EMPLOYEE")
REFERENCES public."EMPLOYEE" ("EMPID") MATCH FULL
ON DELETE RESTRICT ON UPDATE CASCADE;
-- ddl-end --

-- object: "PV_fk" | type: CONSTRAINT --
-- ALTER TABLE public."TIMETABLE" DROP CONSTRAINT IF EXISTS "PV_fk" CASCADE;
ALTER TABLE public."TIMETABLE" ADD CONSTRAINT "PV_fk" FOREIGN KEY ("PVID_PV")
REFERENCES public."PV" ("PVID") MATCH FULL
ON DELETE RESTRICT ON UPDATE CASCADE;
-- ddl-end --

-- object: "PV_fk" | type: CONSTRAINT --
-- ALTER TABLE public."PRESENCE" DROP CONSTRAINT IF EXISTS "PV_fk" CASCADE;
ALTER TABLE public."PRESENCE" ADD CONSTRAINT "PV_fk" FOREIGN KEY ("PVID_PV")
REFERENCES public."PV" ("PVID") MATCH FULL
ON DELETE RESTRICT ON UPDATE CASCADE;
-- ddl-end --


