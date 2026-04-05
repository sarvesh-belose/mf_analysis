import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Title, Text, Group, Stack, Card, SimpleGrid, Badge, Tabs,
  Skeleton, Button, ThemeIcon, Divider,
} from '@mantine/core';
import { LineChart } from '@mantine/charts';
import { IconArrowLeft, IconChartLine, IconReportAnalytics, IconCalendarEvent } from '@tabler/icons-react';
import { getFundDetail, getNavHistory, getRollingReturns } from '../api/client';

function MetricCard({ label, value, format = 'number', suffix = '', benchmarkValue = null }) {
  if (value === null || value === undefined) {
    return (
      <Card p="sm" radius="md" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
        <Text size="xs" c="dimmed">{label}</Text>
        <Text size="lg" fw={700} c="dimmed">—</Text>
        {benchmarkValue !== null && benchmarkValue !== undefined && (
          <Text size="xs" c="dimmed" mt={4}>Bench: {format === 'pct' ? `${benchmarkValue.toFixed(2)}%` : benchmarkValue.toFixed(3)}</Text>
        )}
      </Card>
    );
  }
  const isPositive = value > 0;
  const color = isPositive ? 'teal' : 'red';
  const formatted = format === 'pct' ? `${value.toFixed(2)}%` : value.toFixed(3);

  return (
    <Card p="sm" radius="md" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
      <Text size="xs" c="dimmed">{label}</Text>
      <Group align="flex-end" gap="xs">
        <Text size="lg" fw={700} c={color}>{formatted}{suffix}</Text>
      </Group>
      {benchmarkValue !== null && benchmarkValue !== undefined && (
        <Group justify="space-between" mt={4}>
          <Text size="xs" c="dimmed">Benchmark:</Text>
          <Text size="xs" c="dimmed">{format === 'pct' ? `${benchmarkValue.toFixed(2)}%` : benchmarkValue.toFixed(3)}</Text>
        </Group>
      )}
    </Card>
  );
}

export default function FundDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [fund, setFund] = useState(null);
  const [navData, setNavData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('3Y');

  // Rolling returns state
  const [rollingData, setRollingData] = useState([]);
  const [rollingAvg, setRollingAvg] = useState({ fund: null, benchmark: null });
  const [rollingLoading, setRollingLoading] = useState(false);
  const [rollingWindow, setRollingWindow] = useState('3');
  const [startDate, setStartDate] = useState('2015-01-01');

  useEffect(() => {
    loadFund();
  }, [id]);

  async function loadFund() {
    setLoading(true);
    try {
      const [fundRes, navRes] = await Promise.all([
        getFundDetail(id),
        getNavHistory(id),
      ]);
      setFund(fundRes.data);
      setNavData(navRes.data.data.map(d => ({ date: d.date, NAV: d.nav })));
    } catch (err) {
      console.error('Failed to load fund:', err);
    }
    setLoading(false);
  }

  useEffect(() => {
    loadRollingReturns();
  }, [id, startDate, rollingWindow]);

  async function loadRollingReturns() {
    if (!startDate) return;
    setRollingLoading(true);
    try {
      const { data } = await getRollingReturns(id, { start_date: startDate, window_years: parseInt(rollingWindow) });
      setRollingData(data.data || []);
      setRollingAvg({ fund: data.fund_avg, benchmark: data.benchmark_avg });
    } catch (err) {
      console.error('Failed to load rolling returns:', err);
      setRollingData([]);
    }
    setRollingLoading(false);
  }

  if (loading) {
    return (
      <Stack gap="lg">
        <Skeleton h={40} w={300} />
        <SimpleGrid cols={4}>{[1,2,3,4].map(i => <Skeleton key={i} h={80} />)}</SimpleGrid>
        <Skeleton h={300} />
      </Stack>
    );
  }

  if (!fund) return <Text c="red">Fund not found</Text>;

  const metrics = fund.metrics?.[activeTab] || {};

  return (
    <Stack gap="lg">
      <Group>
        <Button variant="subtle" size="xs" leftSection={<IconArrowLeft size={14} />} onClick={() => navigate(-1)}>
          Back
        </Button>
      </Group>

      <div>
        <Title order={2} c="white">{fund.fund?.fund_name}</Title>
        <Group gap="sm" mt="xs">
          {fund.fund?.fund_house && <Badge variant="light" color="indigo">{fund.fund.fund_house}</Badge>}
          {fund.fund?.scheme_category && <Badge variant="light" color="violet">{fund.fund.scheme_category}</Badge>}
          {fund.benchmark?.name && <Badge variant="light" color="orange">{fund.benchmark.name}</Badge>}
        </Group>
      </div>

      <Tabs value={activeTab} onChange={setActiveTab}>
        <Tabs.List>
          <Tabs.Tab value="3Y">3 Year</Tabs.Tab>
          <Tabs.Tab value="5Y">5 Year</Tabs.Tab>
          <Tabs.Tab value="7Y">7 Year</Tabs.Tab>
        </Tabs.List>
      </Tabs>

      {metrics.data_sufficiency === 'insufficient' && (
        <Badge color="yellow" variant="light" size="lg">⚠ Insufficient data for {activeTab} metrics</Badge>
      )}

      <SimpleGrid cols={{ base: 2, sm: 3, lg: 4 }} spacing="sm">
        <MetricCard label="Avg Rolling Return (3Y)" value={metrics.rolling_return_avg} benchmarkValue={metrics.benchmark_rolling_return_avg} format="pct" />
        <MetricCard label="Sharpe Ratio" value={metrics.sharpe_ratio} benchmarkValue={metrics.benchmark_sharpe_ratio} />
        <MetricCard label="Sortino Ratio" value={metrics.sortino_ratio} benchmarkValue={metrics.benchmark_sortino_ratio} />
        <MetricCard label="Alpha" value={metrics.alpha} format="pct" />
        <MetricCard label="Beta" value={metrics.beta} />
        <MetricCard label="Up Capture" value={metrics.up_capture} format="pct" />
        <MetricCard label="Down Capture" value={metrics.down_capture} format="pct" />
        <MetricCard label="CAGR" value={metrics.fund_cagr} benchmarkValue={metrics.benchmark_cagr} format="pct" />
      </SimpleGrid>

      <Card p="lg" radius="md" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
        <Group mb="md">
          <ThemeIcon variant="subtle" color="indigo"><IconChartLine size={18} /></ThemeIcon>
          <Text fw={600} c="white">NAV History</Text>
          <Badge size="sm" variant="light">{navData.length} data points</Badge>
        </Group>
        {navData.length > 0 ? (
          <LineChart
            h={300}
            data={navData}
            dataKey="date"
            series={[{ name: 'NAV', color: 'indigo.6' }]}
            curveType="natural"
            withDots={false}
            withTooltip
            tooltipAnimationDuration={200}
            gridAxis="y"
          />
        ) : (
          <Text c="dimmed" ta="center" py="xl">No NAV data available</Text>
        )}
      </Card>

      <Card p="lg" radius="md" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
        <Group justify="space-between" mb="md">
          <Group>
            <ThemeIcon variant="subtle" color="teal"><IconReportAnalytics size={18} /></ThemeIcon>
            <Text fw={600} c="white">Dynamic Rolling Returns Analysis</Text>
          </Group>
          <Group gap="sm">
            <Group gap={4} bg="rgba(0,0,0,0.2)" px="sm" py={4} style={{ borderRadius: 8 }}>
              <IconCalendarEvent size={14} style={{ color: 'var(--mantine-color-dimmed)' }} />
              <input 
                type="date" 
                value={startDate} 
                onChange={(e) => setStartDate(e.target.value)} 
                style={{
                  background: 'transparent', border: 'none', color: 'white', 
                  outline: 'none', fontSize: 13, cursor: 'pointer'
                }} 
              />
            </Group>
            <Tabs value={rollingWindow} onChange={setRollingWindow} variant="pills" radius="xl" size="xs">
              <Tabs.List>
                <Tabs.Tab value="1">1Y</Tabs.Tab>
                <Tabs.Tab value="3">3Y</Tabs.Tab>
                <Tabs.Tab value="5">5Y</Tabs.Tab>
              </Tabs.List>
            </Tabs>
          </Group>
        </Group>

        {rollingLoading ? (
          <Skeleton h={300} mt="md" />
        ) : rollingData.length > 0 ? (
          <Stack gap="lg">
            <Group grow>
              <MetricCard label={`Fund Avg ${rollingWindow}Y Return`} value={rollingAvg.fund} format="pct" />
              {rollingAvg.benchmark !== null && (
                <MetricCard label={`Bench Avg ${rollingWindow}Y Return`} value={rollingAvg.benchmark} format="pct" />
              )}
            </Group>
            <LineChart
              h={300}
              data={rollingData}
              dataKey="date"
              series={[
                { name: 'fund_rolling_cagr', label: 'Fund', color: 'indigo.5' },
                { name: 'benchmark_rolling_cagr', label: 'Benchmark', color: 'teal.5' },
              ]}
              curveType="natural"
              withDots={false}
              withTooltip
              gridAxis="y"
              tooltipAnimationDuration={200}
              valueFormatter={(v) => `${v}%`}
            />
          </Stack>
        ) : (
          <Text c="dimmed" ta="center" py="xl">No rolling returns found for this date range</Text>
        )}
      </Card>
    </Stack>
  );
}
