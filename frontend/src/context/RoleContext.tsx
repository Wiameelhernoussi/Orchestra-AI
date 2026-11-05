import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { api } from '../api';

type Role = 'client' | 'provider';

interface UserInfo {
  id: string;
  name: string;
  role: Role;
  orgName: string;
}

const DEMO_USERS: Record<Role, UserInfo> = {
  client: {
    id: 'demo-client',
    name: 'Alice Chen',
    role: 'client',
    orgName: 'ShopFlow Inc',
  },
  provider: {
    id: 'demo-provider',
    name: 'Bob Martinez',
    role: 'provider',
    orgName: 'DevStudio Agency',
  },
};

interface RoleContextType {
  role: Role;
  user: UserInfo;
  setRole: (role: Role) => void;
  demoMode: 'mock' | 'real';
  demoModeError: string;
}

const RoleContext = createContext<RoleContextType | null>(null);

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<Role>(() =>
    window.location.pathname.startsWith('/provider') ? 'provider' : 'client',
  );
  const [demoMode, setDemoMode] = useState<'mock' | 'real'>('real');
  const [demoModeError, setDemoModeError] = useState('');

  useEffect(() => {
    let active = true;
    api.health()
      .then(({ demo_mode: mode }) => {
        if (active) {
          setDemoMode(mode);
          setDemoModeError('');
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setDemoModeError(error instanceof Error ? error.message : 'Demo mode could not be loaded.');
        }
      });
    return () => { active = false; };
  }, []);

  return (
    <RoleContext.Provider value={{ role, user: DEMO_USERS[role], setRole, demoMode, demoModeError }}>
      {children}
    </RoleContext.Provider>
  );
}

export function useRole(): RoleContextType {
  const ctx = useContext(RoleContext);
  if (!ctx) throw new Error('useRole must be used within RoleProvider');
  return ctx;
}
