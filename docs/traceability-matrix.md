# Traceability matrix

## Clinical to engineering traceability

| Clinical requirement | Engineering requirements | Main evidence |
| --- | --- | --- |
| CR1 | ER1 ER2 | Calibration record, reference checks, timed captures and display code.<br>Partial. Three paired checks met the numerical tolerance. Independent reference documentation and full range remain open. |
| CR2 | ER3 ER6 ER8 | Boundary tests, final results, alarm records and phone receipts.<br>Partial. Tested rules pass. Reconcile one-decimal boundaries and latched red behaviour with the card. Revised phone receipt remains open. |
| CR3 | ER2 ER4 ER5 ER6 ER7 | Defined virtual faults, calibration-age tests, stop and interruption records.<br>Partial. Selected refusals pass. Routine stuck detection and physical fault coverage remain open. |
| CR4 | ER5 ER7 ER8 | Calibration identity, paired stores, sample attribution and consent records.<br>Supported for reviewed runs. Current stores reconcile. Crash recovery and revised notification receipts remain open. |

## Verification dispositions

| Requirement | Demonstration disposition | Evidence supported scope and remaining uncertainty |
| --- | --- | --- |
| ER1 Accuracy and range | Incomplete against full criterion | Three meter comparisons meet ±0.30: +0.082, +0.105, +0.231. Reference calibration/uncertainty, temperature, repeatability and continuous-range accuracy remain unresolved. Historical nominal-label differences retained. |
| ER2 Timing and settling | PASS for reviewed cases  | Five v10 outcomes at 21.004-21.009 s; 100 scheduled readings and selected software withholding cases pass. Universal electrode response time is not established. |
| ER3 Classification | PASS for tested inputs  | Boundary tests, invalid-input tests and recorded outcomes support correct classification before rounding. Physical measurement accuracy near the thresholds remains an ER1 issue.  |
| ER4 Fault rejection | Software cases pass. Physical coverage incomplete. | Defined virtual faults and selected buffer challenges support refusal/response logic. Genuine physical fault coverage and routine unknown-sample stuck detection are not established. |
| ER5 Weekly calibration | Expiry logic tested. Seven-day stability unverified. | Selected age-gating software cases pass. Seven-day physical accuracy with unchanged coefficients is not demonstrated. |
| ER6 Indication and stop | Selected patterns demonstrated. Continuous red latch differs from card. | Videos directly support green/red indications, critical tones and physical ACK stopping/muting with ring OFF. Logs support critical-history retention. |
| ER7 Identity audit recovery | PASS for reviewed current cases  | Current JSONL/SQLite pairs match, sample identities and corrections are retained, and interruption handling supports withholding the current verdict. The image confirms the disconnected display. Broader storage-failure and process-restart recovery remain unverified.  |
| ER8 Consent and notification | Software checks pass. Revised live receipt pending. | Revised software checks cover category eligibility and reason-specific messages. Two historical matched receipts establish earlier delivery. Obtain four revised category receipts; separately retain each technical subtype receipt if claiming all subtypes were received. |

Source [Team 4 final report](EXSU620_Team4_Final_Report.pdf).
