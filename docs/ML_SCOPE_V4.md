# ML feature scope — honest demonstration boundaries

Challenge requirements: text/voice/photo intake, category classification, urgency estimation, responsible desk recommendation, target-time estimation, and aggregates for decision makers. This prototype deliberately does not spend 24 hours fine-tuning multiple unrelated ML models without labeled government records.

| Feature | Code today | Data availability / next genuine ML stage |
|---|---|---|
| Category classification | `backend/app/ai.py` deterministic keyword scoring | Train/benchmark on verified public Indian grievance narratives with suitable category labels, if download/licensing is confirmed |
| Responsible desk | Category → illustrative mapping in `backend/app/data.py` | Requires verified official departmental/jurisdiction map; public NYC labels are not UP ground truth |
| Urgency scoring | Keywords, safety flags and priority rule | Needs labeled severity/safety data and human validation. Safety-sensitive cases always require review |
| Resolution ETA | Category heuristic `sla_hours` adjusted by priority | Actual UP prediction needs true complaint creation/closure dates. NYC 311 can test the *method* but not UP performance |
| Similar complaints | `SequenceMatcher` within same category and district | Could replace with a multilingual embedding model after a precision/recall benchmark |
| Trends/backlogs | SQLite aggregations of synthetic date/status fields | Real historical 311 records support methodology demonstrations, not UP outcome claims |
| Speech | Browser Web Speech API (Hindi/English India) | No local ASR model; Awadhi quality unknown and may require internet/network service |
| Photos | Secure upload, EXIF removal and filenames-only mock hint | No computer-vision model or pixel interpretation; reliable photo classification requires real labeled civic images |

No paid keys or private government endpoints are needed to run the demo; there are **zero external model APIs** in the backend.
