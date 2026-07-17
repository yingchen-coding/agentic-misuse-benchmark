# Trusted Monitoring Prompt-Laundering Probe

Cases: 26

| View | Accuracy | Block recall | Allow recall |
|---|---:|---:|---:|
| raw | 20/26 = 0.769 [0.579, 0.890] | 6/12 = 0.500 [0.254, 0.746] | 14/14 = 1.000 [0.785, 1.000] |
| laundered | 19/26 = 0.731 [0.539, 0.863] | 5/12 = 0.417 [0.193, 0.680] | 14/14 = 1.000 [0.785, 1.000] |

Intervals are Wilson 95% CIs over packet items.

Raw/laundered disagreement rate: 1/26 = 0.038 [0.007, 0.189]

Interpretation: the weak monitor preserves allowed work but misses many block cases. The simple laundering view does not improve recall and slightly reduces block recall.
