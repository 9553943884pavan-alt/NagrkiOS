# Real-world extension roadmap (post-prototype)

The current ZIP intentionally solves the **app/workflow engineering** portion; its ML features are simulated.

## Most valuable next steps

1. **Choose an actually accessible labeled dataset.** Verify download terms and whether descriptions, categories, timestamps, departments, and resolution events exist. Do not assume datasets from other jurisdictions provide valid UP routing labels.
2. **Create a canonical grievance taxonomy** and a separately versioned UP-department mapping. Keep a fallback `Human triage required` for low-confidence predictions.
3. **Train category/routing baselines** such as TF-IDF + logistic regression; evaluate macro F1 and per-category confusion before using transformers.
4. **Add robust text handling:** native Hindi, code-mixed Hinglish, optional Awadhi tests, translation fallback, and a documented error budget for transcription.
5. **Replace ETA mock values** only after collecting complaint creation and closed/resolved timestamps from the same operational context; report MAE and interval coverage.
6. **Add a real vision adapter** to describe unsafe works / unfinished buildings, gated behind citizen permission. Validate visual-grounding accuracy; never claim that filename parsing is image understanding.
7. **Add a human-reviewed routing queue** with explicit override and auditable reason codes, monitoring for misrouted or critical cases.
8. **Measure outcomes:** balanced accuracy, macro F1, unsafe escalation misses, routing acceptance rate, median time-to-first-action, backlog by desk, and longitudinal drift.
9. **Strengthen security**: real user accounts, data protection assessment, retention, accessible forms, auditing, encryption, role-scoped files, and incident response.
10. **Demonstrate three stages:** text issue → reviewed route → operational trend; supplement with a real dataset audit and a clearly labeled LLM-as-a-Judge experiment if time permits.

Avoid claiming integration with Jansunwai, CM Helpline, or genuine real-time government workloads until you have explicit permission and live data access.
