const ACTORS = ['AI', 'Provider', 'Client', 'System', 'PayPal'] as const;

const PERMISSIONS: {
  action: string;
  actors: Partial<Record<(typeof ACTORS)[number], string>>;
}[] = [
  {
    action: 'Structure the request',
    actors: { Client: 'Supplies request', AI: 'Structures intent', System: 'Runs agent' },
  },
  {
    action: 'Create agreement proposal',
    actors: { Client: 'Submits proposal', System: 'Stores proposal' },
  },
  { action: 'Submit evidence', actors: { Provider: 'Submits', System: 'Stores submission' } },
  { action: 'Analyze evidence', actors: { AI: 'Advisory only', System: 'Runs and stores advisory' } },
  { action: 'Request revision', actors: { Client: 'Requests', System: 'Records request' } },
  { action: 'Approve work', actors: { Client: 'Human decision', System: 'Records decision' } },
  {
    action: 'Create invoice',
    actors: { Client: 'Requests', System: 'Creates after recorded client approval' },
  },
  {
    action: 'Authorize payment',
    actors: { Client: 'Pays invoice', PayPal: 'Processes payment' },
  },
  {
    action: 'Generate payment QR',
    actors: { Client: 'Requests display', System: 'Restricts to invoice client', PayPal: 'Generates code' },
  },
  {
    action: 'Send payment reminder',
    actors: { Provider: 'Requests reminder', System: 'Rate limits and audits', PayPal: 'Sends reminder' },
  },
  {
    action: 'Confirm payment',
    actors: { System: 'Records verified status', PayPal: 'Reports status / webhook' },
  },
];

export function PermissionMatrix() {
  return (
    <section className="landing-section permission-section" aria-labelledby="permission-heading">
      <details className="permission-matrix-details">
        <summary id="permission-heading">
          <span>Permissions</span>
          <span className="permission-visual" aria-label="AI advises, people decide, system enforces, PayPal processes">
            <span className="permission-visual-ai">AI advises</span>
            <span className="permission-visual-people">People decide</span>
            <span className="permission-visual-system">System enforces gates</span>
            <span className="permission-visual-paypal">PayPal processes</span>
          </span>
          <span className="permission-expand-label">View full matrix</span>
        </summary>
        <div className="permission-matrix-scroll">
          <table className="permission-matrix" aria-label="Permission matrix: actions and responsible actors">
            <thead>
              <tr>
                <th scope="col">Action</th>
                {ACTORS.map((actor) => <th scope="col" key={actor}>{actor}</th>)}
              </tr>
            </thead>
            <tbody>
              {PERMISSIONS.map(({ action, actors }) => (
                <tr key={action}>
                  <th scope="row">{action}</th>
                  {ACTORS.map((actor) => (
                    <td key={actor} className={actors[actor] ? `permission-${actor.toLowerCase()}` : 'permission-empty'}>
                      {actors[actor] ?? '—'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="permission-note">
          Invoices require recorded client approval. AI never approves, creates invoices, or confirms payment.
          QR display is client-only; reminders are provider-only and rate limited.
        </p>
      </details>
    </section>
  );
}
