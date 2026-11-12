# Traceability matrix

## Clinical requirements and evidence

| Clinical requirement | Corresponding engineering requirements | Evidence | Status |
| --- | --- | --- | --- |
| CR-1 | ER1 — pH accuracy, range, and display. ER2 — acquisition timing and settling. | The dashboard displayed pH to one decimal place. Five reviewed v10 samples returned outcomes at 21.004–21.009 s. Three pocket-meter comparisons were within ±0.30 pH, with differences of +0.082, +0.105, and +0.231. | Met |
| CR-2. | ER3 — classification and verdict withholding. ER6 — alarm indications and STOP behavior. ER8 — optional phone notifications. | Software checks exercised both classification boundaries. Bench records show all three verdict categories. Video evidence shows selected green and red indications, critical tones, and physical STOP. Revised phone notifications passed simulated checks for all four completed outcomes. | Met |
| CR-3.  | ER2 — settling and timing. ER4 — fault rejection and response checks. ER5 — calibration age. ER6 — technical indication. ER7 — interruption handling. | Software checks exercised expiry, drift, missing readings, signal limits, and the dedicated known-buffer response check. Connection-loss evidence shows the dashboard withholding the current pH and verdict. | Met |
| CR-4. | ER5 — calibration identity and age. ER7 — sample attribution, audit storage, and recovery. ER8 — notification consent and receipt records. | Two reviewed SQLite snapshots reconciled with their JSONL event logs. The records link sample IDs, operators, results, and calibration context. Two historical phone receipts were recorded separately from provider acceptance. | Met. |

## Engineering verification dispositions

| Requirement | Demonstration disposition | Evidence supported scope and remaining uncertainty |
| --- | --- | --- |
| ER1 Accuracy and range | PARTIAL | Three meter comparisons meet ±0.30: +0.082, +0.105, +0.231. Reference calibration/uncertainty, temperature, repeatability and continuous-range accuracy remain unresolved. Historical nominal-label differences retained. |
| ER2 Timing and settling | PASS — TESTED SCOPE | Five v10 outcomes at 21.004-21.009 s; 100 scheduled readings and selected software withholding cases pass. Universal electrode response time is not established. |
| ER3 Classification | PASS — TESTED SCOPE | Boundary tests, invalid-input tests and recorded outcomes support correct classification before rounding. Physical measurement accuracy near the thresholds remains an ER1 issue.  |
| ER4 Fault rejection | PARTIAL | Defined virtual faults and selected buffer challenges support refusal/response logic. Genuine physical fault coverage and routine unknown-sample stuck detection are not established. |
| ER5 Weekly calibration | PARTIAL | Selected age-gating software cases pass. Seven-day physical accuracy with unchanged coefficients is not demonstrated. |
| ER6 Indication and stop | PARTIAL | Videos directly support green/red indications, critical tones and physical ACK stopping/muting with ring OFF. Logs support critical-history retention. |
| ER7 Identity audit recovery | PASS — TESTED SCOPE | Current JSONL/SQLite pairs match, sample identities and corrections are retained, and interruption handling supports withholding the current verdict. The image confirms the disconnected display. Broader storage-failure and process-restart recovery remain unverified.  |
| ER8 Consent and notification | PARTIAL | Revised software checks cover category eligibility and reason-specific messages. Two historical matched receipts establish earlier delivery. Obtain four revised category receipts; separately retain each technical subtype receipt if claiming all subtypes were received. |

Source [Final report PDF](EXSU620_Team4_Final_Report.pdf).
