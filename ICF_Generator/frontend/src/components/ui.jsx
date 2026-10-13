import React, { useId } from 'react';

const paths = {
  leaf: <><path d="M19 4C9 3 3 7 5 14s12 7 14-10Z"/><path d="m5 19 9-10"/></>,
  document: <><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z"/><path d="M14 3v6h6M8 13h8M8 17h5"/></>,
  study: <><path d="M5 4h14v16H5zM8 8h8M8 12h4M8 16h8"/><path d="M9 2v4M15 2v4"/></>,
  layers: <><path d="m12 3 10 5-10 5L2 8ZM2 12l10 5 10-5M2 16l10 5 10-5"/></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
  spark: <><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5ZM20 2v4M18 4h4"/></>,
  shield: <><path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6Z"/><path d="m8 12 3 3 5-6"/></>,
  user: <><circle cx="12" cy="7" r="4"/><path d="M4 21v-3a8 8 0 0 1 16 0v3"/></>,
  download: <><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></>,
  upload: <><path d="M12 16V4m-5 5 5-5 5 5M4 17v4h16v-4"/></>,
  arrow: <path d="M4 12h16m-6-6 6 6-6 6"/>,
  check: <path d="m5 12 4 4L19 6"/>,
  chevron: <path d="m9 5 7 7-7 7"/>,
  lock: <><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4M12 14v3"/></>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></>,
  alert: <><path d="m12 3 10 18H2ZM12 9v5M12 17h.01"/></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/></>,
  refresh: <><path d="M20 10a8 8 0 0 0-14-5L3 8m0-5v5h5M4 14a8 8 0 0 0 14 5l3-3m0 5v-5h-5"/></>,
};

export function Icon({name = 'document', size = 20, ...props}) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name] || paths.document}</svg>;
}
export function Button({children, variant = 'primary', busy = false, className = '', disabled, ...props}) {
  return <button type="button" className={`button button-${variant} ${className}`} disabled={disabled || busy} aria-busy={busy || undefined} {...props}>{busy && <span className="loading-dots" aria-hidden="true"><i/><i/><i/></span>}{children}</button>;
}
export function Badge({children, tone = 'neutral'}) { return <span className={`badge badge-${tone}`}>{children}</span>; }
export function SectionHeader({eyebrow, title, description, action}) {
  return <div className="panel-header"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h2>{title}</h2>{description && <p className="muted">{description}</p>}</div>{action}</div>;
}
export function Field({label, id, children, hint}) {
  const autoId = useId();
  const fieldId = id || autoId;
  return <div className="field"><label htmlFor={fieldId}>{label}</label>{React.isValidElement(children) ? React.cloneElement(children, {id: children.props.id || fieldId, 'aria-describedby': hint ? `${fieldId}-hint` : children.props['aria-describedby']}) : children}{hint && <span className="field-hint" id={`${fieldId}-hint`}>{hint}</span>}</div>;
}
export function ErrorNotice({title = 'This step needs attention', message, onRetry}) {
  if (!message) return null;
  return <div className="error-notice" role="alert"><Icon name="alert"/><div><strong>{title}</strong><p>{typeof message === 'string' ? message : JSON.stringify(message)}</p>{onRetry && <Button variant="secondary" onClick={onRetry}>Try again <Icon name="refresh" size={14}/></Button>}</div></div>;
}
export function EmptyState({icon = 'document', title, children}) {
  return <div className="empty-state"><span className="icon-tile"><Icon name={icon} size={24}/></span><h3>{title}</h3><div className="muted">{children}</div></div>;
}
export function BusyNotice({children}) {
  return <div className="busy-notice" role="status" aria-live="polite"><span className="loading-dots" aria-hidden="true"><i/><i/><i/></span>{children}<span className="activity-track" aria-hidden="true"/></div>;
}
export function JsonView({data}) { return <pre className="json-view" tabIndex="0" aria-label="Raw JSON response">{JSON.stringify(data, null, 2)}</pre>; }
const friendlyKey = key => key.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase());
export function DataFields({data}) {
  if (data === null || data === undefined || data === '') return <span className="muted">Not available in source</span>;
  if (typeof data === 'boolean') return <span>{data ? 'Yes' : 'No'}</span>;
  if (typeof data !== 'object') return <span className="data-value">{String(data)}</span>;
  if (Array.isArray(data)) return data.length ? <ul className="data-list">{data.map((item, i) => <li key={i}><DataFields data={item}/></li>)}</ul> : <span className="muted">None returned</span>;
  return <dl className="data-fields">{Object.entries(data).map(([key, value]) => <div key={key} className="data-field"><dt>{friendlyKey(key)}</dt><dd><DataFields data={value}/></dd></div>)}</dl>;
}
export function Metric({label, value}) { return <div className="metric"><span>{label}</span><strong>{value ?? '—'}</strong></div>; }
export function TechnicalDetails({children, label = 'Technical details', open}) { return <details className="technical-details" open={open}><summary>{label}<span aria-hidden="true">+</span></summary><div className="technical-content">{children}</div></details>; }
