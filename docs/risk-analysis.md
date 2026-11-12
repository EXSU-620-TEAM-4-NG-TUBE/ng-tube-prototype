# Risk analysis

## VIII. Failure modes and mitigation (Deliverable D8)

| ID and failure | S O D | RPN | Implemented mitigation and remaining evidence |
| --- | --- | --- | --- |
| FM01 Electrode damage or disconnection | 5 1 2 | 10 | Signal gate and response challenge; not every physical fault is detectable. |
| FM02 USB or communication failure | 4 1 1 | 4 | Host withholds result on link loss; no independent audio during outage. |
| FM03 Liquid exposure | 4 2 1 | 8 | PLA enclosure and splash guards; ingress resistance not tested. |
| FM04 Unstable placement or damage | 3 2 1 | 6 | Printed holder and secured assembly; no quantified force or drop test. |
| FM05 Invalid or expired calibration | 5 2 1 | 10 | Coefficient and age checks; reference accuracy and weekly stability unresolved. |
| FM06 Undetected drift | 5 1 1 | 5 | First/last mean and settling checks; selected drift patterns only. |
| FM07 Stuck or unresponsive probe | 5 2 2 | 20 | Known-buffer response check. Routine unknown-sample stuck detection is not established. |
| FM08 Category switching near boundaries | 3 3 1 | 9 | Unrounded classification and held result; repeat samples may straddle thresholds. |
| FM09 Premature settling | 5 1 1 | 5 | Range/dwell checks and 21 s decision; universal electrode settling not established. |
| FM10 Incorrect or incomplete audit | 3 1 1 | 3 | Unique IDs and dual storage; non-atomic writes remain. |
| FM11 Insufficient sample volume | 4 3 1 | 12 | Adequate tip immersion instructed; minimum volume and automatic detection unverified. |
| FM12 Probe movement | 4 2 1 | 8 | Holder and still measurement; movement tolerance unmeasured. |
| FM13 Inadequate rinsing and carry-over | 4 3 3 | 36 | Rinsing required; controlled carry-over study absent. |
| FM14 ACK fails to stop as intended | 2 1 1 | 2 | Button/OFF and audio cessation shown; outage behaviour unverified. |
| FM15 Browser or notification failure | 4 2 1 | 8 | Consent, logging and receipt checks; service and internet dependencies remain. |
| FM16 Power interruption or restart | 5 2 1 | 10 | Time sync and fresh-sample gate; alarm history/consent not restored after restart. |

The following scores are qualitative post-mitigation judgments for the implemented bench design, not measured probabilities. Higher scores indicate greater severity S, occurrence O or difficulty of detection D; RPN = S × O × D. [E01]

Scoring anchors for this review: S1 negligible effect, S2 minor disruption, S3 repeat test or workflow delay, S4 lost function or misleading information, S5 potentially consequential incorrect decision. O1 considered unlikely, O2 occasional, O3 plausible recurring, O4 frequent, O5 very frequent; these are judgments without measured rates. D1 readily apparent or expected to be detected, D2 usually detectable with a defined check, D3 detection depends on operator action, D4 difficult to detect, D5 no reliable detection. These anchors clarify interpretation; they do not retroactively validate the retained scores.

The team reports that the unstable readings were resolved by replacing the Pico, rather than changing the cables, and attributes the fault to the original Pico cable connection point. Replacement success is a team observation; the precise contact defect was not independently isolated. The direct sensor-to-ADC path has no documented overvoltage protection, and software signal rejection does not provide electrical protection.

FM13 has the highest retained RPN, but this is not a validated ranking of clinical risk. For FM07, routine unknown-sample stuck detection is not established

The prototype requires a stable surface, adequate immersion, a functioning laptop and a deliberate new-sample action. Probe transfer and rinsing are operator-dependent. The evidence does not demonstrate a minimum 3-5 mL volume, liquid-ingress resistance, cleaning compatibility, sterilization, electrical certification or nurse usability.

The words “safe to feed” and “not gastric” are course demonstration labels. A pH-only bench classification cannot establish actual tube location.

Source [Final report PDF](EXSU620_Team4_Final_Report.pdf).
