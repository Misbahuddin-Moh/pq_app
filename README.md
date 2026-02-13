##Enterprise Harmonic Compliance Screening Dashboard

**Frontend and API layer for pq-engine.**

------------------------------------------------------------------------

## Overview

pq-app provides a structured web interface and REST API wrapper around
the pq-engine harmonic analysis core.

It enables:

-   Parameterized harmonic screening
-   Risk visualization
-   Run-based artifact storage
-   ZIP export of engineering reports
-   Deterministic compliance evaluation

------------------------------------------------------------------------

## System Architecture

                   ┌────────────────────────┐
                   │       End User         │
                   │  (Electrical Engineer) │
                   └────────────┬───────────┘
                                │
                                ▼
                   ┌────────────────────────┐
                   │  React / Vite UI       │
                   │  (Dashboard)           │
                   └────────────┬───────────┘
                                │
                                ▼
                   ┌────────────────────────┐
                   │  FastAPI Backend       │
                   │  Run Orchestration     │
                   └────────────┬───────────┘
                                │
                                ▼
                   ┌────────────────────────┐
                   │       pq-engine        │
                   │  Harmonic Core         │
                   └────────────┬───────────┘
                                │
                                ▼
                   ┌────────────────────────┐
                   │ Run-Based Artifact     │
                   │ Storage (Per UUID)     │
                   └────────────┬───────────┘
                                │
                                ▼
                   ┌────────────────────────┐
                   │ Downloadable ZIP       │
                   │ JSON + Engineering     │
                   │ Outputs                │
                   └────────────────────────┘

------------------------------------------------------------------------

## API Endpoints

### Create Run

POST /api/runs

Returns: - run_id - risk summary

------------------------------------------------------------------------

### Get Run Results

GET /api/runs/{run_id}

Returns: - THDi - THDv - Risk classification - Harmonic data - Metadata

------------------------------------------------------------------------

### Download Artifacts

GET /api/runs/{run_id}/download.zip

Returns: - JSON results - Harmonic breakdown - Engineering summary

------------------------------------------------------------------------

## IEEE-519 Compliance Logic

Evaluation considers:

-   Voltage distortion at PCC
-   Current distortion relative to Ssc / IL ratio
-   Grid strength sensitivity

Risk categories:

-   PASS
-   LOW
-   MEDIUM
-   HIGH
-   FAIL

------------------------------------------------------------------------

## SaaS Roadmap

Phase 1: - Deterministic screening - Artifact export

Phase 2: - Multi-site portfolio analysis - Mitigation simulation

Phase 3: - Enterprise subscription model - Vendor harmonic database -
Utility submission toolkit

------------------------------------------------------------------------

## Version

1.0.0 -- Live Deployment

------------------------------------------------------------------------

## License

MIT License
