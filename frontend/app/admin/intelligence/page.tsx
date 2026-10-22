"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { Me } from "@/lib/types";
import { AdminNav } from "@/components/admin/AdminNav";
import "./page.css";

interface DashboardSummary {
  summary: {
    high_risk_organizations: number;
    active_anomaly_flags: number;
    unread_alerts: number;
    churn_risk_organizations: number;
    pending_documents: number;
  };
  timestamp: string;
}

interface RiskScore {
  org_id: string;
  score_type: string;
  score_value: number;
  factors: Record<string, number>;
  confidence: string;
  computed_at: string;
}

interface SmartAlert {
  id: string;
  alert_type: string;
  message: string;
  priority: string;
  subject_org_id: string | null;
  recommended_action: string | null;
  created_at: string;
  read: boolean;
}

interface AnomalyFlag {
  id: string;
  org_id: string;
  flag_type: string;
  severity: string;
  details: Record<string, unknown>;
  reasoning: string | null;
  acknowledged: boolean;
  created_at: string;
}

interface ChurnRisk {
  org_id: string;
  org_name: string;
  org_type: string;
  churn_risk_score: number;
  intervention: string | null;
  computed_at: string;
}

interface CampaignForecast {
  project_id: string;
  project_title: string;
  success_probability: number;
  confidence: string;
  computed_at: string;
}

export default function AdminIntelligencePage() {
  const router = useRouter();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [riskScores, setRiskScores] = useState<RiskScore[] | null>(null);
  const [alerts, setAlerts] = useState<SmartAlert[] | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyFlag[] | null>(null);
  const [churnRisks, setChurnRisks] = useState<ChurnRisk[] | null>(null);
  const [forecasts, setForecasts] = useState<CampaignForecast[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"overview" | "risks" | "alerts" | "anomalies" | "churn" | "forecasts">("overview");

  useEffect(() => {
    if (!getToken()) {
      router.replace("/admin/login");
      return;
    }

    async function loadData() {
      try {
        // Check auth first
        await api<Me>("/auth/me");

        // Load dashboard summary
        const dashSummary = await api<DashboardSummary>("/api/admin/dashboard/summary");
        setSummary(dashSummary);

        // Load all data in parallel
        const [risks, smartAlerts, flags, churn, forecast] = await Promise.all([
          api<{ scores: RiskScore[] }>("/api/admin/risk-scores?limit=15").catch(() => null),
          api<{ alerts: SmartAlert[] }>("/api/admin/smart-alerts?limit=15").catch(() => null),
          api<{ flags: AnomalyFlag[] }>("/api/admin/anomalies?limit=15").catch(() => null),
          api<{ churn_risks: ChurnRisk[] }>("/api/admin/churn-risks?limit=15").catch(() => null),
          api<{ forecasts: CampaignForecast[] }>("/api/admin/campaign-forecasts?limit=15").catch(() => null),
        ]);

        if (risks) setRiskScores(risks.scores);
        if (smartAlerts) setAlerts(smartAlerts.alerts);
        if (flags) setAnomalies(flags.flags);
        if (churn) setChurnRisks(churn.churn_risks);
        if (forecast) setForecasts(forecast.forecasts);

        setError(null);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          router.replace("/admin/login");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [router]);

  const renderSeverityBadge = (severity: string) => {
    const colors: Record<string, string> = {
      CRITICAL: "🔴",
      HIGH: "🟠",
      MEDIUM: "🟡",
      LOW: "🟢",
    };
    return colors[severity] || "⚫";
  };

  const renderPriorityBadge = (priority: string) => {
    const colors: Record<string, string> = {
      URGENT: "🔴",
      HIGH: "🟠",
      MEDIUM: "🟡",
      LOW: "🟢",
    };
    return colors[priority] || "⚫";
  };

  if (loading) {
    return (
      <div className="intelligence-page">
        <AdminNav />
        <div className="page-header">
          <div className="header-content">
            <h1>🧠 Admin Intelligence</h1>
            <p>Smart AI-Powered Admin Dashboard</p>
          </div>
        </div>
        <div className="loading">
          <div className="spinner"></div>
          <p>Loading intelligence data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="intelligence-page">
        <AdminNav />
        <div className="page-header">
          <div className="header-content">
            <h1>🧠 Admin Intelligence</h1>
          </div>
        </div>
        <div className="error-box">
          <div className="error-icon">⚠️</div>
          <div className="error-message">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="intelligence-page">
      <AdminNav />
      <div className="page-header">
        <div className="header-content">
          <h1>🧠 Admin Intelligence Dashboard</h1>
          <p>Smart AI-Powered Risk Scoring, Anomaly Detection & Predictive Intelligence</p>
        </div>
      </div>

      <div className="tabs-container">
        <div className="tabs">
          <button
            className={`tab ${activeTab === "overview" ? "active" : ""}`}
            onClick={() => setActiveTab("overview")}
          >
            Overview
          </button>
          <button
            className={`tab ${activeTab === "risks" ? "active" : ""}`}
            onClick={() => setActiveTab("risks")}
          >
            Risk Scores {riskScores && <span className="badge">{riskScores.length}</span>}
          </button>
          <button
            className={`tab ${activeTab === "alerts" ? "active" : ""}`}
            onClick={() => setActiveTab("alerts")}
          >
            Smart Alerts {summary?.summary.unread_alerts ? <span className="badge urgent">{summary.summary.unread_alerts}</span> : null}
          </button>
          <button
            className={`tab ${activeTab === "anomalies" ? "active" : ""}`}
            onClick={() => setActiveTab("anomalies")}
          >
            Anomalies {summary?.summary.active_anomaly_flags ? <span className="badge critical">{summary.summary.active_anomaly_flags}</span> : null}
          </button>
          <button
            className={`tab ${activeTab === "churn" ? "active" : ""}`}
            onClick={() => setActiveTab("churn")}
          >
            Churn Risks {churnRisks && <span className="badge">{churnRisks.length}</span>}
          </button>
          <button
            className={`tab ${activeTab === "forecasts" ? "active" : ""}`}
            onClick={() => setActiveTab("forecasts")}
          >
            Forecasts {forecasts && <span className="badge">{forecasts.length}</span>}
          </button>
        </div>
      </div>

      {activeTab === "overview" && summary && (
        <div className="overview-section">
          <div className="metrics-grid">
            <div className="metric-card critical">
              <div className="metric-icon">⚠️</div>
              <div className="metric-label">High-Risk Orgs</div>
              <div className="metric-value">{summary.summary.high_risk_organizations}</div>
              <div className="metric-desc">Score &gt; 70</div>
            </div>

            <div className="metric-card urgent">
              <div className="metric-icon">🚨</div>
              <div className="metric-label">Anomaly Flags</div>
              <div className="metric-value">{summary.summary.active_anomaly_flags}</div>
              <div className="metric-desc">Unacknowledged</div>
            </div>

            <div className="metric-card warning">
              <div className="metric-icon">📢</div>
              <div className="metric-label">Unread Alerts</div>
              <div className="metric-value">{summary.summary.unread_alerts}</div>
              <div className="metric-desc">Actionable</div>
            </div>

            <div className="metric-card info">
              <div className="metric-icon">📉</div>
              <div className="metric-label">Churn Risk</div>
              <div className="metric-value">{summary.summary.churn_risk_organizations}</div>
              <div className="metric-desc">May become inactive</div>
            </div>

            <div className="metric-card">
              <div className="metric-icon">📋</div>
              <div className="metric-label">Pending Docs</div>
              <div className="metric-value">{summary.summary.pending_documents}</div>
              <div className="metric-desc">Awaiting review</div>
            </div>
          </div>

          {/* Quick actions */}
          <div className="quick-actions">
            <h3>Quick Actions</h3>
            <div className="actions-grid">
              {summary.summary.high_risk_organizations > 0 && (
                <button className="action-btn critical">
                  <span className="action-icon">⚠️</span>
                  <span className="action-text">Review {summary.summary.high_risk_organizations} High-Risk Org{summary.summary.high_risk_organizations !== 1 ? "s" : ""}</span>
                </button>
              )}
              {summary.summary.active_anomaly_flags > 0 && (
                <button className="action-btn urgent">
                  <span className="action-icon">🚨</span>
                  <span className="action-text">Acknowledge {summary.summary.active_anomaly_flags} Anomaly Flag{summary.summary.active_anomaly_flags !== 1 ? "s" : ""}</span>
                </button>
              )}
              {summary.summary.unread_alerts > 0 && (
                <button className="action-btn warning">
                  <span className="action-icon">📢</span>
                  <span className="action-text">Act on {summary.summary.unread_alerts} Smart Alert{summary.summary.unread_alerts !== 1 ? "s" : ""}</span>
                </button>
              )}
              {summary.summary.pending_documents > 0 && (
                <button className="action-btn info">
                  <span className="action-icon">📋</span>
                  <span className="action-text">Auto-Approve Docs ({summary.summary.pending_documents})</span>
                </button>
              )}
            </div>
          </div>

          {/* Health indicators */}
          <div className="health-indicators">
            <h3>System Health</h3>
            <div className="indicators">
              <div className="indicator">
                <div className="indicator-label">Platform Health</div>
                <div className="indicator-bar">
                  <div className="indicator-fill" style={{ width: "85%" }}></div>
                </div>
                <div className="indicator-value">85%</div>
              </div>
              <div className="indicator">
                <div className="indicator-label">Alert Response</div>
                <div className="indicator-bar">
                  <div className="indicator-fill warning" style={{ width: "72%" }}></div>
                </div>
                <div className="indicator-value">72%</div>
              </div>
              <div className="indicator">
                <div className="indicator-label">Document Review</div>
                <div className="indicator-bar">
                  <div className="indicator-fill critical" style={{ width: "58%" }}></div>
                </div>
                <div className="indicator-value">58%</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === "risks" && (
        <div className="section">
          <h2>🎯 Risk Scores</h2>
          {riskScores && riskScores.length > 0 ? (
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Organization</th>
                    <th>Type</th>
                    <th>Risk Score</th>
                    <th>Confidence</th>
                    <th>Verification</th>
                    <th>Completion</th>
                    <th>Velocity</th>
                    <th>Account Age</th>
                  </tr>
                </thead>
                <tbody>
                  {riskScores.map((score) => (
                    <tr key={score.org_id} className={`risk-${score.score_value > 70 ? "critical" : score.score_value > 40 ? "warning" : "good"}`}>
                      <td className="org-id">{score.org_id.substring(0, 12)}...</td>
                      <td>{score.score_type}</td>
                      <td>
                        <span className={`score-badge score-${score.score_value > 70 ? "critical" : score.score_value > 40 ? "warning" : "good"}`}>
                          {score.score_value}
                        </span>
                      </td>
                      <td><span className="confidence-badge">{score.confidence}</span></td>
                      <td>{score.factors.verification}</td>
                      <td>{score.factors.completion_rate}</td>
                      <td>{score.factors.donation_velocity}</td>
                      <td>{score.factors.account_activity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">📊</div>
              <p>No risk scores computed yet. Run scoring to populate.</p>
            </div>
          )}
        </div>
      )}

      {activeTab === "alerts" && (
        <div className="section">
          <h2>🔔 Smart Alerts</h2>
          {alerts && alerts.length > 0 ? (
            <div className="alerts-grid">
              {alerts.map((alert) => (
                <div key={alert.id} className={`alert-card priority-${alert.priority.toLowerCase()}`}>
                  <div className="alert-header">
                    <div className="alert-icon">{renderPriorityBadge(alert.priority)}</div>
                    <div className="alert-info">
                      <div className="alert-type">{alert.alert_type}</div>
                      <div className="alert-time">{new Date(alert.created_at).toLocaleString()}</div>
                    </div>
                  </div>
                  <div className="alert-message">{alert.message}</div>
                  {alert.recommended_action && (
                    <div className="alert-action">
                      <strong>💡 Suggested:</strong> {alert.recommended_action}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">✨</div>
              <p>No active alerts. Your system is running smoothly!</p>
            </div>
          )}
        </div>
      )}

      {activeTab === "anomalies" && (
        <div className="section">
          <h2>⚠️ Anomaly Flags</h2>
          {anomalies && anomalies.length > 0 ? (
            <div className="anomalies-grid">
              {anomalies.map((flag) => (
                <div key={flag.id} className={`anomaly-card severity-${flag.severity.toLowerCase()}`}>
                  <div className="anomaly-header">
                    <div className="anomaly-icon">{renderSeverityBadge(flag.severity)}</div>
                    <div className="anomaly-info">
                      <div className="anomaly-type">{flag.flag_type}</div>
                      <div className="anomaly-org">Org: {flag.org_id.substring(0, 12)}...</div>
                    </div>
                    <div className="anomaly-status">{flag.acknowledged ? "✓ Acknowledged" : "⏳ Pending"}</div>
                  </div>
                  {flag.reasoning && <div className="anomaly-reasoning">{flag.reasoning}</div>}
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">✅</div>
              <p>No anomalies detected. Great job!</p>
            </div>
          )}
        </div>
      )}

      {activeTab === "churn" && (
        <div className="section">
          <h2>📉 Churn Risks</h2>
          {churnRisks && churnRisks.length > 0 ? (
            <div className="churn-grid">
              {churnRisks.map((risk) => (
                <div key={risk.org_id} className={`churn-card risk-${risk.churn_risk_score > 75 ? "critical" : risk.churn_risk_score > 50 ? "warning" : "good"}`}>
                  <div className="churn-header">
                    <div className="churn-name">{risk.org_name || "Unknown Org"}</div>
                    <div className="churn-score">{risk.churn_risk_score}%</div>
                  </div>
                  <div className="churn-type">{risk.org_type}</div>
                  {risk.intervention && <div className="churn-intervention">💡 {risk.intervention}</div>}
                  <div className="churn-bar">
                    <div className="churn-bar-fill" style={{ width: `${risk.churn_risk_score}%` }}></div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">📊</div>
              <p>No churn predictions yet.</p>
            </div>
          )}
        </div>
      )}

      {activeTab === "forecasts" && (
        <div className="section">
          <h2>🎯 Campaign Forecasts</h2>
          {forecasts && forecasts.length > 0 ? (
            <div className="forecasts-grid">
              {forecasts.map((forecast) => (
                <div key={forecast.project_id} className={`forecast-card success-${forecast.success_probability > 70 ? "high" : forecast.success_probability > 40 ? "medium" : "low"}`}>
                  <div className="forecast-header">
                    <div className="forecast-title">{forecast.project_title}</div>
                    <div className="forecast-prob">{Math.round(forecast.success_probability)}%</div>
                  </div>
                  <div className="forecast-confidence">
                    Confidence: <span className="confidence-badge">{forecast.confidence}</span>
                  </div>
                  <div className="forecast-bar">
                    <div className="forecast-bar-fill" style={{ width: `${forecast.success_probability}%` }}></div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">📈</div>
              <p>No campaign forecasts yet.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
