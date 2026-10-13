import React, {useEffect, useState} from "react";
import {TemplatePanel} from './TemplatePanel.jsx';
import {API_BASE_URL} from '../config.js';
import {
  Icon,
  Button,
  Badge,
  SectionHeader,
  Field,
  ErrorNotice,
  EmptyState,
  BusyNotice,
  JsonView,
  DataFields,
  Metric,
  TechnicalDetails,
} from "./ui.jsx";

const labelFor = (value) => String(value).replace(/_/g, " ").replace(/^./, (character) => character.toUpperCase());
const scoreLabel = (value) =>
  typeof value === "number" && Number.isFinite(value)
    ? `${value.toFixed(1)}%`
    : "Not returned";

function statusTone(status) {
  const normalized = String(status || "").toUpperCase();
  if (["SUPPORTED", "PASS", "PASSED", "APPROVED", "SUCCESS"].includes(normalized)) return "success";
  if (["FAIL", "FAILED", "ERROR", "CHANGES_REQUESTED"].includes(normalized)) return "error";
  if (["UNCERTAIN", "WARNING", "REQUIRES_REVIEW", "PENDING", "PARTIAL"].includes(normalized)) return "warning";
  return "neutral";
}

function ResultStatus({ status }) {
  return <Badge tone={statusTone(status)}>{status ? labelFor(status) : "Not returned"}</Badge>;
}

function EvidenceReferences({ ids }) {
  if (!Array.isArray(ids) || ids.length === 0) return null;
  return (
    <div className="evidence-references">
      <span className="eyebrow">Source evidence</span>
      <div className="status-line">
        {ids.map((id, index) => <span className="evidence-id mono" key={`${id}-${index}`}>{String(id)}</span>)}
      </div>
    </div>
  );
}

function FactValue({ value }) {
  if (value === null || value === undefined || value === "") return <p className="muted">Not provided in the returned facts.</p>;
  if (Array.isArray(value)) {
    if (!value.length) return <p className="muted">No facts returned in this category.</p>;
    return <div className="result-list">{value.map((item, index) => <FactValue value={item} key={index} />)}</div>;
  }
  if (typeof value !== "object") return <p className="fact-text">{String(value)}</p>;
  if (Object.prototype.hasOwnProperty.call(value, "value") || Object.prototype.hasOwnProperty.call(value, "status")) {
    const extras = Object.fromEntries(Object.entries(value).filter(([key]) => !["value", "status", "notes", "source_evidence_ids"].includes(key)));
    return (
      <div className="evidence-card fact-card">
        <div className="status-line"><ResultStatus status={value.status} /></div>
        <FactValue value={value.value} />
        {value.notes && <p className="muted">{value.notes}</p>}
        <EvidenceReferences ids={value.source_evidence_ids} />
        {Object.keys(extras).length > 0 && <DataFields data={extras} />}
      </div>
    );
  }
  return (
    <div className="result-list">
      {Object.entries(value).map(([key, nested]) => (
        <div className="fact-category" key={key}>
          <h4>{labelFor(key)}</h4>
          <FactValue value={nested} />
        </div>
      ))}
    </div>
  );
}

function RawToggle({ shown, onClick, label, controls }) {
  return (
    <Button variant="ghost" onClick={onClick} aria-expanded={shown} aria-controls={controls}>
      <Icon name="layers" size={15} /> {shown ? "Hide" : "View"} {label}
    </Button>
  );
}

function NextStage({ onNavigate, target, children }) {
  if (!onNavigate) return null;
  return (
    <div className="form-actions next-stage-navigation">
      <Button variant="secondary" onClick={() => onNavigate(target)}>{children}<Icon name="arrow" size={17} /></Button>
    </div>
  );
}

function DocumentAssembly() {
  return (
    <div className="assembling-document" aria-hidden="true">
      <div className="assembly-paper">
        <span className="assembly-mark"><Icon name="document" size={22} /></span>
        <i /><i /><i /><i />
      </div>
      <div className="assembly-section"><i /><i /></div>
      <div className="assembly-section"><i /><i /></div>
    </div>
  );
}

function ICFDocument({ draft }) {
  if (!draft) {
    return <EmptyState icon="document" title="No document returned">The document is not available in the current generation result.</EmptyState>;
  }
  const sections = Array.isArray(draft.sections) ? draft.sections : [];
  const extraFields = Object.fromEntries(Object.entries(draft).filter(([key]) => !["sections", "revision"].includes(key)));
  return (
    <article className="document-preview" aria-label="Patient-Facing Informed Consent Form">
      <div className="document-heading">
        <div className="eyebrow">Patient-Facing Informed Consent Form</div>
        <h3>Informed Consent Form</h3>
        <p className="muted">Draft for human review{draft.revision != null ? ` · Revision ${draft.revision}` : ""}</p>
      </div>
      {sections.length ? sections.map((section, index) => (
        <section className="document-section" key={section.section_id || index}>
          <div className="panel-header">
            <h4><span className="section-number mono">{String(index + 1).padStart(2, "0")}</span> {section.title || labelFor(section.section_id || "Untitled section")}</h4>
            <ResultStatus status={section.status} />
          </div>
          {typeof section.content === "string" ? <p className="document-content">{section.content}</p> : <DataFields data={section.content} />}
          <EvidenceReferences ids={section.source_evidence_ids} />
        </section>
      )) : <p className="muted">The returned draft contains no sections.</p>}
      {Object.keys(extraFields).length > 0 && <TechnicalDetails label="Additional document metadata"><DataFields data={extraFields} /></TechnicalDetails>}
    </article>
  );
}

export function AnalysisPanel({ vm, onNavigate }) {
  const {
    analysisStudyId, setAnalysisStudyId, analysisQuery, setAnalysisQuery,
    analysisTopK, setAnalysisTopK, isAnalyzing, analysisResult, analysisError,
    showRawFactsJson, setShowRawFactsJson, handleAnalyzeProtocol,
  } = vm;
  const categories = analysisResult?.facts ? Object.entries(analysisResult.facts).filter(([key]) => key !== "study_id") : [];
  return (
    <section className="panel agent-workspace" id="analysis" aria-busy={isAnalyzing}>
      <SectionHeader eyebrow="04 / Protocol intelligence" title="Evidence becomes understanding." description="The Protocol Analysis Agent structures retrieved evidence into study facts, with grounding status and source references for each finding." action={<Badge tone={isAnalyzing ? "warning" : "neutral"}>{isAnalyzing ? "Analyzing evidence" : "AI-assisted analysis"}</Badge>} />
      <div className="card">
        <div className="form-grid">
          <Field label="Target study ID" id="analysis-study"><input id="analysis-study" value={analysisStudyId} onChange={(event) => setAnalysisStudyId(event.target.value)} placeholder="e.g. NCT00081328" /></Field>
          <Field label="Evidence context" id="analysis-top-k"><select id="analysis-top-k" value={analysisTopK} onChange={(event) => setAnalysisTopK(Number(event.target.value))}><option value={3}>Top 3 evidence chunks</option><option value={5}>Top 5 evidence chunks (default)</option><option value={10}>Top 10 evidence chunks</option></select></Field>
        </div>
        <Field label="Analysis requirement" id="analysis-query"><input id="analysis-query" value={analysisQuery} onChange={(event) => setAnalysisQuery(event.target.value)} placeholder="What should the agent extract from the protocol?" /></Field>
        <div className="form-actions"><Button onClick={handleAnalyzeProtocol} disabled={isAnalyzing} busy={isAnalyzing}><Icon name="spark" size={17} />{isAnalyzing ? "Analyzing protocol facts…" : "Analyze protocol facts"}</Button><span className="muted">Grounded in retrieved protocol evidence.</span></div>
      </div>
      {isAnalyzing && <BusyNotice>Protocol Analysis Agent is structuring study evidence.</BusyNotice>}
      {analysisError && <ErrorNotice title="Protocol analysis could not finish" message={analysisError} onRetry={isAnalyzing ? undefined : handleAnalyzeProtocol} />}
      {analysisResult ? (
        <div className="result-list">
          <div className="panel-header">
            <div className="status-line"><span className="mono">{analysisResult.study_id}</span><ResultStatus status={analysisResult.analysis_status} />{analysisResult.evidence_used_count != null && <Badge>{analysisResult.evidence_used_count} evidence chunks supplied</Badge>}</div>
            <RawToggle shown={showRawFactsJson} onClick={() => setShowRawFactsJson(!showRawFactsJson)} label="raw facts JSON" controls="facts-json" />
          </div>
          {analysisResult.message && <p className="muted">{analysisResult.message}</p>}
          {showRawFactsJson && <div id="facts-json"><JsonView data={analysisResult} /></div>}
          <div className="two-column facts-grid">{categories.map(([key, value]) => <section className="card fact-category" key={key}><h3>{labelFor(key)}</h3><FactValue value={value} /></section>)}</div>
          {!categories.length && <EmptyState icon="spark" title="No structured facts returned">Inspect the response details or run the analysis again.</EmptyState>}
        </div>
      ) : !isAnalyzing && !analysisError && <EmptyState icon="spark" title="Ready to read the evidence">Run the agent to reveal study objectives, eligibility, procedures, risks and other protocol facts.</EmptyState>}
      <NextStage onNavigate={onNavigate} target="generation">Open ICF generation</NextStage>
    </section>
  );
}

function StepStatusIcon({ status }) {
  const norm = String(status || "").toLowerCase();
  if (norm === "complete" || norm === "completed" || norm === "succeeded") {
    return <span style={{ color: "var(--success-color, #10b981)", fontWeight: "bold", width: "18px", display: "inline-block" }}>✓</span>;
  }
  if (norm === "active" || norm === "running" || norm === "in_progress") {
    return <span style={{ color: "var(--warning-color, #f59e0b)", fontWeight: "bold", width: "18px", display: "inline-block" }}>⟳</span>;
  }
  if (norm === "error" || norm === "failed") {
    return <span style={{ color: "var(--error-color, #ef4444)", fontWeight: "bold", width: "18px", display: "inline-block" }}>✕</span>;
  }
  return <span style={{ color: "var(--muted-color, #9ca3af)", fontWeight: "bold", width: "18px", display: "inline-block" }}>○</span>;
}

export function GenerationPanel({ vm, onNavigate }) {
  const {
    icfStudyId, sourceMode, selectedStudyId, selectedStudyDetail, selectedFile,
    isGeneratingICF, icfResult, icfError,
    showRawIcfJson, setShowRawIcfJson, handleGenerateICF,
    templateState, workflowProgress, stagedTemplateFile, stagedTemplateError,
    setStagedTemplateFile, setStagedTemplateError,
    preferredLength, setPreferredLength, customInstructions, setCustomInstructions,
  } = vm;
  const uploadedSource = sourceMode === 'upload';
  const deferUploadTemplate = uploadedSource && !icfResult;
  const sourceReady = uploadedSource ? Boolean(selectedFile) : Boolean(selectedStudyDetail && selectedStudyDetail.study_id === selectedStudyId);
  const templateBusy = !deferUploadTemplate && (templateState?.busy || !templateState?.selection || Boolean(templateState?.error));
  const draft = icfResult?.icf_draft;
  return (
    <section className="panel generation-panel" id="generate" aria-busy={isGeneratingICF}>
      <SectionHeader eyebrow="02 / Consent generation" title="A patient-facing draft built from evidence." description="Generate the Patient-Facing Informed Consent Form from the selected study or uploaded protocol. Study evidence, validation and document are prepared automatically." action={<Badge>AI-assisted drafting</Badge>} />
      <div className="card">
        <Field label={uploadedSource ? "Protocol source" : "Clinical study"} id="generation-study"><input id="generation-study" readOnly value={uploadedSource ? (selectedFile?.name || 'Select a protocol first') : (selectedStudyId || icfStudyId || 'Select a study first')} /></Field>
      </div>
      {templateState && <TemplatePanel studyId={deferUploadTemplate ? (selectedFile?.name || '') : icfStudyId} state={templateState} generating={isGeneratingICF} deferUpload={deferUploadTemplate} stagedFile={stagedTemplateFile} onStageTemplate={setStagedTemplateFile} onStageError={setStagedTemplateError} />}
      <div className="card generation-preferences-card">
        <h4 style={{ margin: "0 0 12px 0", fontSize: "0.95rem", fontWeight: "600" }}>
          Generation Preferences <span className="muted" style={{ fontWeight: "normal", fontSize: "0.85rem" }}>(Optional)</span>
        </h4>
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <Field label="Preferred Document Length" id="preferred-length" hint="Optional guideline for target document length. Clinical content completeness is always prioritized.">
            <select
              id="preferred-length"
              value={preferredLength || ""}
              disabled={isGeneratingICF}
              onChange={e => setPreferredLength?.(e.target.value)}
            >
              <option value="">Default (Automatic based on evidence)</option>
              <option value="4–6 pages">4–6 pages</option>
              <option value="6–8 pages">6–8 pages</option>
              <option value="8–10 pages">8–10 pages</option>
              <option value="10–12 pages">10–12 pages</option>
            </select>
          </Field>
          <Field label="Additional Generation Instructions" id="custom-instructions" hint="Optional style or presentation preferences (e.g. use simple patient-friendly language, short paragraphs, bullet points). Will not alter clinical facts.">
            <textarea
              id="custom-instructions"
              rows={3}
              disabled={isGeneratingICF}
              placeholder="e.g. Use simple patient-friendly tone, short paragraphs, and bullet points where appropriate..."
              value={customInstructions || ""}
              onChange={e => setCustomInstructions?.(e.target.value)}
            />
          </Field>
        </div>
      </div>
      <div className="card">
        <div className="form-actions"><Button onClick={handleGenerateICF} disabled={isGeneratingICF || !sourceReady || templateBusy || Boolean(stagedTemplateError)} busy={isGeneratingICF}><Icon name="document" size={17} />{isGeneratingICF ? "Preparing Patient-Facing ICF…" : "Generate Patient-Facing Informed Consent Form"}</Button></div>
      </div>
      {(isGeneratingICF || workflowProgress?.steps?.length) && (
        <div className="generation-activity">
          {isGeneratingICF && <DocumentAssembly />}
          {isGeneratingICF && <BusyNotice>{workflowProgress?.current_step || "Starting the protocol-to-consent workflow."}</BusyNotice>}
          <ol className="data-list workflow-progress" aria-label="Workflow progress" aria-live="polite">
            {workflowProgress?.steps?.map(step => {
              const norm = String(step.status || "").toLowerCase();
              const tone = (norm === 'complete' || norm === 'completed' || norm === 'succeeded') ? 'success'
                : (norm === 'active' || norm === 'running' || norm === 'in_progress') ? 'warning'
                : (norm === 'error' || norm === 'failed') ? 'error'
                : 'neutral';
              return (
                <li key={step.id} className={`workflow-step-item step-${norm}`}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <StepStatusIcon status={step.status} />
                    <strong>{step.label}</strong>
                    <Badge tone={tone}>{step.status}</Badge>
                  </div>
                  <div className="muted" style={{ marginLeft: "26px" }}>{step.message}</div>
                </li>
              );
            })}
          </ol>
        </div>
      )}
      {icfError && <ErrorNotice title="ICF generation could not finish" message={icfError} onRetry={isGeneratingICF ? undefined : handleGenerateICF} />}
      {icfResult ? (
        <div className="result-list">
          <div className="panel-header"><div className="status-line"><span className="mono">{icfResult.study_id}</span><ResultStatus status={icfResult.generation_status} /></div><RawToggle shown={showRawIcfJson} onClick={() => setShowRawIcfJson(!showRawIcfJson)} label="raw ICF JSON" controls="icf-json" /></div>
          {icfResult.message && <p className="muted">{icfResult.message}</p>}
          {icfResult.template && <p className="muted">Revision {icfResult.revision} template: <strong>{icfResult.template.filename}</strong></p>}
          {showRawIcfJson && <div id="icf-json"><JsonView data={icfResult} /></div>}
          <ICFDocument draft={draft} />
        </div>
      ) : !isGeneratingICF && !icfError && <EmptyState icon="document" title="Your patient-facing consent draft will appear here">Generated sections retain source references and identify missing or uncertain protocol information.</EmptyState>}
      <NextStage onNavigate={onNavigate} target="review">Open human review</NextStage>
    </section>
  );
}

export function ValidationPanel({ vm, onNavigate }) {
  const {
    validationStudyId, setValidationStudyId, isValidatingICF, validationResult,
    validationError, showRawValidationJson, setShowRawValidationJson, handleValidateICF,
  } = vm;
  const checks = Array.isArray(validationResult?.checks) ? validationResult.checks : [];
  const summaryScores = validationResult ? Object.entries(validationResult).filter(([key, value]) => key.endsWith("_score") && key !== "overall_score" && typeof value === "number") : [];
  return (
    <section className="panel validation-panel" id="validate" aria-busy={isValidatingICF}>
      <SectionHeader eyebrow="06 / Automated validation" title="Inspect the draft. Follow the evidence." description="Review returned findings for groundedness, completeness, missing information, traceability and readability before a human makes the final decision." action={<Badge>Validation Agent</Badge>} />
      <div className="card form-grid">
        <Field label="Target study ID" id="validation-study"><input id="validation-study" value={validationStudyId} onChange={(event) => setValidationStudyId(event.target.value)} placeholder="e.g. NCT00081328" /></Field>
        <div className="form-actions"><Button onClick={handleValidateICF} disabled={isValidatingICF} busy={isValidatingICF}><Icon name="shield" size={17} />{isValidatingICF ? "Validating draft…" : "Run validation agent"}</Button></div>
      </div>
      {isValidatingICF && <BusyNotice>Checking generated content against protocol evidence.</BusyNotice>}
      {validationError && <ErrorNotice title="Validation could not finish" message={validationError} onRetry={isValidatingICF ? undefined : handleValidateICF} />}
      {validationResult ? (
        <div className="result-list">
          <div className="card validation-summary">
            <div className="panel-header"><div><div className="eyebrow">Validation report</div><h3>{validationResult.study_id}</h3></div><ResultStatus status={validationResult.overall_status} /></div>
            <div className="metadata-grid"><Metric label="Overall score" value={scoreLabel(validationResult.overall_score)} /><Metric label="Checks returned" value={checks.length} /><Metric label="Revision checked" value={validationResult.revision ?? "Not returned"} /></div>
            {summaryScores.length > 0 && <div className="metadata-grid">{summaryScores.map(([key, value]) => <Metric key={key} label={labelFor(key.replace(/_score$/, ""))} value={scoreLabel(value)} />)}</div>}
          </div>
          <div className="panel-header"><h3>Validation findings</h3><RawToggle shown={showRawValidationJson} onClick={() => setShowRawValidationJson(!showRawValidationJson)} label="validation JSON" controls="validation-json" /></div>
          {showRawValidationJson && <div id="validation-json"><JsonView data={validationResult} /></div>}
          {checks.length ? <div className="result-list">{checks.map((check, index) => (
            <article className={`card validation-check ${statusTone(check.status)}`} key={check.check_id || index}>
              <div className="panel-header"><h4>{check.check_name || labelFor(check.check_id || `Check ${index + 1}`)}</h4><div className="status-line"><ResultStatus status={check.status} /><span className="mono muted">{scoreLabel(check.score)}</span></div></div>
              {check.details && <p>{check.details}</p>}
              {Array.isArray(check.flagged_items) && check.flagged_items.length > 0 && <div className="inset-card"><div className="eyebrow">Findings requiring attention · {check.flagged_items.length}</div><DataFields data={check.flagged_items} /></div>}
            </article>
          ))}</div> : <EmptyState icon="shield" title="No individual checks returned">The summary above reflects the response. No check-level pass or score has been inferred.</EmptyState>}
          {Array.isArray(validationResult.recommendations) && validationResult.recommendations.length > 0 && <div className="card"><h3>Recommended next steps</h3><DataFields data={validationResult.recommendations} /></div>}
          <p className="muted">Automated validation findings support the reviewer. A human approval is still required for export.</p>
        </div>
      ) : !isValidatingICF && !validationError && <EmptyState icon="shield" title="Validation has not run">Run validation to inspect the generated draft against its protocol evidence. A draft is prepared first if needed.</EmptyState>}
      <NextStage onNavigate={onNavigate} target="review">Open human review</NextStage>
    </section>
  );
}

export function ReviewPanel({ vm, onNavigate }) {
  const {
    icfResult, validationResult, humanReview, reviewerComment,
    setReviewerComment, humanReviewLoading, humanReviewError, isGeneratingICF,
    icfError, handleUpdateHumanReview, handleRegenerateICF,
    templateReviewed, setTemplateReviewed, revisionHistory, icfStudyId, templateState,
  } = vm;
  const selectedStudyId = icfResult?.study_id || icfStudyId;
  const sameRevision = Boolean(icfResult?.study_id) && icfResult.study_id === icfStudyId && validationResult?.study_id === icfResult.study_id && validationResult?.revision === icfResult?.revision;
  const currentSelectedTemplateId = templateState?.selection?.template_id || icfResult?.template?.template_id;
  const templateMatches = Boolean(icfResult?.template?.template_id) && Boolean(currentSelectedTemplateId) && icfResult.template.template_id === currentSelectedTemplateId && !templateState?.error;
  const customTemplate = icfResult?.template?.kind === 'custom';
  const reviewStatus = humanReview?.review_status;
  const flaggedChecks = Array.isArray(validationResult?.checks) ? validationResult.checks.filter((check) => check.status !== "PASS" && check.status !== "PASSED") : [];
  const canRegenerate = reviewStatus === "CHANGES_REQUESTED" && humanReview?.reviewer_comment && humanReview.reviewer_comment.trim() !== "";
  return (
    <section className="panel review-panel" id="review" aria-busy={humanReviewLoading}>
      <SectionHeader eyebrow="03 / Human oversight" title="The final decision is human." description="Read the consent draft and validation findings, record your judgement and approve the document or request specific changes." action={<Badge tone="warning"><Icon name="user" size={14} />Human oversight required</Badge>} />
      <div className="two-column review-layout">
        <aside className="card review-context">
          <div className="eyebrow">Review context</div>
          <h3>{selectedStudyId || "No study selected"}</h3>
          <div className="metadata-grid"><Metric label="Draft revision" value={icfResult?.icf_draft ? `Revision ${icfResult.icf_draft.revision || 1}` : "No draft available"} /><Metric label="Validation score" value={validationResult ? scoreLabel(validationResult.overall_score) : "Not run"} /></div>
          {icfResult?.study_id && icfResult.study_id !== selectedStudyId && <p className="muted">The displayed draft belongs to study <span className="mono">{icfResult.study_id}</span>.</p>}
          {validationResult?.study_id && validationResult.study_id !== selectedStudyId && <p className="muted">The displayed validation report belongs to study <span className="mono">{validationResult.study_id}</span>.</p>}
          <div className="section-divider" />
          <h4>Automated validation</h4>
          {validationResult ? <><ResultStatus status={validationResult.overall_status} /><p className="muted">{flaggedChecks.length} returned check{flaggedChecks.length === 1 ? "" : "s"} require attention.</p>{flaggedChecks.length > 0 && <DataFields data={flaggedChecks.map((check) => ({ check: check.check_name || check.check_id, status: check.status, details: check.details, flagged_items: check.flagged_items }))} />}</> : <p className="muted">Run the Validation Agent before completing human review.</p>}
          {humanReview?.reviewed_at && <div className="metadata-item"><span className="eyebrow">Last reviewed</span><p>{Number.isNaN(Date.parse(humanReview.reviewed_at)) ? humanReview.reviewed_at : new Date(humanReview.reviewed_at).toLocaleString()}</p></div>}
        </aside>
        <div className="card review-decision">
          <div className="panel-header"><div><div className="eyebrow">Your review decision</div><h3>Clinical review</h3></div>{reviewStatus ? <ResultStatus status={reviewStatus} /> : <Badge>{humanReviewLoading ? "Loading review" : "Review not loaded"}</Badge>}</div>
          <p className="muted">{reviewStatus === "APPROVED" ? "This study is approved to proceed to document export." : reviewStatus === "CHANGES_REQUESTED" ? "Revisions have been requested. Saved feedback can guide a new draft and validation pass." : "Review the generated ICF and its evidence before making a decision."}</p>
          <Field label="Reviewer notes & feedback" id="reviewer-comment" hint="Include specific changes when requesting a revision."><textarea id="reviewer-comment" rows={6} value={reviewerComment} onChange={(event) => setReviewerComment(event.target.value)} disabled={humanReviewLoading} placeholder="Record your assessment or describe what needs to change in the consent draft…" /></Field>
          <div className="form-actions review-actions">
            <Button onClick={() => handleUpdateHumanReview("APPROVED")} disabled={humanReviewLoading || isGeneratingICF || !sameRevision || !templateMatches || (customTemplate && !templateReviewed)} busy={humanReviewLoading}><Icon name="check" size={17} />{humanReviewLoading ? "Updating…" : reviewStatus === "APPROVED" ? "Reconfirm approval" : "Approve ICF"}</Button>
            <Button variant="secondary" onClick={() => handleUpdateHumanReview("CHANGES_REQUESTED")} disabled={humanReviewLoading || isGeneratingICF || !selectedStudyId || !sameRevision}>{humanReviewLoading ? "Updating…" : "Request changes & regenerate"}</Button>
          </div>
          {!templateMatches && icfResult && <p className="muted">The selected template differs from this draft or could not be checked. Generate a new revision before approval.</p>}
          {customTemplate && <label className="template-review-check"><input type="checkbox" checked={Boolean(templateReviewed)} onChange={event => setTemplateReviewed(event.target.checked)} />I checked the populated template, including retained wording, against this study’s protocol.</label>}
          <p className="muted">Requesting changes immediately prepares a new revision, validates it, and returns it for human review.</p>
        </div>
      </div>
      {humanReviewLoading && <BusyNotice>Updating human review state.</BusyNotice>}
      {canRegenerate && isGeneratingICF && <BusyNotice>Preparing the requested revision and checking the Patient-Facing ICF document. Human review will remain pending.</BusyNotice>}
      {humanReviewError && <ErrorNotice title="Human review needs attention" message={humanReviewError} />}
      {canRegenerate && icfError && <ErrorNotice title="ICF regeneration could not finish" message={icfError} onRetry={isGeneratingICF || humanReviewLoading ? undefined : handleRegenerateICF} />}
      {icfResult?.icf_draft && <TechnicalDetails label="Read the current Patient-Facing ICF draft"><ICFDocument draft={icfResult.icf_draft} /></TechnicalDetails>}
      {Object.entries(icfResult?.document_preview || {}).map(([kind, text]) => <TechnicalDetails key={kind} label="Read populated Patient-Facing ICF document text"><p className="muted">This preview includes retained template wording. DOCX/PDF layout can differ from this text view.</p><div className="document-preview">{text}</div></TechnicalDetails>)}
      {revisionHistory && <TechnicalDetails label="Revision and review history"><DataFields data={{revisions: revisionHistory.revisions.map(item => ({revision: item.revision, template: item.template?.filename, validation: item.validation_report?.overall_status})), reviews: revisionHistory.reviews.map(item => ({revision: item.revision, status: item.review_status, comment: item.reviewer_comment, reviewed_at: item.reviewed_at}))}} /></TechnicalDetails>}
      <NextStage onNavigate={onNavigate} target="export">Open document export</NextStage>
    </section>
  );
}

export function ExportPanel({ vm }) {
  const { icfStudyId, icfResult, humanReview, isExportingDocx, exportError, handleExportDocx, lastExport, exportFormat, templateState } = vm;
  const [capabilities, setCapabilities] = useState(null);
  useEffect(() => {
    let active = true;
    fetch(`${API_BASE_URL}/api/icf/export-capabilities`).then(response => response.ok ? response.json() : null)
      .then(data => {if (active) setCapabilities(data);}).catch(() => {});
    return () => {active = false;};
  }, []);
  const studyId = icfResult?.study_id || icfStudyId;
  const revision = icfResult?.revision;
  const currentSelectedTemplateId = templateState?.selection?.template_id || icfResult?.template?.template_id;
  const ready = Boolean(icfResult?.icf_draft && studyId === icfStudyId && humanReview?.study_id === studyId &&
    humanReview?.review_status === 'APPROVED' && humanReview.approved_revision === revision &&
    currentSelectedTemplateId === icfResult?.template?.template_id && !templateState?.error);
  const exporting = (exportFormat || 'pdf').toUpperCase();
  const success = lastExport?.studyId === studyId && lastExport?.revision === revision && lastExport?.draft === icfResult?.icf_draft;
  return <section className="panel export-panel" id="export" aria-busy={isExportingDocx}>
      <SectionHeader eyebrow="04 / Final documents" title={ready ? 'Approved. Ready for the next step.' : 'Your final document, with approval.'} description="Download the approved Patient-Facing ICF as PDF, or keep an editable DOCX copy." action={<Badge tone={ready ? 'success' : 'warning'}><Icon name={ready ? 'check' : 'lock'} size={14} />{ready ? 'Ready for export' : 'Export locked'}</Badge>} />
    <div className="two-column export-layout">
      <div className="card export-document">
        <div className="document-mark"><Icon name="document" size={36} /></div><div className="eyebrow">PDF · Primary output</div><h3>Patient-Facing Informed Consent Form</h3>
        <p className="mono muted">{studyId || 'Select a study'}</p>
        <div className="metadata-grid"><Metric label="Draft revision" value={revision ? `Revision ${revision}` : 'Not available'} /><Metric label="Human review" value={humanReview?.study_id === studyId ? labelFor(humanReview.review_status) : 'Not loaded'} /></div>
        {icfResult?.template && <p className="muted">Template: <strong>{icfResult.template.filename}</strong></p>}
      </div>
      <div className="card export-actions">
        <h3>{ready ? 'Download approved Patient-Facing ICF' : 'Human approval unlocks export'}</h3>
        <p className="muted">{ready ? 'Each download uses the stored content and template for this approved revision.' : 'Generate and validate the current revision, review the populated document and approve it before exporting.'}</p>
        <div className="result-list"><Button onClick={() => handleExportDocx('patient_facing', 'pdf')} disabled={!ready || isExportingDocx} busy={isExportingDocx && exportFormat === 'pdf'}><Icon name="download" size={17} />{isExportingDocx && exportFormat === 'pdf' ? 'Generating PDF…' : 'Download Patient-Facing PDF'}</Button></div>
        {capabilities?.pdf?.available === false && <p className="muted" role="status">{capabilities.pdf.message}</p>}
        <div className="section-divider" /><h4>Optional editable DOCX</h4>
        <div className="result-list"><Button variant="secondary" onClick={() => handleExportDocx('patient_facing', 'docx')} disabled={!ready || isExportingDocx} busy={isExportingDocx && exportFormat === 'docx'}><Icon name="download" size={17} />{isExportingDocx && exportFormat === 'docx' ? 'Preparing DOCX…' : 'Download Patient-Facing DOCX'}</Button></div>
      </div>
    </div>
    {isExportingDocx && <BusyNotice>Preparing and verifying the approved {exporting} for download.</BusyNotice>}
    {exportError && <ErrorNotice title="Document export could not finish" message={exportError} />}
    {success && !exportError && !isExportingDocx && <div className="card export-success" role="status"><div className="status-line"><Badge tone="success"><Icon name="check" size={14} />Download requested</Badge><span className="mono">{lastExport.filename}</span></div><p className="muted">The {(lastExport.format || 'pdf').toUpperCase()} was generated and handed to your browser for download.</p></div>}
  </section>;
}
