// One place for success and error text so every page announces changes the same way to assistive technology.
export function Notice({ kind, children }: { kind: "success" | "error"; children: React.ReactNode }) {
  if (kind === "error") {
    return (
      <div role="alert" className="rounded-sm border-2 border-status-rejected bg-white p-3 text-sm text-status-rejected">
        {children}
      </div>
    );
  }
  return (
    <div role="status" className="rounded-sm border-2 border-status-approved bg-white p-3 text-sm text-status-approved">
      {children}
    </div>
  );
}
