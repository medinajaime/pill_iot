---
name: Hero Smart Pill Dispenser — Project Context
description: Full context of the pill detection system being built for a Taiwan-focused IoT smart pill dispenser
type: project
---

Smart IoT pill dispenser for Taiwan's elderly population. School project (Jaime Medina + Marcus Canul).

**Core flow:**
1. User scans paper prescription or NHI QR code in Flutter app
2. App OCRs/parses prescription → sends medication list (with NHI codes, color, shape) to Pi over BLE
3. User physically loads pills one medication type at a time (no app guidance required)
4. Pi camera images each pill in optical chamber → identifies which prescription medication it is
5. Routes pill to correct carousel slot
6. Pills dispensed automatically on schedule, or on demand

**Why:** Taiwan becoming super-aged society (20%+ over 65 by 2025). Reduces medication errors and caregiver burden.

**Detection approach:**
- Open identification against ≤10 prescription medications (not global database)
- MobileNetV2 fine-tuned on ePillID public dataset → TFLite INT8 for Pi 4
- Metric learning: embedding-based matching (cosine similarity), no retraining when new pills added
- Auto-registration: first 3-5 pills of each type captured automatically; NHI color/shape used as prior
- Three outcomes: MATCH (auto-route) / UNSURE (hold, notify app) / NO_MATCH (hold, alert)
- Confirmation button on app/dispenser for UNSURE cases — shows pill photo to user

**Three confidence tiers:**
- MATCH: confidence ≥ high_threshold → route silently
- UNSURE: between thresholds → hold pill, send alert + image to app, wait for YES/NO
- NO_MATCH: confidence < low_threshold → hold, alert (wrong pill)

**Hardware (Pi 4):** Pi Camera v2 at 45° tilt, NeoPixel LED ring, NEMA17 carousel, SG90 trapdoor servo, HX711 load cell, TCST2103 home sensor

**Files to build:**
- capture.py — Pi Camera v2 + NeoPixel (done)
- preprocess.py — perspective correction + segmentation + feature extraction (done, needs feature update)
- database.py — prescription-driven profile storage
- model.py — TFLite wrapper + cosine similarity matching
- train.py — fine-tune MobileNetV2 on ePillID, export TFLite INT8
- pipeline.py — full state machine orchestration
- ble_server.py — BLE peripheral (bless) + HTTP fallback (Flask)

**Why:** Taiwan becoming super-aged society (20%+ over 65 by 2025). Reduces medication errors and caregiver burden.

**Phase 2:** Add Taiwan NHI-specific pill images via few-shot fine-tuning.
