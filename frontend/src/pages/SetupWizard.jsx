import { useState, useEffect, useCallback } from 'react';
import {
  Stepper, Button, Group, Text, Paper, Stack, Progress,
  ThemeIcon, Center, Title, Badge, Loader, Alert, Card,
  RingProgress,
} from '@mantine/core';
import {
  IconUpload, IconDatabase, IconDownload, IconCalculator,
  IconCheck, IconX, IconAlertCircle, IconChartBar, IconRocket,
} from '@tabler/icons-react';
import {
  loadMaster, loadTri, fetchNavs, computeMetrics,
  getTaskStatus, stopTask,
} from '../api/client';

const STEPS = [
  { label: 'Load Fund Master', desc: 'Import funds from Excel & map benchmarks', icon: IconUpload, task: 'load_master' },
  { label: 'Load TRI Data', desc: 'Import benchmark TRI CSV files', icon: IconDatabase, task: 'load_tri' },
  { label: 'Fetch NAV Data', desc: 'Download NAV history from AMFI API', icon: IconDownload, task: 'fetch_navs' },
  { label: 'Compute Metrics', desc: 'Calculate Sharpe, Sortino, Alpha & more', icon: IconCalculator, task: 'compute_metrics' },
];

export default function SetupWizard({ onComplete }) {
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState({});
  const [error, setError] = useState(null);
  const [polling, setPolling] = useState(false);

  const pollStatus = useCallback(async (task) => {
    setPolling(true);
    const poll = async () => {
      try {
        const { data } = await getTaskStatus(task);
        setStatus(prev => ({ ...prev, [task]: data }));

        if (data.status === 'running') {
          setTimeout(poll, 2000);
        } else {
          setPolling(false);
          setLoading(false);
          if (data.status === 'completed') {
            setActive(prev => prev + 1);
          }
        }
      } catch {
        setTimeout(poll, 3000);
      }
    };
    poll();
  }, []);

  async function runStep(stepIndex) {
    setLoading(true);
    setError(null);
    const step = STEPS[stepIndex];

    try {
      switch (step.task) {
        case 'load_master':
          await loadMaster();
          const { data: masterData } = await getTaskStatus('load_master');
          setStatus(prev => ({ ...prev, load_master: masterData }));
          setLoading(false);
          setActive(1);
          break;
        case 'load_tri':
          await loadTri();
          const { data: triData } = await getTaskStatus('load_tri');
          setStatus(prev => ({ ...prev, load_tri: triData }));
          setLoading(false);
          setActive(2);
          break;
        case 'fetch_navs':
          await fetchNavs();
          pollStatus('fetch_navs');
          break;
        case 'compute_metrics':
          await computeMetrics();
          pollStatus('compute_metrics');
          break;
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'An error occurred');
      setLoading(false);
    }
  }

  function getProgress(task) {
    const s = status[task];
    if (!s || s.total_items === 0) return 0;
    return Math.round((s.completed_items / s.total_items) * 100);
  }

  return (
    <Center h="100vh" style={{ background: 'linear-gradient(135deg, #0f0c29, #302b63, #24243e)' }}>
      <Paper
        shadow="xl"
        p="xl"
        radius="lg"
        w={700}
        style={{
          background: 'rgba(30, 30, 50, 0.9)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <Stack gap="lg">
          <Group justify="center" gap="sm" mb="sm">
            <ThemeIcon size={48} radius="xl" variant="gradient" gradient={{ from: 'indigo', to: 'violet' }}>
              <IconChartBar size={28} />
            </ThemeIcon>
          </Group>
          <Title order={2} ta="center" c="white">MF Analysis Setup</Title>
          <Text ta="center" c="dimmed" size="sm">
            Let's set up your mutual fund analysis database. This is a one-time process.
          </Text>

          <Stepper active={active} color="indigo" size="sm" mt="md">
            {STEPS.map((step, i) => {
              const StepIcon = step.icon;
              return (
                <Stepper.Step
                  key={i}
                  label={step.label}
                  description={step.desc}
                  icon={<StepIcon size={18} />}
                  loading={loading && active === i}
                  color={status[step.task]?.status === 'failed' ? 'red' : 'indigo'}
                />
              );
            })}
          </Stepper>

          {error && (
            <Alert color="red" icon={<IconAlertCircle size={16} />} title="Error" variant="light">
              {error}
            </Alert>
          )}

          {/* Progress for long-running tasks */}
          {polling && status[STEPS[active]?.task] && (
            <Card p="md" radius="md" style={{ background: 'rgba(255,255,255,0.03)' }}>
              <Stack gap="xs">
                <Group justify="space-between">
                  <Text size="sm" c="dimmed">{STEPS[active].label}</Text>
                  <Badge color={status[STEPS[active].task].status === 'stopping' ? 'orange' : 'blue'} variant="light" size="sm">
                    {status[STEPS[active].task].status === 'stopping' ? 'Stopping...' : `${status[STEPS[active].task].completed_items} / ${status[STEPS[active].task].total_items}`}
                  </Badge>
                </Group>
                <Progress
                  value={getProgress(STEPS[active].task)}
                  color={status[STEPS[active].task].status === 'stopping' ? 'orange' : 'indigo'}
                  size="lg"
                  radius="xl"
                  animated
                />
                <Group justify="space-between" align="center">
                  <Text size="xs" c="red">
                    {status[STEPS[active].task].failed_items > 0 ? `${status[STEPS[active].task].failed_items} failed` : ''}
                  </Text>
                  <Button 
                    size="compact-xs" 
                    variant="subtle" 
                    color="red" 
                    onClick={() => stopTask(STEPS[active].task)}
                    disabled={status[STEPS[active].task].status === 'stopping'}
                  >
                    Stop Task
                  </Button>
                </Group>
              </Stack>
            </Card>
          )}

          {/* Result cards for completed steps */}
          {status.load_master?.status === 'completed' && active > 0 && (
            <Card p="sm" radius="md" style={{ background: 'rgba(18, 184, 134, 0.08)', border: '1px solid rgba(18, 184, 134, 0.2)' }}>
              <Group gap="xs">
                <IconCheck size={16} color="#12b886" />
                <Text size="xs" c="teal">
                  {status.load_master.completed_items} funds loaded, benchmarks mapped
                </Text>
              </Group>
            </Card>
          )}

          {(() => {
            const ActiveIcon = active < STEPS.length ? STEPS[active].icon : null;
            return (
              <Group justify="center" mt="md">
                {active < STEPS.length ? (
                  <Button
                    size="md"
                    radius="xl"
                    variant="gradient"
                    gradient={{ from: 'indigo', to: 'violet' }}
                    onClick={() => runStep(active)}
                    loading={loading}
                    disabled={polling}
                    leftSection={ActiveIcon ? <ActiveIcon size={18} /> : null}
                  >
                    {STEPS[active].label}
                  </Button>
                ) : (
                  <Button
                    size="md"
                    radius="xl"
                    variant="gradient"
                    gradient={{ from: 'teal', to: 'green' }}
                    onClick={onComplete}
                    leftSection={<IconRocket size={18} />}
                  >
                    Launch Dashboard
                  </Button>
                )}

                {active > 0 && active < STEPS.length && !loading && (
                  <Button
                    size="md"
                    radius="xl"
                    variant="subtle"
                    color="gray"
                    onClick={() => onComplete()}
                  >
                    Skip & Continue Later
                  </Button>
                )}
              </Group>
            );
          })()}
        </Stack>
      </Paper>
    </Center>
  );
}
