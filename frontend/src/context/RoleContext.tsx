import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { api } from '../api';

export type Role = 'client' | 'provider';

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
  role: Role | null;
  user: UserInfo;
  setRole: (role: Role | null) => void;
  demoMode: 'mock' | 'real' | 'loading' | 'unavailable';
  demoModeError: string;
}

const RoleContext = createContext<RoleContextType | null>(null);

function storedRole(search: string): Role | null {
  const queryRole = new URLSearchParams(search).get('demoRole');
  if (queryRole === 'client' || queryRole === 'provider') return queryRole;
  const role = window.sessionStorage.getItem('orchestra.demo.role');
  return role === 'client' || role === 'provider' ? role : null;
}

export function RoleProvider({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [role, setRoleState] = useState<Role | null>(() => storedRole(location.search));
  const [demoMode, setDemoMode] = useState<'mock' | 'real' | 'loading' | 'unavailable'>('loading');
  const [demoModeError, setDemoModeError] = useState('');

  useEffect(() => {
    if (role) window.sessionStorage.setItem('orchestra.demo.role', role);
  }, [role]);

  const setRole = useCallback((nextRole: Role | null) => {
    if (nextRole) window.sessionStorage.setItem('orchestra.demo.role', nextRole);
    else window.sessionStorage.removeItem('orchestra.demo.role');
    setRoleState(nextRole);
  }, []);

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
          setDemoMode('unavailable');
          setDemoModeError(error instanceof Error ? error.message : 'Demo mode could not be loaded.');
        }
      });
    return () => { active = false; };
  }, []);

  return (
    <RoleContext.Provider value={{ role, user: DEMO_USERS[role ?? 'client'], setRole, demoMode, demoModeError }}>
      {children}
    </RoleContext.Provider>
  );
}

export function useRole(): RoleContextType {
  const ctx = useContext(RoleContext);
  if (!ctx) throw new Error('useRole must be used within RoleProvider');
  return ctx;
}
