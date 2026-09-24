-- PostgreSQL schema for AgentInspector
-- Run this script against your PostgreSQL database to create all tables.

CREATE TABLE IF NOT EXISTS agents (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    agent_type VARCHAR(100),
    config TEXT,
    endpoint VARCHAR(500),
    api_key VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audits (
    id VARCHAR(255) PRIMARY KEY,
    agent_id VARCHAR(255) REFERENCES agents(id),
    status VARCHAR(50) DEFAULT 'pending',
    overall_score FLOAT,
    reliability_score FLOAT,
    security_score FLOAT,
    tool_usage_score FLOAT,
    hallucination_score FLOAT,
    privacy_score FLOAT,
    cost_score FLOAT,
    latency_score FLOAT,
    instruction_following_score FLOAT,
    human_escalation_score FLOAT,
    test_count INTEGER DEFAULT 0,
    findings_count INTEGER DEFAULT 0,
    critical_count INTEGER DEFAULT 0,
    high_count INTEGER DEFAULT 0,
    medium_count INTEGER DEFAULT 0,
    low_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS findings (
    id VARCHAR(255) PRIMARY KEY,
    audit_id VARCHAR(255) REFERENCES audits(id),
    category VARCHAR(100),
    severity VARCHAR(50),
    title VARCHAR(500),
    description TEXT,
    evidence TEXT,
    remediation TEXT,
    reproducibility FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS test_results (
    id VARCHAR(255) PRIMARY KEY,
    audit_id VARCHAR(255) REFERENCES audits(id),
    test_name VARCHAR(255),
    category VARCHAR(100),
    status VARCHAR(50),
    input_data TEXT,
    output_data TEXT,
    expected TEXT,
    actual TEXT,
    latency_ms FLOAT,
    cost FLOAT,
    tokens_used INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS task_queue (
    id VARCHAR(255) PRIMARY KEY,
    audit_id VARCHAR(255) REFERENCES audits(id),
    status VARCHAR(50) DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    retries INTEGER DEFAULT 0,
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_keys (
    key VARCHAR(255) PRIMARY KEY,
    owner VARCHAR(255),
    rate_limit INTEGER DEFAULT 100,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audits_agent_id ON audits(agent_id);
CREATE INDEX IF NOT EXISTS idx_findings_audit_id ON findings(audit_id);
CREATE INDEX IF NOT EXISTS idx_test_results_audit_id ON test_results(audit_id);
CREATE INDEX IF NOT EXISTS idx_task_queue_audit_id ON task_queue(audit_id);

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id VARCHAR(255) PRIMARY KEY,
    webhook_url VARCHAR(500) NOT NULL,
    payload TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    next_retry_at TIMESTAMP,
    failed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_status ON webhook_deliveries(status);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_next_retry ON webhook_deliveries(next_retry_at);
