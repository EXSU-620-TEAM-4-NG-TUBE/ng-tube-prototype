# System diagrams

## Functional architecture

![Functional architecture](diagrams/architecture.png)

## D4 Wiring and control diagrams

![System diagram](diagrams/figure-2.png)

Figure 2. Functional wiring for the documented signal assignments. Grounds are common. The sensor-to-ADC link is shown as documented direct wiring, not as an electrically protected input. Wire colour is not used to infer a pin assignment. [E03, E17]

![System diagram](diagrams/figure-3.png)

Figure 3. Pico sample lifecycle and the separate host critical memory. A completed valid result is held. A technical result withholds a verdict. Physical stop commands OFF; it does not erase the host’s critical history. This explains why our alarm system differs from the course.  [E03, E13]

### D4 Sample to notification sequence

![System diagram](diagrams/figure-4.png)

Figure 4. Routine measurement and notification sequence. The decision time starts when the Pico accepts the sample. The notification branch applies to all four completed outcomes in the revised service. [E03, E13, E23]

The service synchronizes laptop UTC with the Pico. If calibration completion has not been registered, the operator supplies the actual completion time once; that control does not perform a calibration. Each NEW SAMPLE creates a fresh identifier. Repeated requests with the same identifier do not restart the Pico timer.

With consent active, the revised service queues one submission per sample ID for an eligible result at or after 21 seconds. Measuring, idle and manually stopped samples do not send. USB loss clears the active sample and has no phone alert. All four outcomes use ntfy priority 4. The phone worker records provider acceptance or failure. The operator records receipt separately. [E23]

Communication interruption clears the host’s current sample gate. Reconnection does not convert buffered or held data into a valid new measurement. The operator must request another sample. This behaviour does not establish recovery from every power, storage or process failure; the service’s in-memory state is not reconstructed after a fresh process start.

Source [Team 4 final report](EXSU620_Team4_Final_Report.pdf).
