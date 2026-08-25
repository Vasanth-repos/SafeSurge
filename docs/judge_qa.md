# Judge Q&A Prep Guide

Prepared answers for common technical questions and challenges from competition judges:

---

### Q1: "Is this real-world validated?"
> **Answer:** "No. This prototype is validated through controlled synthetic scenarios, physical sensor fault-injection tests, and mass conservation checks. Field validation against historical flood observations is a required next phase."

---

### Q2: "Why SCS-CN?"
> **Answer:** "We needed a computationally lightweight runoff approximation for the MVP. We're using cumulative rainfall with incremental runoff rather than resetting the event model at every timestep. We explicitly treat this as a prototype approximation rather than a calibrated operational hydrological model."

---

### Q3: "Does D8 calculate flooding?"
> **Answer:** "No. D8 only determines the topographic flow direction. The time evolution comes from our cell-storage balance and routing model."

---

### Q4: "Can you really detect a blockage?"
> **Answer:** "We don't claim confirmed blockage detection. We identify possible drainage-capacity anomalies from abnormal water-level behavior and model disagreement."

---

### Q5: "What if the sensor fails?"
> **Answer:** "The model continues in degraded mode. The sensor is marked offline, its stale observation isn't fused, and forecast confidence decreases."

---

### Q6: "Where does your live radar data come from?"
> **Answer:** "The hackathon prototype operates in replay mode using a standardized rainfall-grid interface. Live meteorological integration is an external deployment dependency."
