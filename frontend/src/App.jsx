import { useState, useEffect } from 'react';
import { Routes, Route, NavLink, useLocation } from 'react-router-dom';
import {
  AppShell, Group, Text, UnstyledButton, Stack, ThemeIcon, Badge,
  useMantineColorScheme, ActionIcon, Tooltip, Loader, Center,
} from '@mantine/core';
import {
  IconDashboard, IconTable, IconChartBar, IconScale,
  IconSettings, IconDatabase, IconSun, IconMoon,
  IconRefresh, IconWand,
} from '@tabler/icons-react';

import DashboardPage from './pages/DashboardPage';
import MetricsPage from './pages/MetricsPage';
import FundDetailPage from './pages/FundDetailPage';
import ComparisonPage from './pages/ComparisonPage';
import BenchmarkPage from './pages/BenchmarkPage';
import SettingsPage from './pages/SettingsPage';
import SetupWizard from './pages/SetupWizard';
import { healthCheck, getIngestionStatus } from './api/client';

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: IconDashboard },
  { path: '/metrics', label: 'Fund Explorer', icon: IconTable },
  { path: '/compare', label: 'Compare', icon: IconScale },
  { path: '/benchmarks', label: 'Benchmarks', icon: IconDatabase },
  { path: '/settings', label: 'Settings', icon: IconSettings },
];

function NavItem({ item, active }) {
  return (
    <UnstyledButton
      component={NavLink}
      to={item.path}
      style={(theme) => ({
        display: 'block',
        width: '100%',
        padding: '10px 16px',
        borderRadius: 8,
        borderLeft: active ? '3px solid var(--mantine-color-indigo-6)' : '3px solid transparent',
        backgroundColor: active ? 'rgba(99, 102, 241, 0.12)' : 'transparent',
        color: active ? 'var(--mantine-color-indigo-4)' : 'var(--mantine-color-dimmed)',
        transition: 'all 0.15s ease',
        textDecoration: 'none',
        '&:hover': {
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
        },
      })}
    >
      <Group gap="sm">
        <ThemeIcon variant="subtle" color={active ? 'indigo' : 'gray'} size="md">
          <item.icon size={18} />
        </ThemeIcon>
        <Text size="sm" fw={active ? 600 : 400}>{item.label}</Text>
      </Group>
    </UnstyledButton>
  );
}

export default function App() {
  const location = useLocation();
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();
  const [needsSetup, setNeedsSetup] = useState(null); // null = loading, true/false
  const [backendReady, setBackendReady] = useState(false);

  useEffect(() => {
    checkBackendAndSetup();
  }, []);

  async function checkBackendAndSetup() {
    try {
      await healthCheck();
      setBackendReady(true);

      const { data } = await getIngestionStatus();
      const masterStatus = data.find(s => s.task_name === 'load_master');
      if (!masterStatus || masterStatus.status !== 'completed') {
        setNeedsSetup(true);
      } else {
        setNeedsSetup(false);
      }
    } catch {
      // Backend not ready yet, retry
      setTimeout(checkBackendAndSetup, 2000);
    }
  }

  if (!backendReady) {
    return (
      <Center h="100vh" style={{ background: 'var(--mantine-color-dark-9)' }}>
        <Stack align="center" gap="md">
          <Loader size="lg" color="indigo" />
          <Text c="dimmed" size="sm">Connecting to backend...</Text>
        </Stack>
      </Center>
    );
  }

  if (needsSetup === null) {
    return (
      <Center h="100vh" style={{ background: 'var(--mantine-color-dark-9)' }}>
        <Loader size="lg" color="indigo" />
      </Center>
    );
  }

  if (needsSetup) {
    return <SetupWizard onComplete={() => setNeedsSetup(false)} />;
  }

  return (
    <AppShell
      navbar={{ width: 240, breakpoint: 'sm' }}
      padding="lg"
    >
      <AppShell.Navbar p="md" style={{
        background: 'rgba(20, 20, 30, 0.95)',
        backdropFilter: 'blur(10px)',
        borderRight: '1px solid rgba(255,255,255,0.06)',
      }}>
        <AppShell.Section>
          <Group justify="space-between" mb="xl" px="xs">
            <Group gap="xs">
              <ThemeIcon size="lg" radius="md" variant="gradient" gradient={{ from: 'indigo', to: 'violet' }}>
                <IconChartBar size={20} />
              </ThemeIcon>
              <div>
                <Text size="sm" fw={700} lh={1}>MF Analysis</Text>
                <Text size="xs" c="dimmed" lh={1.2}>Portfolio Intelligence</Text>
              </div>
            </Group>
            <Tooltip label={colorScheme === 'dark' ? 'Light mode' : 'Dark mode'}>
              <ActionIcon variant="subtle" onClick={toggleColorScheme} size="md">
                {colorScheme === 'dark' ? <IconSun size={16} /> : <IconMoon size={16} />}
              </ActionIcon>
            </Tooltip>
          </Group>
        </AppShell.Section>

        <AppShell.Section grow>
          <Stack gap={4}>
            {NAV_ITEMS.map((item) => (
              <NavItem
                key={item.path}
                item={item}
                active={location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path))}
              />
            ))}
          </Stack>
        </AppShell.Section>

        <AppShell.Section>
          <Text size="xs" c="dimmed" ta="center" py="sm">
            v1.0 • Powered by FastAPI + Mantine
          </Text>
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main style={{ background: 'var(--mantine-color-dark-9)' }}>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/metrics" element={<MetricsPage />} />
          <Route path="/funds/:id" element={<FundDetailPage />} />
          <Route path="/compare" element={<ComparisonPage />} />
          <Route path="/benchmarks" element={<BenchmarkPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </AppShell.Main>
    </AppShell>
  );
}
