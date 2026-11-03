function NewAgreementWizard() {
  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 24 }}>New Agreement</h1>

      <div
        style={{
          background: 'white',
          borderRadius: 12,
          padding: 32,
          border: '1px solid #e0e0e0',
        }}
      >
        <h3 style={{ margin: '0 0 8px' }}>Describe your project</h3>
        <p style={{ color: '#666', margin: '0 0 16px' }}>
          Tell us what you need in plain language. Our AI will structure it into
          milestones with deliverables and acceptance criteria.
        </p>

        <textarea
          placeholder="Example: I need a modern e-commerce website for my boutique clothing store. Budget around $600. Need design mockups first, then development, then final deployment..."
          style={{
            width: '100%',
            minHeight: 120,
            padding: 12,
            borderRadius: 8,
            border: '1px solid #d0d0d0',
            fontSize: 14,
            fontFamily: 'inherit',
            resize: 'vertical',
            boxSizing: 'border-box',
          }}
        />

        <button
          style={{
            marginTop: 16,
            background: '#0070ba',
            color: 'white',
            border: 'none',
            padding: '12px 24px',
            borderRadius: 8,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          🤖 Analyze with AI
        </button>

        <p style={{ fontSize: 12, color: '#999', marginTop: 12 }}>
          The AI will propose milestones and highlight any missing information.
          You will review and edit everything before sending.
        </p>
      </div>
    </div>
  );
}

export default NewAgreementWizard;

