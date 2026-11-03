
import { Link } from 'react-router-dom';

function ClientDashboard() {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 24 }}>Client Dashboard</h1>
        <Link
          to="/client/new"
          style={{
            background: '#0070ba',
            color: 'white',
            padding: '10px 20px',
            borderRadius: 8,
            textDecoration: 'none',
            fontWeight: 600,
            fontSize: 14,
          }}
        >
          + New Agreement
        </Link>
      </div>

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
        <p style={{ fontSize: 48, margin: '0 0 16px' }}>📋</p>
        <h3 style={{ margin: '0 0 8px' }}>No agreements yet</h3>
        <p>Create your first agreement to get started with Orchestra AI.</p>
      </div>
    </div>
  );
}

export default ClientDashboard;

