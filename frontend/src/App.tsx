import { Routes, Route, Navigate } from 'react-router-dom';
import { RoleProvider } from './context/RoleContext';
import Layout from './components/layout/Layout';
import ClientDashboard from './pages/client/ClientDashboard';
import NewAgreementWizard from './pages/client/NewAgreementWizard';
import ClientAgreementDetail from './pages/client/ClientAgreementDetail';
import ProviderDashboard from './pages/provider/ProviderDashboard';
import ProviderAgreementDetail from './pages/provider/ProviderAgreementDetail';
import LandingPage from './pages/LandingPage';

function App() {
  return (
    <RoleProvider>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route element={<Layout />}>
          {/* Client Routes */}
          <Route path="/client" element={<ClientDashboard />} />
          <Route path="/client/new" element={<NewAgreementWizard />} />
          <Route path="/client/agreements/:id" element={<ClientAgreementDetail />} />

          {/* Provider Routes */}
          <Route path="/provider" element={<ProviderDashboard />} />
          <Route path="/provider/agreements/:id" element={<ProviderAgreementDetail />} />

          {/* Default redirect */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </RoleProvider>
  );
}

export default App;
