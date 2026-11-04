export function NextStep({ children }: { children: string }) {
  return (
    <aside className="next-step">
      <span className="next-step-icon" aria-hidden="true">→</span>
      <p><strong>Next step</strong>{children}</p>
    </aside>
  );
}
