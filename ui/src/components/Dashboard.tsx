import type { ClaimSummary } from "../types";

interface DashboardProps {
  claims: ClaimSummary[];
}

export function Dashboard({ claims }: DashboardProps) {
  // Calculate stats
  const totalClaims = claims.length;
  const reviewedClaims = claims.filter((c) => c.status === "Reviewed").length;
  const pendingClaims = totalClaims - reviewedClaims;
  const highRiskClaims = claims.filter((c) => c.risk_score >= 50).length;
  const totalAmount = claims.reduce((sum, c) => sum + (c.amount || 0), 0);
  const avgRiskScore = claims.length > 0
    ? Math.round(claims.reduce((sum, c) => sum + c.risk_score, 0) / claims.length)
    : 0;

  // Group by loss type
  const lossTypeStats = claims.reduce((acc, c) => {
    acc[c.loss_type] = (acc[c.loss_type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="p-6">
      <h2 className="text-2xl font-semibold text-gray-900 mb-6">Dashboard</h2>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          title="Total Claims"
          value={totalClaims.toString()}
          icon={<ClaimsIcon />}
          color="blue"
        />
        <StatCard
          title="Pending Review"
          value={pendingClaims.toString()}
          icon={<PendingIcon />}
          color="amber"
        />
        <StatCard
          title="High Risk"
          value={highRiskClaims.toString()}
          icon={<AlertIcon />}
          color="red"
        />
        <StatCard
          title="Total Value"
          value={`$${(totalAmount / 1000).toFixed(0)}K`}
          icon={<ValueIcon />}
          color="green"
        />
      </div>

      {/* Secondary Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Risk Overview */}
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Risk Overview</h3>
          <div className="space-y-4">
            <RiskBar label="High Risk (50+)" count={highRiskClaims} total={totalClaims} color="red" />
            <RiskBar
              label="Medium Risk (25-49)"
              count={claims.filter((c) => c.risk_score >= 25 && c.risk_score < 50).length}
              total={totalClaims}
              color="amber"
            />
            <RiskBar
              label="Low Risk (<25)"
              count={claims.filter((c) => c.risk_score < 25).length}
              total={totalClaims}
              color="green"
            />
          </div>
          <div className="mt-4 pt-4 border-t">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Average Risk Score</span>
              <span className="font-medium text-gray-900">{avgRiskScore}</span>
            </div>
          </div>
        </div>

        {/* Loss Type Breakdown */}
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Loss Type Breakdown</h3>
          <div className="space-y-3">
            {Object.entries(lossTypeStats)
              .sort((a, b) => b[1] - a[1])
              .map(([type, count]) => (
                <div key={type} className="flex items-center justify-between">
                  <span className="text-sm text-gray-700">{type}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-24 h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full"
                        style={{ width: `${(count / totalClaims) * 100}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium text-gray-900 w-8 text-right">{count}</span>
                  </div>
                </div>
              ))}
          </div>
        </div>
      </div>

      {/* Review Progress */}
      <div className="bg-white rounded-lg border p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Review Progress</h3>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-green-500 rounded-full transition-all"
                style={{ width: `${totalClaims > 0 ? (reviewedClaims / totalClaims) * 100 : 0}%` }}
              />
            </div>
          </div>
          <span className="text-sm font-medium text-gray-900">
            {reviewedClaims} / {totalClaims} reviewed
          </span>
        </div>
      </div>
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: string;
  icon: React.ReactNode;
  color: "blue" | "amber" | "red" | "green";
}

function StatCard({ title, value, icon, color }: StatCardProps) {
  const colorClasses = {
    blue: "bg-blue-50 text-blue-600",
    amber: "bg-amber-50 text-amber-600",
    red: "bg-red-50 text-red-600",
    green: "bg-green-50 text-green-600",
  };

  return (
    <div className="bg-white rounded-lg border p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-semibold text-gray-900 mt-1">{value}</p>
        </div>
        <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${colorClasses[color]}`}>
          {icon}
        </div>
      </div>
    </div>
  );
}

interface RiskBarProps {
  label: string;
  count: number;
  total: number;
  color: "red" | "amber" | "green";
}

function RiskBar({ label, count, total, color }: RiskBarProps) {
  const percentage = total > 0 ? (count / total) * 100 : 0;
  const colorClasses = {
    red: "bg-red-500",
    amber: "bg-amber-500",
    green: "bg-green-500",
  };

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-700">{label}</span>
        <span className="font-medium text-gray-900">{count}</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${colorClasses[color]}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

// Icons
function ClaimsIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  );
}

function PendingIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
  );
}

function ValueIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}
