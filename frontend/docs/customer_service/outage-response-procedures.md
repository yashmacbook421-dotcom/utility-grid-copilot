# Outage Response Procedures

## Trigger
An outage is confirmed when SCADA/AMI reports loss of voltage across 3 or more meters in a
contiguous area, or a customer-reported outage is corroborated by a second independent report
within 15 minutes.

## Classification
- Momentary (under 5 minutes): no crew dispatch, logged only.
- Sustained (5 minutes or more): crew dispatched, an outage-system case is opened, and an
  estimated restoration time (ERT) is published within 30 minutes of confirmation.
- Major event (more than 500 customers, or 3+ sustained outages in one service area at once):
  the Emergency Operations Center is activated per Emergency Response Procedures.

## Customer communication
Publish outage status (area, cause if known, crew status, ERT) to the customer-facing outage
map and IVR within 30 minutes of confirmation. Update the ERT whenever it changes by more than
30 minutes from what was last published.

## Restoration estimate rules
An ERT is only published once a crew has been dispatched and assessed the cause, or a standard
restoration-time table applies: equipment failure, 2-4 hours; vehicle or pole damage, 3-5 hours;
tree contact, 2-3 hours; scheduled maintenance, as scheduled. Representatives must never quote a
restoration time that isn't currently in the outage system.

## Escalation
If two reports for the same area show conflicting status — for example, one shows "resolved"
and a newer one shows "active" — escalate to Grid Operations before communicating any
restoration estimate to the customer.
