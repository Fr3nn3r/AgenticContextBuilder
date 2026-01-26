import { Link } from "react-router-dom";

// Control framework requirements mapped to system capabilities
const AUDIT_REQUIREMENTS = [
  {
    id: "capture",
    name: "Decision Capture",
    description: "Universal logging of all AI decisions",
    status: "implemented",
    items: [
      { name: "Classification decisions", status: "complete", link: "/compliance/ledger?type=classification" },
      { name: "Extraction decisions", status: "complete", link: "/compliance/ledger?type=extraction" },
      { name: "Human reviews", status: "complete", link: "/compliance/ledger?type=human_review" },
      { name: "Override actions", status: "complete", link: "/compliance/ledger?type=override" },
    ],
  },
  {
    id: "integrity",
    name: "Tamper Evidence",
    description: "Append-only ledger with hash chain",
    status: "implemented",
    items: [
      { name: "Hash chain linking", status: "complete", link: "/compliance/verification" },
      { name: "Integrity verification", status: "complete", link: "/compliance/verification" },
      { name: "AES-256-GCM encryption", status: "available", link: null },
    ],
  },
  {
    id: "versioning",
    name: "Version Control",
    description: "Track exact versions for reproducibility",
    status: "implemented",
    items: [
      { name: "Git commit tracking", status: "complete", link: "/compliance/version-bundles" },
      { name: "Model version capture", status: "complete", link: "/compliance/version-bundles" },
      { name: "Prompt template hashing", status: "complete", link: "/compliance/version-bundles" },
      { name: "Extraction spec hashing", status: "complete", link: "/compliance/version-bundles" },
    ],
  },
  {
    id: "oversight",
    name: "Human Oversight",
    description: "Capture human actions and accountability",
    status: "implemented",
    items: [
      { name: "Review logging", status: "complete", link: "/compliance/ledger?type=human_review" },
      { name: "Override with reason", status: "complete", link: "/compliance/ledger?type=override" },
      { name: "Actor identification", status: "complete", link: "/compliance/ledger" },
    ],
  },
  {
    id: "access",
    name: "Access Control",
    description: "Role-based access to compliance data",
    status: "implemented",
    items: [
      { name: "Role definitions (admin/auditor/reviewer/operator)", status: "complete", link: "/admin" },
      { name: "Compliance endpoint protection", status: "complete", link: null },
      { name: "Session management", status: "complete", link: "/admin" },
    ],
  },
  {
    id: "export",
    name: "Evidence Export",
    description: "Export audit data for regulators",
    status: "planned",
    items: [
      { name: "Decision export (JSON/CSV)", status: "planned", link: null },
      { name: "Evidence pack generation", status: "planned", link: null },
      { name: "Bulk audit reports", status: "planned", link: null },
    ],
  },
];

export function ComplianceControls() {
  const implementedCount = AUDIT_REQUIREMENTS.filter((r) => r.status === "implemented").length;
  const totalCount = AUDIT_REQUIREMENTS.length;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Control Mapping</h1>
          <p className="text-muted-foreground mt-1">
            How True AIm maps to audit-first compliance requirements
          </p>
        </div>
        <Link
          to="/compliance"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Back to Overview
        </Link>
      </div>

      {/* Summary card */}
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center gap-6">
          <div className="w-24 h-24 rounded-full bg-green-500/10 flex items-center justify-center">
            <span className="text-3xl font-bold text-green-500">
              {Math.round((implementedCount / totalCount) * 100)}%
            </span>
          </div>
          <div>
            <h2 className="text-lg font-medium text-foreground">Audit-First Minimum</h2>
            <p className="text-muted-foreground mt-1">
              {implementedCount} of {totalCount} control categories implemented
            </p>
            <p className="text-sm text-muted-foreground mt-2">
              Core compliance infrastructure is in place. Export functionality is planned
              for post-demo implementation.
            </p>
          </div>
        </div>
      </div>

      {/* Control categories */}
      <div className="space-y-4">
        {AUDIT_REQUIREMENTS.map((requirement) => (
          <div
            key={requirement.id}
            className="bg-card border border-border rounded-lg overflow-hidden"
          >
            <div className="p-4 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-3">
                <StatusIcon status={requirement.status} />
                <div>
                  <h3 className="font-medium text-foreground">{requirement.name}</h3>
                  <p className="text-sm text-muted-foreground">{requirement.description}</p>
                </div>
              </div>
              <StatusBadge status={requirement.status} />
            </div>
            <div className="p-4">
              <ul className="space-y-2">
                {requirement.items.map((item, idx) => (
                  <li key={idx} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <ItemStatusIcon status={item.status} />
                      <span className="text-sm text-foreground">{item.name}</span>
                    </div>
                    {item.link ? (
                      <Link
                        to={item.link}
                        className="text-xs text-primary hover:underline"
                      >
                        View →
                      </Link>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        {item.status === "planned" ? "Coming soon" : "Config-based"}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ))}
      </div>

      {/* Demo talking points */}
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-6">
        <h3 className="font-medium text-foreground mb-4">Demo Talking Points</h3>
        <ul className="space-y-3 text-sm">
          <li className="flex items-start gap-2">
            <CheckIcon className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
            <span className="text-foreground">
              <strong>Tamper-evident audit trail</strong> - Every AI decision is logged with
              cryptographic hash chain linking. Modifications to past records break the chain.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <CheckIcon className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
            <span className="text-foreground">
              <strong>Full version traceability</strong> - We capture exact model versions,
              prompt templates, and extraction specs at decision time for reproducibility.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <CheckIcon className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
            <span className="text-foreground">
              <strong>Human oversight accountability</strong> - All human reviews and
              overrides are logged with actor identification and reasoning.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <CheckIcon className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
            <span className="text-foreground">
              <strong>Role-based access control</strong> - Only admin and auditor roles can
              access compliance data. All access is authenticated.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <ShieldIcon className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
            <span className="text-foreground">
              <strong>Encryption at rest</strong> - AES-256-GCM encryption is available for
              production deployments. Data is protected with envelope encryption.
            </span>
          </li>
        </ul>
      </div>
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (status === "implemented") {
    return (
      <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
        <CheckIcon className="w-5 h-5 text-green-500" />
      </div>
    );
  }
  return (
    <div className="w-10 h-10 rounded-lg bg-yellow-500/10 flex items-center justify-center">
      <ClockIcon className="w-5 h-5 text-yellow-500" />
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === "implemented") {
    return (
      <span className="px-2 py-1 text-xs font-medium rounded bg-green-500/10 text-green-500">
        Implemented
      </span>
    );
  }
  return (
    <span className="px-2 py-1 text-xs font-medium rounded bg-yellow-500/10 text-yellow-500">
      Planned
    </span>
  );
}

function ItemStatusIcon({ status }: { status: string }) {
  if (status === "complete") {
    return <CheckCircleIcon className="w-4 h-4 text-green-500" />;
  }
  if (status === "available") {
    return <CheckCircleIcon className="w-4 h-4 text-blue-500" />;
  }
  return <ClockIcon className="w-4 h-4 text-yellow-500" />;
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  );
}

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

function ShieldIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
      />
    </svg>
  );
}

export default ComplianceControls;
