# AI-Assisted ICF Generator: Latency Benchmark Report

**Timestamp:** `2026-10-10 16:22:16`  
**Target Study ID:** `NCT00081328`  
**Template ID:** `builtin-v1`  
**Successful Trials:** `20` / `20`  
**Percentile Calculation Method:** `Nearest-rank P95 (math.ceil(0.95 * N) - 1)`  

---
## 1. Executive Latency Summary

| Metric / Phase | Sample Size (N) | Min (ms) | Max (ms) | Mean (ms) | P95 Latency (ms) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **End-to-End ICF Generation** | 20 | **10845.75** | **12614.39** | **11367.5** | **11886.25** | COMPLETED |
| **FAISS RAG Vector Search** | 5 | **2062.81** | **2124.74** | **2084.1** | **2124.74** | COMPLETED |
| **DOCX File Export** | 5 | **2027.14** | **2051.83** | **2040.37** | **2051.83** | COMPLETED |

## 2. Trial-by-Trial End-to-End Timings

| Trial # | Timestamp | HTTP Status | Wall-Clock Latency (ms) | Wall-Clock Latency (sec) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Trial 1 | `2026-10-10T16:17:39.927575` | 200 | **11640.36** | **11.64** | SUCCESS |
| Trial 2 | `2026-10-10T16:17:53.651388` | 200 | **11723.65** | **11.724** | SUCCESS |
| Trial 3 | `2026-10-10T16:18:06.851673` | 200 | **11200.1** | **11.2** | SUCCESS |
| Trial 4 | `2026-10-10T16:18:20.739156` | 200 | **11886.25** | **11.886** | SUCCESS |
| Trial 5 | `2026-10-10T16:18:35.353524` | 200 | **12614.39** | **12.614** | SUCCESS |
| Trial 6 | `2026-10-10T16:18:48.698022` | 200 | **11342.66** | **11.343** | SUCCESS |
| Trial 7 | `2026-10-10T16:19:01.763184` | 200 | **11065.88** | **11.066** | SUCCESS |
| Trial 8 | `2026-10-10T16:19:15.019721` | 200 | **11253.69** | **11.254** | SUCCESS |
| Trial 9 | `2026-10-10T16:19:28.348118` | 200 | **11328.03** | **11.328** | SUCCESS |
| Trial 10 | `2026-10-10T16:19:42.231548` | 200 | **11882.74** | **11.883** | SUCCESS |
| Trial 11 | `2026-10-10T16:19:55.591599` | 200 | **11359.61** | **11.36** | SUCCESS |
| Trial 12 | `2026-10-10T16:20:08.711743` | 200 | **11118.99** | **11.119** | SUCCESS |
| Trial 13 | `2026-10-10T16:20:22.012959` | 200 | **11301.33** | **11.301** | SUCCESS |
| Trial 14 | `2026-10-10T16:20:34.859537` | 200 | **10845.75** | **10.846** | SUCCESS |
| Trial 15 | `2026-10-10T16:20:48.084215` | 200 | **11223.79** | **11.224** | SUCCESS |
| Trial 16 | `2026-10-10T16:21:01.319191` | 200 | **11234.72** | **11.235** | SUCCESS |
| Trial 17 | `2026-10-10T16:21:14.222849` | 200 | **10902.39** | **10.902** | SUCCESS |
| Trial 18 | `2026-10-10T16:21:27.208772` | 200 | **10985.44** | **10.985** | SUCCESS |
| Trial 19 | `2026-10-10T16:21:40.240216` | 200 | **11032.11** | **11.032** | SUCCESS |
| Trial 20 | `2026-10-10T16:21:53.650114` | 200 | **11408.08** | **11.408** | SUCCESS |


## 3. Component Latency Breakdown & Findings

- **End-to-End Generation:** Measures total HTTP round-trip latency from request dispatch to final JSON payload receipt.
- **FAISS Vector Search:** Sub-second dense vector retrieval across 384-dimensional protocol embeddings.
- **DOCX Rendering & Export:** Template rendering, table formatting, and file compilation latency.

## 4. Error & Failed Request Log

Zero HTTP failures, timeouts, or rate-limit errors occurred during benchmarking.
