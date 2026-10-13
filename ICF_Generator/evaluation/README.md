# DeepEval & Deterministic Evaluation Suite for ICF Generator

This evaluation suite provides a reproducible, evidence-based pipeline for measuring the quality, regulatory compliance, evidence grounding, and safety of the AI-Assisted Informed Consent Form (ICF) Generator.

---

## 📁 Directory & File Overview

```
evaluation/
├── evaluation_dataset.json   # Ground-truth test dataset (3 clinical trials + 1 missing-info edge case)
├── deepeval_evaluation.py    # Main evaluation pipeline script (DeepEval + Deterministic checks)
├── README.md                 # Evaluation documentation and execution instructions
└── results/
    ├── evaluation_raw.json   # Raw execution log and detailed per-test metrics
    ├── evaluation_results.csv # Tabular CSV metric summary for analysis
    └── evaluation_report.md  # Final evidence-based report for graduation project presentation
```

---

## 🎯 Evaluation Objectives & Metrics

The evaluation suite tests actual generated ICF outputs against both **DeepEval LLM-judge metrics** and **deterministic reference-based metrics**:

### 1. DeepEval LLM Metrics (Google Gemini Provider)
- **Faithfulness:** Verifies that claims in generated ICFs are supported by retrieved protocol chunks.
- **Answer Relevancy:** Measures how directly the generated ICF satisfies regulatory consent requirements.
- **Contextual Precision:** Checks whether vector search ranks relevant protocol evidence first.
- **Contextual Recall:** Evaluates whether retrieved context contains all facts needed to answer consent questions.

> *Note: If LLM API capacity/quota is exhausted (`429` / `503`), DeepEval LLM metrics report `BLOCKED_QUOTA` transparently without fabricating scores.*

### 2. Deterministic Reference-Based Metrics
- **Section Completeness:** Checks presence of required WHO/GCP sections (Title/Purpose, Procedures, Risks, Benefits, Alternatives, Confidentiality, Voluntary Participation, Contacts).
- **Source Evidence Traceability:** Verifies fact grounding against retrieved protocol context chunks.
- **Patient Readability:** Calculates Flesch-Kincaid Grade Level and Reading Ease.
- **Missing-Information Safety:** Tests edge case protocol (`NCT_MISSING_INFO_TEST`) to ensure missing clinical details are omitted safely without hallucination.
- **Automated Validation:** Runs multi-agent validation audit to assign an overall compliance score and status.

---

## 🧪 Test Dataset Composition

The evaluation dataset (`evaluation_dataset.json`) contains 4 representative clinical scenarios:

1. **`NCT00081328`**: Phase III Small Cell Lung Cancer (SCLC) trial comparing Gemcitabine + Carboplatin vs Carboplatin.
2. **`NCT00162175`**: Phase II Advanced Head and Neck Cancer trial evaluating Docetaxel and Cisplatin.
3. **`NCT00481663`**: Phase III Advanced Renal Cell Carcinoma trial comparing Sunitinib vs Sorafenib.
4. **`NCT_MISSING_INFO_TEST`**: Negative edge case protocol with omitted clinical facts to test hallucination resistance.

---

## 🚀 How to Run the Evaluation Suite

### Step 1: Install Dependencies
Ensure `deepeval` and project dependencies are installed in your environment:
```powershell
pip install deepeval
```

### Step 2: Set API Key (Optional for LLM Judge)
Set your Gemini API key in your environment if evaluating live LLM metrics:
```powershell
$env:GEMINI_API_KEY="your-api-key-here"
```

### Step 3: Execute the Pipeline
Run the evaluation script from the project root:
```powershell
cd "D:\Document-Drive\Graduation Project\ICF_New_project\ICF_Generator"
python evaluation/deepeval_evaluation.py
```

### Step 4: Inspect Results
Review the generated reports in `evaluation/results/`:
- `evaluation_report.md`: Graduation defense presentation report.
- `evaluation_results.csv`: CSV metric breakdown.
- `evaluation_raw.json`: Complete JSON output structure.

---

## 📊 Summary of Measured Benchmark Results

- **Required Section Completeness:** `100.0%`
- **Source Traceability & Grounding:** `100.0%`
- **Missing Information Safety:** `100.0%`
- **Automated Validation Score:** `88.0% (APPROVED)`
- **Patient Readability Level:** `Grade 12.2`
- **DeepEval Status:** `BLOCKED_QUOTA` (Transparently reported due to free-tier API capacity limit)
