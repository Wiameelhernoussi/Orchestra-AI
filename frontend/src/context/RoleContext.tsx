import { createContext, useContext, useState, ReactNode } from 'react';

type Role = 'client' | 'provider';

interface UserInfo {
  id: string;
  name: string;
  role: Role;
  orgName: string;
}

const DEMO_USERS: Record<Role, UserInfo> = {
  client: {
    id: 'client-user-001',
    name: 'Alice Chen',
    role: 'client',
    orgName: 'ShopFlow Inc',
  },
  provider: {
    id: 'provider-user-001',
    name: 'Bob Martinez',
    role: 'provider',
    orgName: 'DevStudio Agency',
  },
};

interface RoleContextType {
  role: Role;
  user: UserInfo;
  switchRole: () => void;
}

const RoleContext = createContext<RoleContextType | null>(null);

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<Role>('client');

  const switchRole = () => {
    setRole((prev) => (prev === 'client' ? 'provider' : 'client'));
  };

  return (
    <RoleContext.Provider value={{ role, user: DEMO_USERS[role], switchRole }}>
      {children}
    </RoleContext.Provider>
  );
}

export function useRole(): RoleContextType {
  const ctx = useContext(RoleContext);
  if (!ctx) throw new Error('useRole must be used within RoleProvider');
  return ctx;
}

