# Risk analysis

## D8 Failure modes and mitigation

The following scores are qualitative post-mitigation judgments for the implemented bench design, not measured probabilities. Higher scores indicate greater severity S, occurrence O or difficulty of detection D; RPN = S × O × D. FM07 detection is revised to 2 and its RPN to 20. FM03, FM06 and FM11 retain the team-selected scores. Low detection scores in these rows are assumptions, not demonstrated detection performance. [E01]

| ID and failure | S O D | RPN | Implemented mitigation and remaining evidence |
| --- | --- | --- | --- |
| FM01 Electrode damage or disconnection | 5 1 2 | 10 | Signal gate, technical refusal and dedicated response challenge. Cannot identify every disconnection or physical fault. |
| FM02 USB or communication failure | 4 1 1 | 4 | Image shows blank pH, paused timer and connection-loss message. Host gate/unit tests support withholding. Recovery timing and independent audio absent. |
| FM03 Liquid exposure | 4 2 1 | 8 | Assembled enclosure and external liquid handling visible in video. No ingress or spill test is supplied. |
| FM04 Unstable placement or damage | 3 2 1 | 6 | Printed support and secured assembly are reported. No quantified force, drop or repeatability test. |
| FM05 Invalid or expired calibration | 5 2 1 | 10 | Loaded coefficients and recorded-age gate. Selected software cases pass; reference accuracy and weekly stability remain open. |
| FM06 Undetected drift | 5 1 1 | 5 | First/last mean comparison and settling gate. Defined cases pass; not all physical drift patterns are covered. |
| FM07 Stuck or unresponsive probe | 5 2 2 | 20 | Known-buffer challenge with measured baseline. Routine unknown-sample stuck detection is not established. D = 2 reflects the dedicated check, not automatic detection in routine samples. |
| FM08 Category switching near boundaries | 3 3 1 | 9 | Unrounded classification and frozen completed result. Repeat samples can still fall on opposite sides; physical threshold accuracy is unresolved. |

Scoring anchors for this review: S1 negligible effect, S2 minor disruption, S3 repeat test or workflow delay, S4 lost function or misleading information, S5 potentially consequential incorrect decision. O1 considered unlikely, O2 occasional, O3 plausible recurring, O4 frequent, O5 very frequent; these are judgments without measured rates. D1 readily apparent or expected to be detected, D2 usually detectable with a defined check, D3 detection depends on operator action, D4 difficult to detect, D5 no reliable detection. These anchors clarify interpretation; they do not retroactively validate the retained scores.

Temporary connections, high ADC readings and reference disagreement were encountered during development. Some causes were suspected, but the evidence does not isolate every fault mechanism. The direct sensor-to-ADC path has no documented overvoltage protection. Rejecting a reading after conversion is not electrical protection. No claim that the completed system is safe under every disconnected-probe or wiring condition follows from stable buffer readings.

### D8 Use and environment risks

| ID and failure | S O D | RPN | Implemented mitigation and remaining evidence |
| --- | --- | --- | --- |
| FM09 Premature settling | 5 1 1 | 5 | Range/dwell gate and 21 s outcome. Defined cases pass; no independent universal stabilization time. |
| FM10 Incorrect or incomplete audit | 3 1 1 | 3 | Unique IDs and dual stores. Two current pairs match; one older session-start mismatch and non-atomic writes remain. |
| FM11 Insufficient sample volume | 4 3 1 | 12 | Instructions require tip immersion. No quantified minimum volume or automatic volume detector is verified. |
| FM12 Probe movement | 4 2 1 | 8 | Holder, still measurement and quality checks. Controlled movement tolerance is not measured. |
| FM13 Inadequate rinsing and carry-over | 4 3 3 | 36 | Rinsing and clean liquid handling are required. No controlled rinse versus no-rinse dataset is reconstructed. |
| FM14 ACK fails to stop as intended | 2 1 1 | 2 | Both videos show button/OFF; dedicated ACK clip shows critical audio cessation. Five v10 stops retained. Exact latency and outage behaviour unverified. |
| FM15 Browser or notification failure | 4 2 1 | 8 | Host state checks, audit and receipt confirmation. Dependence on service, internet and subscribed phone remains. |
| FM16 Power interruption or restart | 5 2 1 | 10 | Time resynchronization and fresh-sample gate. Host critical history, consent and pending deliveries are not restored from storage. |

FM13 has the highest retained RPN, but this is not a validated ranking of clinical risk. FM03, FM06 and FM11 retain D = 1 by team decision despite incomplete evidence: no ingress test, only selected drift patterns covered, and no verified automatic volume detection. These detectability assumptions require review before any broader use. Routine unknown-sample stuck detection is not established; FM07 therefore uses D = 2 for the dedicated response-check approach.

The prototype requires a stable surface, adequate immersion, a functioning laptop and a deliberate new-sample action. Probe transfer and rinsing are operator-dependent. The evidence does not demonstrate a minimum 3-5 mL volume, liquid-ingress resistance, cleaning compatibility, sterilization, electrical certification or nurse usability.

The words “safe to feed” and “not gastric” are course demonstration labels. A pH-only bench classification cannot establish actual tube location. A final interface intended for clinical evaluation would require review of wording, alarm presentation and measurement uncertainty. No such evaluation is claimed here.

Source [Team 4 final report](EXSU620_Team4_Final_Report.pdf).
