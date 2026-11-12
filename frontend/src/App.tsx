import { useEffect, type ReactNode } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { RoleProvider } from './context/RoleContext';
import { useRole, type Role } from './context/RoleContext';
import Layout from './components/layout/Layout';
import ClientDashboard from './pages/client/ClientDashboard';
import NewAgreementWizard from './pages/client/NewAgreementWizard';
import ClientAgreementDetail from './pages/client/ClientAgreementDetail';
import ProviderDashboard from './pages/provider/ProviderDashboard';
import ProviderAgreementDetail from './pages/provider/ProviderAgreementDetail';
import LandingPage from './pages/LandingPage';
import ClientPaywallAssistant from './pages/client/ClientPaywallAssistant';

const paywallAssistantEnabled = import.meta.env.VITE_ENABLE_PAYWALL_ASSISTANT === 'true';

function RoleGuard({ role, children }: { role: Role; children: ReactNode }) {
  const { role: activeRole, setRole } = useRole();
  const location = useLocation();
  useEffect(() => {
    if (activeRole && activeRole !== role) setRole(null);
  }, [activeRole, role, setRole]);
  if (activeRole !== role) {
    return (
      <Navigate
        to="/"
        replace
        state={{ from: location.pathname, chooseRoleMessage: 'Choose your role to enter the matching workspace.' }}
      />
    );
  }
  return children;
}

function App() {
  return (
    <RoleProvider>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route element={<RoleGuard role="client"><Layout /></RoleGuard>}>
          {/* Client Routes */}
          <Route path="/client" element={<ClientDashboard />} />
          <Route path="/client/new" element={<NewAgreementWizard />} />
          <Route
            path="/client/paywall"
            element={paywallAssistantEnabled
              ? <ClientPaywallAssistant />
              : <Navigate to="/client" replace />}
          />
          <Route path="/client/agreements/:id" element={<ClientAgreementDetail />} />
        </Route>
        <Route element={<RoleGuard role="provider"><Layout /></RoleGuard>}>
          {/* Provider Routes */}
          <Route path="/provider" element={<ProviderDashboard />} />
          <Route path="/provider/agreements/:id" element={<ProviderAgreementDetail />} />
        </Route>
        <Route
          path="/client/*"
          element={<RoleGuard role="client"><Navigate to="/client" replace /></RoleGuard>}
        />
        <Route
          path="/provider/*"
          element={<RoleGuard role="provider"><Navigate to="/provider" replace /></RoleGuard>}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </RoleProvider>
  );
}

export default App;
