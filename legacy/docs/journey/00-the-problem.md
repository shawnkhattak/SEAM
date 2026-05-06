# The Problem OceansX V2 Solves

---

## TL;DR

Singapore is one of the world's two or three busiest ports. Knowing which vessels are in its waters is easy — the data is public. Knowing which of those vessels are sanctioned, shadow-fleet flagged, or carrying a history of port inspection failures is hard. OceansX V2 solves the second problem.

---

## The Singapore Maritime Context

The Port of Singapore handles more than 140,000 vessel calls per year. It sits at the junction of the Strait of Malacca and the South China Sea — the funnel through which roughly 40% of global seaborne trade passes. On any given day, dozens of vessels are anchored in the Singapore Strait, the Eastern Anchorage, or the Western Outer Port Limit, waiting for berths, changing cargo, refueling, or taking on crew.

This throughput makes Singapore an unavoidable waypoint — not just for legitimate commercial shipping, but for vessels operating in ways that international sanctions are designed to prevent. Shadow fleet tankers carrying Russian oil. Vessels flagged by multiple Port State Control authorities for safety deficiencies. Companies with layers of anonymous shell ownership connected to sanctioned entities.

The data to identify these vessels exists. It is public, it is regularly updated, and it is freely available for non-commercial use. What does not exist, out of the box, is a dashboard that pulls these sources together, matches them against live vessel positions in Singapore waters, and surfaces actionable intelligence in one place.

---

## What V1 Did Well

OceansX V1 was a live vessel tracker for Singapore waters built on a SQLite database (a lightweight, file-based database) and a simple FastAPI backend. It consumed the MPA (Maritime and Port Authority of Singapore) OceansX API, displayed real-time vessel positions on a Leaflet map, and showed basic vessel particulars — name, flag, type, speed, heading — in a detail panel.

V1 proved the core data pipeline: the MPA API is reliable, vessel positions update frequently, and a React + Leaflet frontend renders a Singapore-area maritime map cleanly. It established the foundation that V2 builds on.

---

## What V1 Couldn't Do

V1 had no answer to any compliance or intelligence question:

- **Is this vessel sanctioned?** No sanctions data, no matching pipeline, no answer.
- **Is this vessel part of the shadow fleet?** No shadow fleet data at all.
- **Does this vessel have a detention history?** No Port State Control (PSC) records — no Tokyo MoU, no Paris MoU.
- **Who actually owns this vessel?** No organizational graph; only the name on the registration.
- **What is the news saying about this vessel or its owner?** No news integration.
- **How congested is the Eastern Anchorage right now?** No anchorage dwell tracking.
- **What is the overall risk profile of this vessel?** No risk scoring.

V1 also had a database architecture that could not grow with the feature set. SQLite does not handle multiple concurrent writers (three separate processes write to the V2 database simultaneously), has no geospatial index (needed to determine which terminal a vessel is in), and has no time-series compression (needed to store a year of position history efficiently). V2 could not be built by extending V1 — it required a greenfield rewrite on a new foundation.

---

## Why This Matters

Maritime compliance is a multi-billion-dollar professional services market. Port agents, ship managers, commodity traders, and financial institutions all need answers to the questions V1 could not answer — and they need those answers in the context of live, Singapore-specific vessel visibility.

OceansX V2 does not replace enterprise-grade compliance platforms (which cost tens of thousands of dollars per year and carry legal indemnification). It demonstrates something different: that an individual developer, with thoughtful system design and publicly available free data sources, can build a meaningful compliance intelligence layer over live maritime positioning data — and document the entire process openly.

The combination of live vessel positioning, sanctions screening, shadow fleet detection, port inspection history, entity-aware news, and risk scoring in a single, purpose-built Singapore dashboard is the core demonstration. The architecture choices — which database, which matching rules, how to handle autonomous AI agents safely — are the engineering story behind it.

For a recruiter or hiring manager reading this: the project is not a tutorial exercise. It addresses a real domain problem, makes defensible architectural choices, and documents the reasoning for each one. The code, the decision records, and this journal are all part of what is being built.
