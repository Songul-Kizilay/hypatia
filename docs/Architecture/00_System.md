# System Overview

## Status

Draft — no application architecture has been selected yet.

## Intent

Hypatia will be designed as a local-first, modular system. Each capability should have a clearly documented responsibility, input/output boundary, and permission model.

## Design questions

- Which capabilities must work fully offline?
- What data may leave the local device, and only with what consent?
- How do modules request actions without bypassing user control?
- What is the minimum viable core for the first release?
