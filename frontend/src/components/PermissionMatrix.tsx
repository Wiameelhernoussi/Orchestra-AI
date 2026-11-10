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
    action: 'Confirm payment',
    actors: { System: 'Records verified status', PayPal: 'Reports status / webhook' },
  },
];

export function PermissionMatrix() {
  return (
    <section className="landing-section permission-section" aria-labelledby="permission-heading">
      <div className="section-heading-landing">
        <div>
          <p className="landing-eyebrow dark-eyebrow">CLEAR RESPONSIBILITIES</p>
          <h2 id="permission-heading">Who does what</h2>
        </div>
        <p>AI advises; people make the decisions; the server enforces the payment gates.</p>
      </div>
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
        Invoice creation is a server-side step and requires recorded client approval. The AI never approves work,
        creates invoices, or confirms payment.
      </p>
    </section>
  );
}
