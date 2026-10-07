-- Runs once, the first time the PostgreSQL volume is created (docker-entrypoint-initdb.d).
-- Demo "company database" for the Data Analyst agent. All figures are fictional.

CREATE SCHEMA demo;

CREATE TABLE demo.product_metrics (
    quarter       text          NOT NULL,   -- e.g. 2025-Q2
    product       text          NOT NULL,
    revenue_usd   numeric(14,2) NOT NULL,
    active_users  integer       NOT NULL,
    churn_rate    numeric(5,2)  NOT NULL,   -- percent per quarter
    nps           integer       NOT NULL,
    PRIMARY KEY (quarter, product)
);

INSERT INTO demo.product_metrics VALUES
  ('2024-Q3', 'Atlas',   4200000, 51000, 3.10, 41), ('2024-Q4', 'Atlas',   4350000, 52400, 3.00, 42),
  ('2025-Q1', 'Atlas',   4480000, 53100, 2.90, 43), ('2025-Q2', 'Atlas',   4610000, 54000, 2.80, 44),
  ('2024-Q3', 'Beacon',  1100000, 12000, 5.20, 31), ('2024-Q4', 'Beacon',  1450000, 15800, 4.90, 34),
  ('2025-Q1', 'Beacon',  1900000, 20500, 4.60, 36), ('2025-Q2', 'Beacon',  2480000, 27200, 4.10, 39),
  ('2024-Q3', 'Compass', 2300000, 30500, 3.80, 37), ('2024-Q4', 'Compass', 2290000, 30100, 4.00, 36),
  ('2025-Q1', 'Compass', 2250000, 29400, 4.30, 35), ('2025-Q2', 'Compass', 2180000, 28300, 4.70, 33);

CREATE TABLE demo.support_tickets (
    quarter                text    NOT NULL,
    product                text    NOT NULL,
    tickets                integer NOT NULL,
    avg_resolution_hours   numeric(5,1) NOT NULL,
    PRIMARY KEY (quarter, product)
);

INSERT INTO demo.support_tickets VALUES
  ('2024-Q3', 'Atlas', 1850, 6.2), ('2024-Q4', 'Atlas', 1790, 6.0), ('2025-Q1', 'Atlas', 1760, 5.8), ('2025-Q2', 'Atlas', 1700, 5.5),
  ('2024-Q3', 'Beacon', 620, 9.5), ('2024-Q4', 'Beacon', 780, 8.9), ('2025-Q1', 'Beacon', 1010, 8.4), ('2025-Q2', 'Beacon', 1320, 7.8),
  ('2024-Q3', 'Compass', 940, 7.1), ('2024-Q4', 'Compass', 980, 7.4), ('2025-Q1', 'Compass', 1050, 8.0), ('2025-Q2', 'Compass', 1140, 8.6);

-- Least-privilege role used by the Data Analyst agent: read-only, demo schema only.
CREATE ROLE analyst_ro LOGIN PASSWORD 'analyst_ro';
ALTER ROLE analyst_ro SET default_transaction_read_only = on;
ALTER ROLE analyst_ro SET search_path = demo;
GRANT USAGE ON SCHEMA demo TO analyst_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA demo TO analyst_ro;
