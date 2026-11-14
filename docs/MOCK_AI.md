# What “AI” means in this prototype

**No trained model is downloaded or called.** All predictions are deterministic mock behavior designed to demonstrate the user journey, not accuracy.

- **Category:** case-insensitive keyword matches against metadata in `backend/app/data.py`. Hindi/Devanagari keywords are included for several categories. Matches are scored and the highest category wins. Unknown text is classified as `Other`.
- **Routing:** each category is mapped to one illustrative department. This mapping is **not verified** against real UP administrative desks.
- **Urgency:** severity keywords trigger critical/high; the default is medium/low. Critical cases flag `requires_human_review=true`. Critical urgency is not an emergency response system.
- **Confidence:** a heuristic based on the count of keyword hits. This is **not** statistical model confidence or calibrated probability.
- **Estimated resolution:** category default SLA-like hour values multiplied by priority. These are **invented demo targets**, not empirically learned closure times.
- **Similar-case count:** `difflib.SequenceMatcher` character similarity against recent same-category, same-district stored complaints. It is **not** embedding-based semantic clustering.
- **Trend analysis:** real SQL aggregations on **synthetic** case records; the computation works, but output does not describe current conditions in Uttar Pradesh.
- **Photo input:** the real photo is uploaded and retrievable, but preview classification looks only at a **filename hint**, never the pixels. For example `anganwadi_building.png` can influence mock classification; a generic `IMG_001.png` cannot.
- **Voice input:** the browser's optional Web Speech API creates a transcript which is then processed like text. Browser availability, connectivity, dialect support, and external speech-provider processing vary.
- **LLM-as-a-Judge:** intentionally **not integrated**. You can export case data and attach an evaluator later, but no judge scores or evaluation accuracy should be claimed for this build.

## Suggested testing examples

| Input | Expected illustrative behavior |
| --- | --- |
| “Water pipeline broken, no drinking water for three days” | Water Supply, often high urgency |
| “Exposed live electric wire causing injury” | Electricity, critical, review flag |
| “हमारे गांव में आंगनवाड़ी भवन अधूरा है” | Women & Child Services |
| “The road has deep potholes by school” | Roads & Infrastructure |
| Ambiguous unrelated sentence | Other, low confidence, review flag |

Any real-world claim of routing accuracy requires a labeled, representative validation set and government-approved routing policy.
