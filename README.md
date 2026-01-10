# README

## Project Goal
- Provide an automated plan execution and verification framework to validate tasks and policies via repeatable tests.

## Usage
- Run tests: `python -m pytest -q`

## Calculator behavior
- `src/calc.py` exposes `add(a, b)` that accepts ints or floats and returns their sum.
- Providing a string (or any non-numeric) argument raises `TypeError` because `add` strictly rejects non-numeric inputs.
