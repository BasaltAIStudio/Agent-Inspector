
const API_BASE = '/api/v1';

async function apiRequest(url, options = {}) {
    const response = await fetch(`${API_BASE}${url}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }
    return response.json();
}

async function loadAgents() {
    try {
        const agents = await apiRequest('/agents/');
        const container = document.getElementById('agents-list');
        if (agents.length === 0) {
            container.innerHTML = '<p class="empty-state">No agents connected yet.</p>';
            return;
        }
        container.innerHTML = agents.map(agent => `
            <div class="agent-item">
                <div class="agent-info">
                    <h4>${escapeHtml(agent.name)}</h4>
                    <p>${agent.agent_type} • ${escapeHtml(agent.description)}</p>
                </div>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-primary" onclick="selectAgent('${agent.id}', '${escapeHtml(agent.name)}')">Audit</button>
                    <button class="btn btn-secondary" onclick="deleteAgent('${agent.id}')">Delete</button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load agents:', error);
    }
}

async function loadAudits() {
    try {
        const audits = await apiRequest('/audits/');
        const container = document.getElementById('audits-list');
        if (audits.length === 0) {
            container.innerHTML = '<p class="empty-state">No audits run yet.</p>';
            return;
        }
        container.innerHTML = audits.map(audit => {
            const statusClass = audit.status === 'completed' ? 'badge-success' : 
                               audit.status === 'running' ? 'badge-info' : 'badge-danger';
            const scoreDisplay = audit.overall_score !== null ? 
                `<span style="font-weight: 800; color: var(--primary); margin-right: 12px;">${audit.overall_score.toFixed(1)}</span>` : 
                '--';
            return `
                <div class="audit-item">
                    <div class="audit-info">
                        <h4>Audit ${audit.id.slice(0, 8)}</h4>
                        <p>${new Date(audit.created_at).toLocaleString()} • ${audit.test_count} tests • ${audit.findings_count} findings</p>
                    </div>
                    <div style="display: flex; align-items: center; gap: 12px;">
                        ${scoreDisplay}
                        <span class="badge ${statusClass}">${audit.status}</span>
                        <a href="/audit/${audit.id}" class="btn btn-primary">View Report</a>
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Failed to load audits:', error);
    }
}

let selectedAgentId = null;
function selectAgent(agentId, agentName) {
    selectedAgentId = agentId;
    document.getElementById('audit-section').style.display = 'block';
    document.getElementById('audit-section').scrollIntoView({ behavior: 'smooth' });
}

async function deleteAgent(agentId) {
    if (!confirm('Delete this agent?')) return;
    try {
        await apiRequest(`/agents/${agentId}`, { method: 'DELETE' });
        loadAgents();
    } catch (error) { alert(error.message); }
}

document.getElementById('agent-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const agentData = {
        name: document.getElementById('agent-name').value,
        description: document.getElementById('agent-description').value,
        agent_type: document.getElementById('agent-type').value,
        endpoint: document.getElementById('agent-endpoint').value,
        api_key: document.getElementById('agent-api-key').value,
    };
    try {
        await apiRequest('/agents/', { method: 'POST', body: JSON.stringify(agentData) });
        e.target.reset();
        loadAgents();
    } catch (error) { alert(error.message); }
});

document.getElementById('audit-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!selectedAgentId) { alert('Select an agent first'); return; }
    const auditData = {
        agent_id: selectedAgentId,
        expected_behavior: document.getElementById('expected-behavior').value,
        prohibited_actions: document.getElementById('prohibited-actions').value,
        test_count: parseInt(document.getElementById('test-count').value),
        include_security: document.getElementById('include-security').checked,
        include_cost: document.getElementById('include-cost').checked,
    };
    const loadingOverlay = document.getElementById('loading-overlay');
    loadingOverlay.style.display = 'flex';
    try {
        const result = await apiRequest('/audits/', { method: 'POST', body: JSON.stringify(auditData) });
        const pollInterval = setInterval(async () => {
            try {
                const audit = await apiRequest(`/audits/${result.id}`);
                if (audit.status === 'completed') {
                    clearInterval(pollInterval);
                    window.location.href = `/audit/${result.id}`;
                } else if (audit.status === 'failed') {
                    clearInterval(pollInterval);
                    loadingOverlay.style.display = 'none';
                }
            } catch (error) { console.error(error); }
        }, 2000);
    } catch (error) {
        loadingOverlay.style.display = 'none';
        alert(error.message);
    }
});

async function loadReport(auditId) {
    try {
        const [audit, findings, tests] = await Promise.all([
            apiRequest(`/audits/${auditId}`),
            apiRequest(`/audits/${auditId}/findings`),
            apiRequest(`/audits/${auditId}/tests`),
        ]);
        
        const container = document.getElementById('report-container');
        const grade = audit.overall_score >= 90 ? 'A' : audit.overall_score >= 80 ? 'B' : audit.overall_score >= 70 ? 'C' : audit.overall_score >= 60 ? 'D' : 'F';
        
        const categoryBars = [
            { name: 'Reliability', score: audit.reliability_score },
            { name: 'Security', score: audit.security_score },
            { name: 'Tool Usage', score: audit.tool_usage_score },
            { name: 'Hallucination', score: audit.hallucination_score },
            { name: 'Privacy', score: audit.privacy_score },
            { name: 'Cost', score: audit.cost_score },
        ].map(cat => `
            <div class="score-bar">
                <div class="score-bar-label">${cat.name}</div>
                <div class="score-bar-track">
                    <div class="score-bar-fill" style="width: ${cat.score || 0}%"></div>
                </div>
                <div class="score-bar-value">${cat.score !== null ? cat.score.toFixed(1) : '--'}</div>
            </div>
        `).join('');

        const findingsHtml = findings.length > 0 ? findings.map(f => `
            <div class="finding-item severity-${f.severity}">
                <div class="finding-header">
                    <div class="finding-title">${escapeHtml(f.title)}</div>
                    <span class="badge badge-${f.severity}">${f.severity}</span>
                </div>
                <div class="finding-description">${escapeHtml(f.description)}</div>
                <div class="finding-remediation">
                    <strong style="color: var(--primary);">Remediation:</strong> ${escapeHtml(f.remediation)}
                </div>
            </div>
        `).join('') : '<p class="empty-state">No findings detected.</p>';

        container.innerHTML = `
            <div class="report-container">
                <div class="report-header">
                    <div>
                        <h2>Security Audit Report</h2>
                        <p style="color: var(--text-muted);">Audit ID: ${audit.id.slice(0, 8)} • ${new Date(audit.created_at).toLocaleString()}</p>
                    </div>
                    <div class="score-circle">${audit.overall_score !== null ? audit.overall_score.toFixed(1) : '--'}</div>
                </div>
                
                <div class="summary-grid">
                    <div class="summary-card"><div class="value">${audit.test_count}</div><div class="label">Total Tests</div></div>
                    <div class="summary-card"><div class="value">${audit.findings_count}</div><div class="label">Findings</div></div>
                    <div class="summary-card"><div class="value" style="color: var(--sev-critical)">${audit.critical_count}</div><div class="label">Critical</div></div>
                    <div class="summary-card"><div class="value" style="color: var(--sev-high)">${audit.high_count}</div><div class="label">High</div></div>
                </div>
                
                <div class="card">
                    <h3>Calibration Metrics</h3>
                    ${categoryBars}
                </div>
                
                <div class="card">
                    <h3>Failure Analysis & Findings</h3>
                    ${findingsHtml}
                </div>
            </div>
        `;
    } catch (error) {
        document.getElementById('report-container').innerHTML = `<div class="error">Failed to load report: ${error.message}</div>`;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

document.addEventListener('DOMContentLoaded', () => {
    loadAgents();
    loadAudits();
});
