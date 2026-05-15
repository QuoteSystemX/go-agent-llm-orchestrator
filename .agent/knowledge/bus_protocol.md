# Antigravity Hive: Context Bus Protocol

## Overview

The Context Bus is a shared state management system used by agents to synchronize their actions and share intermediate results. It is implemented as a set of JSON files in `.agent/bus/`.

## Core Components

- **context.json**: The primary bus file containing an array of objects.
- **metrics/**: Subdirectory for modular metric reports (KI coverage, ROI, etc.).
- **telemetry.json**: Real-time performance and budget tracking.

## Object Schema

Each object on the bus has:

- `id`: Unique identifier.
- `type`: Category (e.g., `requirement`, `telemetry`, `incident`).
- `author`: The agent or script that pushed the object.
- `timestamp`: ISO-8601 UTC time.
- `content`: JSON payload.
- `metadata`: Optional extra data.

## Management

Scripts in `.agent/scripts/context/` manage the bus:

- `bus_manager.py`: Push/Pull/List operations.
- `conflict_resolver.py`: Detects and fixes ID collisions.
- `bus_debugger.py`: Interactive inspection.
