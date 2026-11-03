import { useParams } from 'react-router-dom';

function ProviderAgreementDetail() {
  const { id } = useParams();

  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 24 }}>Agreement Detail</h1>
      <div
        style={{
          background: 'white',
          borderRadius: 12,
          padding: 32,
          border: '1px solid #e0e0e0',
          color: '#666',
        }}
      >
        <p>Agreement ID: <code>{id}</code></p>
        <p>Agreement terms, milestone progress, evidence submission, and payment status will appear here.</p>
      </div>
    </div>
  );
}

export default ProviderAgreementDetail;

