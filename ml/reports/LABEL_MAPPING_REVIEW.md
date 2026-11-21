# Proposed Uttar Pradesh category and department mapping

Research date: 2026-11-20. This is a **review sheet**, not an approved routing policy. The machine-readable proposal is `ml/configs/category_mapping.json`. It mirrors the 11 category names in `backend/app/data.py` and records the app's illustrative department separately from possible real authorities. No application routing logic was changed.

Official sources establish that relevant organizations exist and describe some responsibilities; they do **not** establish an exhaustive, current district-level assignment table for NagrikOS. In particular, [the UP department directory](https://msme1connect.up.gov.in/department-directory) identifies Public Works, Revenue, and Urban Development, while [the UP government service overview](https://information.up.gov.in/admin/UploadDocument/OtherPress/compressed_241020250301228%20Years%20full%20english%20CTB%20for%20Govt%20%281%29.pdf) lists multiple education and welfare departments. The latter makes a single broad category-to-desk rule unreliable.

| App category | Candidate authority and supporting evidence | Required human decision |
| --- | --- | --- |
| Roads & Infrastructure | Public Works for some roads/bridges; [UP district plan](https://jjm.up.gov.in/Content/ngdashboard/pdf/shahjhapur/DGP_-_Shahjahanpur-Final_Draft_20230718.pdf) describes PWD's road role. | Identify road owner, urban/rural jurisdiction, and whether the issue is a streetlight or road asset. |
| Water Supply | [UP Jal Jeevan Mission](https://jjm.up.gov.in/home/About) places rural drinking-water work under Jal Shakti; [UP district plan](https://jjm.up.gov.in/Content/ngdashboard/pdf/shahjhapur/DGP_-_Shahjahanpur-Final_Draft_20230718.pdf) identifies Jal Nigam's water/sewage scheme role. | Identify urban/rural area, network operator, and drinking-water versus sewerage issue. |
| Electricity | [UPPCL consumer services](https://consumer.uppcl.org/wss/other-consumer-service) lists power-failure complaints and area distribution companies. | Identify the distribution service area and whether fault belongs to distribution or transmission. |
| Sanitation & Waste | [UP solid-waste policy](https://invest.up.gov.in/uttar-pradesh-state-solid-waste-management-policy/) assigns solid-waste duties to urban local bodies. | Distinguish waste collection, drains, sewerage, and rural sanitation. |
| Healthcare | [Medical Health & Family Welfare directorate](https://dgmh.up.gov.in/en/about_us) describes the state health-service remit. | Identify facility operator and whether immediate emergency response is needed. |
| Education | [UP government service overview](https://information.up.gov.in/admin/UploadDocument/OtherPress/compressed_241020250301228%20Years%20full%20english%20CTB%20for%20Govt%20%281%29.pdf) lists Basic, Secondary, Higher, and Technical Education separately. | Record institution type and education level. |
| Women & Child Services | [UP child-development release](https://www.information.up.gov.in/admin/UploadDocument/CmPress/compressed_31032026011207PN-CM-Baal%20Vikas%20Seva%20evam%20Pushtahaar%20Department%20Programme-30%20March%2C%202026.pdf) addresses anganwadi and nutrition; [UP Police](https://uppolice.gov.in/article/en/contact-us) identifies separate crime/safety channels. | Separate nutrition/anganwadi from welfare and safety/crime cases. |
| Land & Revenue | [UP Bhulekh](https://upbhulekh.gov.in/) is run by the Board of Revenue for land records. | Distinguish record requests, mutation, registration, and legal disputes. |
| Public Safety | [UP Police contact page](https://uppolice.gov.in/article/en/contact-us) identifies police, fire, and other complaint channels, including emergency 112. | Escalate immediate danger through the appropriate official emergency channel; determine crime/traffic/fire type. |
| Social Benefits | [UP food/civil supplies system](https://smartpds.up.gov.in/) establishes ration's separate agency; [UP government overview](https://uplc.up.gov.in/policy/Department-of-IT-and-Electronics-2025.pdf) lists Social Welfare and Food & Civil Supplies separately. | Identify exact scheme and implementing agency. |
| Other | No reliable category-specific candidate. | Manual triage. |

## Review requested before any operational use

1. Obtain a current, authorized UP district/municipality service-owner matrix, including urban/rural boundaries and escalation channels. Who will own approval and future updates?
2. Confirm whether the app's 11 broad categories should be subdivided (for example road asset owner; sewerage versus water; ration versus pension; basic versus higher education).
3. Define a human-review path for ambiguous, safety-sensitive, and out-of-jurisdiction cases. No automated emergency dispatch should be inferred.
4. Confirm whether external datasets' source labels may be mapped into this taxonomy for **research only**. Each mapping requires an explicit, versioned crosswalk and manual examples. A source-provided label remains separate from any generated category suggestion.

No SLA, urgency, ETA, or ownership facts are inferred from these references. The app's `sla_hours` values and `mock-rules-v1` output remain illustrative.
