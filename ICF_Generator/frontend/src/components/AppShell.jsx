import React from 'react';
import {Icon, Button, Badge, JsonView, ErrorNotice} from './ui';
import {navigation} from './workflow';

export function AppShell({vm, activePage, onNavigate, stages, children}) {
  const currentNav = navigation.find(item => item.id === activePage);
  const backendOnline = vm.healthStatus === 'success' && vm.healthData?.status === 'ok';
  return <div className="app-shell">
    <a className="skip-link" href="#workspace">Skip to workspace</a>
    <header className="topbar">
      <a className="brand" href="#source" onClick={event => {event.preventDefault(); onNavigate('source');}} aria-label="ICF AI home"><span className="brand-symbol"><Icon name="leaf" size={24}/></span><span>ICF<span className="brand-ai">AI</span><small>CONSENT WORKSPACE</small></span></a>
      <div className="topbar-context"><span>Research workspace</span><Icon name="chevron" size={13}/><strong>{currentNav.label}</strong></div>
      <div className="topbar-actions">
        <span className="study-chip mono">{vm.sourceMode === 'preloaded' ? vm.selectedStudyId || 'No study selected' : vm.selectedFile?.name || 'Protocol upload'}</span>
        <details className="health-popover">
          <summary><span className={`status-dot ${backendOnline ? 'online' : vm.healthStatus === 'error' ? 'offline' : ''}`}/>{backendOnline ? 'System online' : vm.healthStatus === 'error' ? 'System offline' : vm.healthStatus === 'loading' ? 'Checking system' : vm.healthStatus === 'success' ? 'Check status' : 'Check system'}<Icon name="chevron" size={12}/></summary>
          <div className="health-content"><div className="eyebrow">Backend connection</div><code>{vm.API_BASE_URL}</code>{vm.healthData && <JsonView data={vm.healthData}/>}<ErrorNotice title="Connection unavailable" message={vm.healthError}/><Button variant="secondary" busy={vm.healthStatus === 'loading'} onClick={vm.handleCheckConnection}>Check connection <Icon name="refresh" size={14}/></Button></div>
        </details>
      </div>
    </header>
    <aside className="sidebar">
      <div className="sidebar-heading eyebrow">YOUR WORKFLOW</div>
      <nav aria-label="Consent workflow">{navigation.map((item, index) => {
        const related = stages.filter(stage => stage.page === item.id);
        const state = related.some(stage => stage.state === 'active') ? 'active' : related.some(stage => stage.state === 'error') ? 'error' : related.every(stage => stage.state === 'complete') ? 'complete' : '';
        return <button key={item.id} className={`nav-item ${activePage === item.id ? 'selected' : ''}`} onClick={() => onNavigate(item.id)} aria-current={activePage === item.id ? 'step' : undefined}><span className="nav-number">{String(index + 1).padStart(2, '0')}</span><Icon name={item.icon} size={18}/><span>{item.label}</span><span className={`nav-state ${state}`} aria-label={state || undefined}>{state === 'complete' && <Icon name="check" size={12}/>}</span></button>;
      })}</nav>
      <div className="sidebar-note"><span className="icon-tile"><Icon name="user" size={20}/></span><strong>AI assisted.<br/>Human approved.</strong><p>Every final document requires a human review decision.</p><a href="#review" onClick={event => {event.preventDefault(); onNavigate('review');}}>Review workspace <Icon name="arrow" size={14}/></a></div>
      <div className="sidebar-footer"><span className="status-dot online"/> Evidence-led documentation</div>
    </aside>
    <main id="workspace" className="workspace" tabIndex="-1">
      <div className="workspace-breadcrumb"><span className="eyebrow">ICF GENERATOR</span><span className="muted">{String(navigation.findIndex(item => item.id === activePage) + 1).padStart(2, '0')} / 04</span></div>
      {activePage === 'source' ? <Hero onNavigate={onNavigate}/> : <div className="workspace-heading"><div><div className="eyebrow">EVIDENCE TO CONSENT</div><h1>{currentNav.label}</h1><p>{currentNav.description}.</p></div><span className="workspace-heading-icon"><Icon name={currentNav.icon} size={34}/></span></div>}
      <Pipeline stages={stages} activePage={activePage} onNavigate={onNavigate}/>
      <div className="workspace-content" key={activePage}>{children}</div>
      <footer className="workspace-footer"><span>ICF AI <span className="footer-divider">/</span> Informed consent, thoughtfully prepared.</span><span>Evidence <span aria-hidden="true">→</span> Intelligence <span aria-hidden="true">→</span> Human oversight</span></footer>
    </main>
  </div>;
}

function Hero({onNavigate}) {
  return <section className="hero" aria-label="About this workspace"><div className="hero-copy"><div className="hero-label"><span className="status-dot online"/> AI-ASSISTED CLINICAL DOCUMENTATION</div><h1>From protocol to<br/>informed <em>consent.</em></h1><p>Turn study evidence into clear, structured consent documents. Grounded in your protocol. Guided by human review.</p><div className="hero-footer"><span className="hero-footnote"><Icon name="shield" size={16}/> Evidence at every step</span><button className="text-button" onClick={() => onNavigate('review')}>Human oversight built in <Icon name="arrow" size={15}/></button></div></div><div className="hero-art" aria-hidden="true"><div className="art-orbit"/><div className="paper paper-back"><span>PROTOCOL EVIDENCE</span><i/><i/><i/><i/></div><div className="paper paper-front"><div className="paper-header"><span className="paper-brand"><Icon name="leaf" size={16}/> ICF AI</span><span>CONSENT FORM</span></div><h3>Information.<br/>Understanding.<br/><em>Choice.</em></h3><div className="paper-rule"/><i/><i/><i/><div className="paper-signature"><span>Participant consent</span><span>_________</span></div></div><div className="floating-label evidence-label"><span className="mini-icon"><Icon name="layers" size={14}/></span>Protocol-grounded</div><div className="floating-label review-label"><span className="mini-icon"><Icon name="user" size={14}/></span>Human-reviewed workflow</div><div className="art-caption">A CLEARER PATH TO INFORMED CONSENT</div></div></section>;
}

export function Pipeline({stages, activePage, onNavigate}) {
  const active = stages.find(stage => stage.state === 'active');
  const completed = stages.filter(stage => stage.state === 'complete').length;
  return <section className={`pipeline-card ${active ? 'is-processing' : ''}`} aria-label="Live workflow status"><div className="pipeline-heading"><div><span className="eyebrow">THE CONSENT PATHWAY</span><span className="pipeline-description">From source evidence to a reviewed document</span></div><span className="pipeline-count" aria-live="polite">{active ? `${active.label} in progress` : `${completed} of ${stages.length} stages complete`}</span></div><ol className="pipeline-stages">{stages.map((stage, i) => <li key={stage.label} className={`pipeline-stage is-${stage.state} ${stage.page === activePage ? 'is-current' : ''}`}><button onClick={() => onNavigate(stage.page)} aria-label={`${stage.label}: ${stage.state}`}><span className="stage-node">{stage.state === 'complete' ? <Icon name="check" size={15}/> : stage.state === 'error' || stage.state === 'warning' ? '!' : String(i + 1).padStart(2, '0')}</span><strong>{stage.label}</strong><small>{stage.state === 'active' ? 'In progress' : stage.state === 'warning' ? 'Attention' : stage.state}</small></button></li>)}</ol></section>;
}
