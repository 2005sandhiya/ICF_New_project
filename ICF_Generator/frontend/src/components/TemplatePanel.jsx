import React, {useEffect, useRef, useState} from 'react';
import {Badge, Button, BusyNotice, ErrorNotice, Field} from './ui.jsx';
import {templateDownloadUrl, templateRequest, validateTemplateFile} from '../api/templates.js';

export function useICFTemplate(studyId, onChanged) {
  const [selection, setSelection] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [reload, setReload] = useState(0);
  const currentStudy = useRef(studyId);
  currentStudy.current = studyId;
  useEffect(() => {
    setSelection(null); setError(''); setMessage('');
    if (!studyId.trim()) {setBusy(false); return;}
    let active = true;
    const controller = new AbortController();
    setBusy(true);
    templateRequest(studyId, 'GET', null, controller.signal).then(result => {
      if (!active) return;
      setBusy(false);
      if (result.success) setSelection(result.data);
      else setError(result.error);
    });
    return () => {active = false; controller.abort();};
  }, [studyId, reload]);
  async function change(method, file) {
    if (file) {
      const validationError = validateTemplateFile(file);
      if (validationError) {setError(validationError); setMessage(''); return;}
    }
    const target = studyId;
    setBusy(true); setError(''); setMessage('');
    const result = await templateRequest(target, method, file);
    if (currentStudy.current !== target) return;
    setBusy(false);
    if (!result.success) {setError(result.error); return;}
    setSelection(result.data);
    setMessage(method === 'DELETE' ? 'Custom template removed. The default template will be used for the next revision.' : 'Template uploaded. Generate a new revision to use this template.');
    onChanged(result.data);
  }
  return {selection: selection?.study_id === studyId ? selection : null, busy, error, message,
    upload: file => change('POST', file), remove: () => change('DELETE'), retry: () => setReload(n => n + 1)};
}

export function TemplatePanel({studyId, state, generating, deferUpload = false, stagedFile = null, onStageTemplate, onStageError}) {
  const input = useRef(null);
  const [stagingError, setStagingError] = useState('');
  const custom = deferUpload ? Boolean(stagedFile) : state.selection?.kind === 'custom';
  const busy = deferUpload ? Boolean(generating) : state.busy;
  const selection = deferUpload ? null : state.selection;
  const stageFile = file => {
    const validationError = validateTemplateFile(file);
    if (validationError) {
      setStagingError(validationError);
      onStageError?.(validationError);
      return;
    }
    setStagingError('');
    onStageError?.('');
    onStageTemplate?.(file);
  };
  const removeTemplate = () => {
    if (deferUpload) {
      onStageTemplate?.(null);
      setStagingError('');
      onStageError?.('');
    } else state.remove();
  };
  return <section className="card template-panel" aria-label="ICF Template" aria-busy={state.busy}>
    <div className="panel-header"><div><div className="eyebrow">Optional document layout</div><h3>ICF Template</h3></div><Badge>{custom ? 'Custom DOCX' : selection ? 'Default template' : deferUpload ? 'Optional DOCX' : 'Checking template'}</Badge></div>
    <p className="muted">{deferUpload ? <>Upload an optional DOCX template for the study identified in <strong>{studyId || 'the uploaded protocol'}</strong>. When no custom template is selected, the default ICF template is used.</> : <>Upload an optional DOCX template for <span className="mono">{studyId || 'the target study'}</span>. When no custom template is selected, the default ICF template is used.</>}</p>
    {stagedFile && deferUpload && <p><strong>{stagedFile.name}</strong> <span className="muted">will be saved for this study when generation starts.</span></p>}
    {selection && <p><strong>{selection.filename}</strong></p>}
    <Field label={custom ? 'Replace DOCX template' : 'Upload DOCX template'} id="icf-template-file" hint="DOCX only, up to 10 MB. Use ICF section headings or placeholders such as {{icf.purpose}}. Template text is never used as clinical evidence.">
      <input ref={input} type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" disabled={busy || (!deferUpload && !studyId.trim())} onChange={event => {const file = event.target.files?.[0]; if (file) deferUpload ? stageFile(file) : state.upload(file); event.target.value = '';}} />
    </Field>
    <div className="form-actions">{custom && !deferUpload && <a className="button button-secondary" href={templateDownloadUrl(studyId)} download>View selected template</a>}{(custom || state.error) && <Button variant="secondary" disabled={busy || (!deferUpload && !studyId.trim())} onClick={removeTemplate}>{deferUpload ? 'Remove selected DOCX' : 'Remove custom template / use default'}</Button>}</div>
    {selection?.warnings?.length > 0 && <ul className="data-list muted">{selection.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul>}
    {deferUpload && stagedFile && <p className="muted">This template will be associated only with the study identified from the uploaded protocol.</p>}
    {busy && <BusyNotice>{deferUpload ? 'Preparing the selected template.' : 'Checking the selected template.'}</BusyNotice>}
    {(deferUpload ? stagingError : state.error) && <ErrorNotice title="Template needs attention" message={deferUpload ? stagingError : state.error} onRetry={deferUpload ? undefined : state.retry} />}
    {!deferUpload && state.message && <p role="status">{state.message}</p>}
  </section>;
}
