import { useState, useEffect } from 'react';
import {
  Title, Text, Stack, Card, Group, TextInput, Button, Badge,
  NumberInput, Alert, Divider, SimpleGrid, Progress, Checkbox,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconSettings, IconCheck, IconRefresh, IconAlertCircle,
  IconDatabase, IconDownload, IconCalculator,
} from '@tabler/icons-react';
import {
  getConfig, updateConfig, getIngestionStatus,
  loadMaster, loadTri, fetchNavs, computeMetrics, getTaskStatus, stopTask,
} from '../api/client';

export default function SettingsPage() {
  const [configs, setConfigs] = useState([]);
  const [riskFreeRate, setRiskFreeRate] = useState(6.0);
  const [statuses, setStatuses] = useState([]);
  const [loading, setLoading] = useState({});
  const [polling, setPolling] = useState({});
  const [forceNav, setForceNav] = useState(false);
  const [forceMetrics, setForceMetrics] = useState(false);

  useEffect(() => {
    loadData();
    const interval = setInterval(refreshStatuses, 5000);
    return () => clearInterval(interval);
  }, []);

  async function loadData() {
    try {
      const [cfgRes, statusRes] = await Promise.all([
        getConfig(),
        getIngestionStatus(),
      ]);
      setConfigs(cfgRes.data);
      setStatuses(statusRes.data);
      const rfr = cfgRes.data.find(c => c.key === 'risk_free_rate');
      if (rfr) setRiskFreeRate(parseFloat(rfr.value));
    } catch {}
  }

  async function refreshStatuses() {
    try {
      const { data } = await getIngestionStatus();
      setStatuses(data);
    } catch {}
  }

  async function saveRiskFreeRate() {
    try {
      await updateConfig('risk_free_rate', String(riskFreeRate));
      notifications.show({
        title: 'Saved',
        message: `Risk-free rate updated to ${riskFreeRate}%`,
        color: 'teal',
        icon: <IconCheck size={16} />,
      });
    } catch {
      notifications.show({
        title: 'Error',
        message: 'Failed to save',
        color: 'red',
      });
    }
  }

  async function runTask(taskKey, apiFn) {
    setLoading(prev => ({ ...prev, [taskKey]: true }));
    try {
      await apiFn();
      notifications.show({
        title: 'Started',
        message: `${taskKey} is running...`,
        color: 'blue',
      });
      // Poll for this task
      const poll = async () => {
        try {
          const { data } = await getTaskStatus(taskKey);
          setStatuses(prev => {
            const idx = prev.findIndex(s => s.task_name === taskKey);
            if (idx >= 0) {
              const newArr = [...prev];
              newArr[idx] = data;
              return newArr;
            }
            return [...prev, data];
          });
          if (data.status === 'running' || data.status === 'stopping') {
            setTimeout(poll, 2000);
          } else {
            setLoading(prev => ({ ...prev, [taskKey]: false }));
            if (data.status === 'completed') {
              notifications.show({ title: 'Success', message: `${taskKey} completed!`, color: 'teal' });
            }
          }
        } catch {
          setLoading(prev => ({ ...prev, [taskKey]: false }));
        }
      };
      setTimeout(poll, 2000);
    } catch {
      setLoading(prev => ({ ...prev, [taskKey]: false }));
    }
  }

  function getStatus(taskName) {
    return statuses.find(s => s.task_name === taskName);
  }

  async function handleStop(taskKey) {
    try {
      await stopTask(taskKey);
      notifications.show({
        title: 'Stopping',
        message: `${taskKey} signaled to stop...`,
        color: 'orange',
      });
    } catch (err) {
      notifications.show({
        title: 'Stop failed',
        message: err.response?.data?.message || 'The task may have finished already.',
        color: 'red',
      });
    }
  }

  function TaskCard({ title, desc, taskKey, apiFn, icon: Icon }) {
    const status = getStatus(taskKey);
    const isRunning = loading[taskKey] || status?.status === 'running';
    const isStopping = status?.status === 'stopping';
    const progress = status?.total_items > 0
      ? Math.round((status.completed_items / status.total_items) * 100)
      : 0;

    return (
      <Card p="lg" radius="md" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
        <Group justify="space-between" mb="sm">
          <Group gap="sm">
            <Icon size={18} />
            <div>
              <Text fw={600} size="sm">{title}</Text>
              <Text size="xs" c="dimmed">{desc}</Text>
            </div>
          </Group>
          {status?.status && (
            <Badge
              color={status.status === 'completed' ? 'teal' : (status.status === 'running' || status.status === 'stopping') ? 'blue' : (status.status === 'failed' || status.status === 'stopped') ? 'red' : 'gray'}
              variant="light"
              size="sm"
            >
              {status.status}
            </Badge>
          )}
        </Group>

        {(isRunning || isStopping) && status?.total_items > 0 && (
          <Stack gap={4} mb="sm">
            <Progress value={progress} color={isStopping ? 'orange' : 'indigo'} size="sm" animated />
            <Text size="xs" c="dimmed">
              {status.completed_items} / {status.total_items} completed
              {status.failed_items > 0 && ` • ${status.failed_items} failed`}
            </Text>
          </Stack>
        )}
        {!isRunning && !isStopping && status?.failed_items > 0 && status?.error_message && (
          <Alert color="red" title="Failures Detected" mb="sm" p="xs">
            <Text size="xs">{status.error_message}</Text>
          </Alert>
        )}

        <Group gap="xs">
          <Button
            size="xs"
            variant="light"
            onClick={() => runTask(taskKey, 
              taskKey === 'fetch_navs' ? () => apiFn(forceNav) : 
              taskKey === 'compute_metrics' ? () => apiFn(forceMetrics) : apiFn
            )}
            loading={isRunning && !isStopping}
            disabled={isStopping}
            leftSection={<IconRefresh size={14} />}
          >
            {status?.status === 'completed' ? 'Re-run' : (status?.status === 'failed' || status?.status === 'stopped') ? 'Restart' : 'Run'}
          </Button>
          
          {(taskKey === 'fetch_navs' || taskKey === 'compute_metrics') && !isRunning && (
            <Checkbox 
              label="Full Refresh" 
              size="xs" 
              checked={taskKey === 'fetch_navs' ? forceNav : forceMetrics} 
              onChange={(e) => taskKey === 'fetch_navs' ? setForceNav(e.currentTarget.checked) : setForceMetrics(e.currentTarget.checked)}
              disabled={isRunning || isStopping}
            />
          )}

          {(isRunning || isStopping) && (
            <Button
              size="xs"
              variant="subtle"
              color="red"
              onClick={() => handleStop(taskKey)}
              disabled={isStopping}
            >
              {isStopping ? 'Stopping...' : 'Stop'}
            </Button>
          )}
        </Group>
      </Card>
    );
  }

  return (
    <Stack gap="lg">
      <Title order={2} c="white">Settings</Title>

      {/* System Properties */}
      <Card p="lg" radius="md" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
        <Text fw={600} mb="md" c="white">System Properties</Text>
        <Group gap="md">
          <NumberInput
            label="Risk-Free Rate (% p.a.)"
            description="Used for Sharpe, Sortino, and Alpha calculations"
            value={riskFreeRate}
            onChange={setRiskFreeRate}
            min={0}
            max={20}
            step={0.5}
            decimalScale={2}
            w={300}
            size="sm"
          />
          <Button
            mt={24}
            size="sm"
            onClick={saveRiskFreeRate}
            leftSection={<IconCheck size={14} />}
          >
            Save
          </Button>
        </Group>
      </Card>

      {/* Data Pipeline */}
      <Text fw={600} c="white" mt="sm">Data Pipeline</Text>
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
        <TaskCard
          title="Load Fund Master"
          desc="Import from Excel & map benchmarks"
          taskKey="load_master"
          apiFn={loadMaster}
          icon={IconDatabase}
        />
        <TaskCard
          title="Load TRI Data"
          desc="Import benchmark TRI CSV files"
          taskKey="load_tri"
          apiFn={loadTri}
          icon={IconDatabase}
        />
        <TaskCard
          title="Fetch NAV Data"
          desc="Download NAV history from AMFI API"
          taskKey="fetch_navs"
          apiFn={fetchNavs}
          icon={IconDownload}
        />
        <TaskCard
          title="Compute Metrics"
          desc="Calculate all financial ratios"
          taskKey="compute_metrics"
          apiFn={computeMetrics}
          icon={IconCalculator}
        />
      </SimpleGrid>
    </Stack>
  );
}
