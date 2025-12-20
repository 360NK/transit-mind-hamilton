--
-- PostgreSQL database dump
--

\restrict QjchuOiYPXZS2doxxSaufZWoKNF2W0raPw82p9xzReAFDaetlCHxCmY4so5axVd

-- Dumped from database version 17.6 (Postgres.app)
-- Dumped by pg_dump version 17.6 (Postgres.app)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: live_permits; Type: TABLE; Schema: public; Owner: kashy
--

CREATE TABLE public.live_permits (
    id integer NOT NULL,
    permit_id character varying(100),
    source_layer character varying(50),
    hazard_type character varying(50),
    description text,
    start_time timestamp with time zone,
    end_time timestamp with time zone,
    metadata jsonb,
    geom public.geometry(Geometry,4326)
);


ALTER TABLE public.live_permits OWNER TO kashy;

--
-- Name: live_permits_id_seq; Type: SEQUENCE; Schema: public; Owner: kashy
--

CREATE SEQUENCE public.live_permits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.live_permits_id_seq OWNER TO kashy;

--
-- Name: live_permits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: kashy
--

ALTER SEQUENCE public.live_permits_id_seq OWNED BY public.live_permits.id;


--
-- Name: routes; Type: TABLE; Schema: public; Owner: kashy
--

CREATE TABLE public.routes (
    route_id character varying(50) NOT NULL,
    agency_id character varying(50),
    route_short_name character varying(50),
    route_long_name character varying(255),
    route_desc text,
    route_type integer,
    route_url character varying(255),
    route_color character varying(10),
    route_text_color character varying(10)
);


ALTER TABLE public.routes OWNER TO kashy;

--
-- Name: shape_geoms; Type: TABLE; Schema: public; Owner: kashy
--

CREATE TABLE public.shape_geoms (
    shape_id character varying(50),
    geom public.geometry(Geometry,4326)
);


ALTER TABLE public.shape_geoms OWNER TO kashy;

--
-- Name: shapes; Type: TABLE; Schema: public; Owner: kashy
--

CREATE TABLE public.shapes (
    shape_id character varying(50),
    shape_pt_lat double precision,
    shape_pt_lon double precision,
    shape_pt_sequence integer,
    shape_dist_traveled double precision,
    geom public.geometry(Point,4326)
);


ALTER TABLE public.shapes OWNER TO kashy;

--
-- Name: stop_times; Type: TABLE; Schema: public; Owner: kashy
--

CREATE TABLE public.stop_times (
    trip_id character varying(50),
    arrival_time interval,
    departure_time interval,
    stop_id character varying(50),
    stop_sequence integer,
    stop_headsign character varying(255),
    pickup_type integer,
    drop_off_type integer,
    shape_dist_traveled double precision,
    timepoint integer
);


ALTER TABLE public.stop_times OWNER TO kashy;

--
-- Name: stops; Type: TABLE; Schema: public; Owner: kashy
--

CREATE TABLE public.stops (
    stop_id character varying(50) NOT NULL,
    stop_code character varying(50),
    stop_name character varying(255),
    stop_desc character varying(255),
    stop_lat double precision,
    stop_lon double precision,
    zone_id character varying(50),
    stop_url character varying(255),
    location_type integer,
    parent_station character varying(50),
    stop_timezone character varying(50),
    wheelchair_boarding integer,
    geom public.geometry(Point,4326)
);


ALTER TABLE public.stops OWNER TO kashy;

--
-- Name: trips; Type: TABLE; Schema: public; Owner: kashy
--

CREATE TABLE public.trips (
    trip_headsign character varying(255),
    shape_id character varying(50),
    wheelchair_accessible integer,
    service_id character varying(50),
    route_id character varying(50),
    block_id character varying(50),
    direction_id integer,
    trip_id character varying(50) NOT NULL,
    trip_short_name character varying(50),
    wheelchair_boarding integer,
    bikes_allowed integer
);


ALTER TABLE public.trips OWNER TO kashy;

--
-- Name: vw_capital_projects; Type: VIEW; Schema: public; Owner: kashy
--

CREATE VIEW public.vw_capital_projects AS
 SELECT (((metadata -> 'original_fields'::text) ->> 'globalid'::text))::uuid AS id,
    ((metadata -> 'original_fields'::text) ->> 'GeomaticsJobID'::text) AS job_number,
    ((metadata -> 'original_fields'::text) ->> 'Project_Name'::text) AS project_name,
    ((metadata -> 'original_fields'::text) ->> 'Project_Description'::text) AS description,
    ((metadata -> 'original_fields'::text) ->> 'Status'::text) AS status,
    ((metadata -> 'original_fields'::text) ->> 'Subtype'::text) AS work_type,
    ((metadata -> 'original_fields'::text) ->> 'Client_Department'::text) AS department,
    to_timestamp(((((((metadata -> 'original_fields'::text) ->> 'Date_Submitted'::text))::bigint)::numeric / 1000.0))::double precision) AS date_submitted,
    to_timestamp(((((((metadata -> 'original_fields'::text) ->> 'Date_Requested_Completion'::text))::bigint)::numeric / 1000.0))::double precision) AS estimated_completion,
    geom
   FROM public.live_permits
  WHERE (((source_layer)::text = 'Capital_Projects'::text) AND (((metadata -> 'original_fields'::text) ->> 'GeomaticsJobID'::text) IS NOT NULL));


ALTER VIEW public.vw_capital_projects OWNER TO kashy;

--
-- Name: vw_occupancy_permits; Type: VIEW; Schema: public; Owner: kashy
--

CREATE VIEW public.vw_occupancy_permits AS
 SELECT (((metadata -> 'original_fields'::text) ->> 'globalid'::text))::uuid AS id,
    ((metadata -> 'original_fields'::text) ->> 'Occupancy_Number'::text) AS permit_number,
    ((metadata -> 'original_fields'::text) ->> 'Item_for_Occupancy'::text) AS obstruction_type,
    ((metadata -> 'original_fields'::text) ->> 'Location'::text) AS address,
    ((metadata -> 'original_fields'::text) ->> 'Status'::text) AS status,
    ((metadata -> 'original_fields'::text) ->> 'LRT'::text) AS affects_lrt,
    to_timestamp(((((((metadata -> 'original_fields'::text) ->> 'Start_Date_of_Occupancy'::text))::bigint)::numeric / 1000.0))::double precision) AS start_date,
    to_timestamp(((((((metadata -> 'original_fields'::text) ->> 'End_Date_of_Occupancy'::text))::bigint)::numeric / 1000.0))::double precision) AS end_date,
    geom
   FROM public.live_permits
  WHERE (((source_layer)::text = 'Occupancy'::text) AND (((metadata -> 'original_fields'::text) ->> 'globalid'::text) IS NOT NULL));


ALTER VIEW public.vw_occupancy_permits OWNER TO kashy;

--
-- Name: vw_road_closures; Type: VIEW; Schema: public; Owner: kashy
--

CREATE VIEW public.vw_road_closures AS
 SELECT (((metadata -> 'original_fields'::text) ->> 'globalid'::text))::uuid AS id,
    ((metadata -> 'original_fields'::text) ->> 'Permit_Number'::text) AS permit_number,
    ((metadata -> 'original_fields'::text) ->> 'closure_to_what_street_name'::text) AS road_name,
    ((metadata -> 'original_fields'::text) ->> 'from_what_cross_street'::text) AS from_street,
    ((metadata -> 'original_fields'::text) ->> 'to_what_cross_street'::text) AS to_street,
    ((metadata -> 'original_fields'::text) ->> 'Project_Name'::text) AS title,
    ((metadata -> 'original_fields'::text) ->> 'Description'::text) AS description,
    ((metadata -> 'original_fields'::text) ->> 'Type_of_Use'::text) AS reason,
    ((metadata -> 'original_fields'::text) ->> 'Close_Both_Traffic_Directions'::text) AS closure_type,
    ((metadata -> 'original_fields'::text) ->> 'Status'::text) AS status,
    to_timestamp(((((((metadata -> 'original_fields'::text) ->> 'Start_Date_of_Closure'::text))::bigint)::numeric / 1000.0))::double precision) AS start_date,
    to_timestamp(((((((metadata -> 'original_fields'::text) ->> 'End_Date_of_Closure'::text))::bigint)::numeric / 1000.0))::double precision) AS end_date,
    ((metadata -> 'original_fields'::text) ->> 'Start_Time'::text) AS daily_start_time,
    ((metadata -> 'original_fields'::text) ->> 'End_Time'::text) AS daily_end_time,
    geom
   FROM public.live_permits
  WHERE (((source_layer)::text = 'Closures'::text) AND (((metadata -> 'original_fields'::text) ->> 'globalid'::text) IS NOT NULL));


ALTER VIEW public.vw_road_closures OWNER TO kashy;

--
-- Name: vw_utility_permits; Type: VIEW; Schema: public; Owner: kashy
--

CREATE VIEW public.vw_utility_permits AS
 SELECT (((metadata -> 'original_fields'::text) ->> 'GlobalID'::text))::uuid AS id,
    ((metadata -> 'original_fields'::text) ->> 'MC_Permit_Number'::text) AS permit_number,
    ((metadata -> 'original_fields'::text) ->> 'Road_Cut_Permit_EP'::text) AS road_cut_id,
    ((metadata -> 'original_fields'::text) ->> 'Utility_Company_Name'::text) AS company_name,
    ((metadata -> 'original_fields'::text) ->> 'Project_Name'::text) AS project_name,
    ((metadata -> 'original_fields'::text) ->> 'Status'::text) AS status,
    ((metadata -> 'original_fields'::text) ->> 'Stream_Class'::text) AS impact_level,
    (((metadata -> 'original_fields'::text) ->> 'Underground_Linear_Length_m'::text))::numeric AS length_m,
    to_timestamp(((((((metadata -> 'original_fields'::text) ->> 'Date_Approved'::text))::bigint)::numeric / 1000.0))::double precision) AS date_approved,
    to_timestamp(((((((metadata -> 'original_fields'::text) ->> 'Date_Expired'::text))::bigint)::numeric / 1000.0))::double precision) AS date_expired,
    geom
   FROM public.live_permits
  WHERE (((source_layer)::text = 'Utility_Consent'::text) AND (((metadata -> 'original_fields'::text) ->> 'GlobalID'::text) IS NOT NULL));


ALTER VIEW public.vw_utility_permits OWNER TO kashy;

--
-- Name: vw_all_disruptions; Type: VIEW; Schema: public; Owner: kashy
--

CREATE VIEW public.vw_all_disruptions AS
 SELECT vw_road_closures.id,
    'CLOSURE'::text AS disruption_type,
    vw_road_closures.status,
    (((vw_road_closures.road_name || ' ('::text) || vw_road_closures.closure_type) || ')'::text) AS description,
    vw_road_closures.start_date AS start_time,
    vw_road_closures.end_date AS end_time,
    vw_road_closures.geom
   FROM public.vw_road_closures
UNION ALL
 SELECT vw_capital_projects.id,
    'CONSTRUCTION'::text AS disruption_type,
    vw_capital_projects.status,
    vw_capital_projects.project_name AS description,
    vw_capital_projects.date_submitted AS start_time,
    vw_capital_projects.estimated_completion AS end_time,
    vw_capital_projects.geom
   FROM public.vw_capital_projects
UNION ALL
 SELECT vw_utility_permits.id,
    'UTILITY_WORK'::text AS disruption_type,
    vw_utility_permits.status,
    (((vw_utility_permits.company_name || ' ('::text) || vw_utility_permits.impact_level) || ')'::text) AS description,
    vw_utility_permits.date_approved AS start_time,
    vw_utility_permits.date_expired AS end_time,
    vw_utility_permits.geom
   FROM public.vw_utility_permits
UNION ALL
 SELECT vw_occupancy_permits.id,
    'OCCUPANCY'::text AS disruption_type,
    vw_occupancy_permits.status,
    ((vw_occupancy_permits.obstruction_type || ' at '::text) || vw_occupancy_permits.address) AS description,
    vw_occupancy_permits.start_date AS start_time,
    vw_occupancy_permits.end_date AS end_time,
    vw_occupancy_permits.geom
   FROM public.vw_occupancy_permits;


ALTER VIEW public.vw_all_disruptions OWNER TO kashy;

--
-- Name: live_permits id; Type: DEFAULT; Schema: public; Owner: kashy
--

ALTER TABLE ONLY public.live_permits ALTER COLUMN id SET DEFAULT nextval('public.live_permits_id_seq'::regclass);


--
-- Name: live_permits live_permits_permit_id_key; Type: CONSTRAINT; Schema: public; Owner: kashy
--

ALTER TABLE ONLY public.live_permits
    ADD CONSTRAINT live_permits_permit_id_key UNIQUE (permit_id);


--
-- Name: live_permits live_permits_pkey; Type: CONSTRAINT; Schema: public; Owner: kashy
--

ALTER TABLE ONLY public.live_permits
    ADD CONSTRAINT live_permits_pkey PRIMARY KEY (id);


--
-- Name: routes routes_pkey; Type: CONSTRAINT; Schema: public; Owner: kashy
--

ALTER TABLE ONLY public.routes
    ADD CONSTRAINT routes_pkey PRIMARY KEY (route_id);


--
-- Name: stops stops_pkey; Type: CONSTRAINT; Schema: public; Owner: kashy
--

ALTER TABLE ONLY public.stops
    ADD CONSTRAINT stops_pkey PRIMARY KEY (stop_id);


--
-- Name: trips trips_pkey; Type: CONSTRAINT; Schema: public; Owner: kashy
--

ALTER TABLE ONLY public.trips
    ADD CONSTRAINT trips_pkey PRIMARY KEY (trip_id);


--
-- Name: idx_live_permits_geom; Type: INDEX; Schema: public; Owner: kashy
--

CREATE INDEX idx_live_permits_geom ON public.live_permits USING gist (geom);


--
-- Name: idx_live_permits_time; Type: INDEX; Schema: public; Owner: kashy
--

CREATE INDEX idx_live_permits_time ON public.live_permits USING btree (start_time, end_time);


--
-- Name: idx_shape_geoms_spatial; Type: INDEX; Schema: public; Owner: kashy
--

CREATE INDEX idx_shape_geoms_spatial ON public.shape_geoms USING gist (geom);


--
-- Name: idx_stop_times_stop_id; Type: INDEX; Schema: public; Owner: kashy
--

CREATE INDEX idx_stop_times_stop_id ON public.stop_times USING btree (stop_id);


--
-- Name: idx_stop_times_trip_id; Type: INDEX; Schema: public; Owner: kashy
--

CREATE INDEX idx_stop_times_trip_id ON public.stop_times USING btree (trip_id);


--
-- PostgreSQL database dump complete
--

\unrestrict QjchuOiYPXZS2doxxSaufZWoKNF2W0raPw82p9xzReAFDaetlCHxCmY4so5axVd

