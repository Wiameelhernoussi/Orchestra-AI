function ProviderDashboard() {
  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 24 }}>Provider Dashboard</h1>

      <div
        style={{
          background: 'white',
          borderRadius: 12,
          padding: 32,
          textAlign: 'center',
          color: '#666',
          border: '1px solid #e0e0e0',
        }}
      >
        <p style={{ fontSize: 48, margin: '0 0 16px' }}>🔨</p>
        <h3 style={{ margin: '0 0 8px' }}>No active agreements</h3>
        <p>Agreements proposed by clients will appear here for your review.</p>
      </div>
    </div>
  );
}

export default ProviderDashboard;

