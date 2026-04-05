import { useState, useEffect } from 'react';
import {
  Title, Text, SimpleGrid, Card, Group, Stack, Badge,
  RingProgress, ThemeIcon, SegmentedControl, Paper, Skeleton,
} from '@mantine/core';
import { BarChart, AreaChart } from '@mantine/charts';
import {
  IconTrendingUp, IconChartBar, IconScale, IconArrowUpRight,
  IconArrowDownRight, IconUsers,
} from '@tabler/icons-react';
import { getDashboardSummary, getTopFunds } from '../api/client';

function StatCard({ title, value, subtitle, icon: Icon, color, trend }) {
  return (
    <Card
      p="lg"
      radius="md"
      className="glass-card"
      style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
    >
      <Group justify="space-between" mb="xs">
        <Text size="xs" c="dimmed" tt="uppercase" fw={600} ls={0.5}>{title}</Text>
        <ThemeIcon variant="subtle" color={color} size="sm">
          <Icon size={16} />
        </ThemeIcon>
      </Group>
      <Text size="xl" fw={700} c="white">{value ?? '—'}</Text>
      {subtitle && <Text size="xs" c="dimmed" mt={4}>{subtitle}</Text>}
      {trend && (
        <Group gap={4} mt={4}>
          {trend > 0 ? (
            <IconArrowUpRight size={14} color="#12b886" />
          ) : (
            <IconArrowDownRight size={14} color="#fa5252" />
          )}
          <Text size="xs" c={trend > 0 ? 'teal' : 'red'}>
            {Math.abs(trend).toFixed(1)}%
          </Text>
        </Group>
      )}
    </Card>
  );
}

export default function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const [topFunds, setTopFunds] = useState([]);
  const [bottomFunds, setBottomFunds] = useState([]);
  const [period, setPeriod] = useState('3Y');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, [period]);

  async function loadData() {
    setLoading(true);
    try {
      const [summaryRes, topRes, bottomRes] = await Promise.all([
        getDashboardSummary(),
        getTopFunds({ metric: 'sharpe_ratio', period, n: 10, direction: 'top' }),
        getTopFunds({ metric: 'sharpe_ratio', period, n: 10, direction: 'bottom' }),
      ]);
      setSummary(summaryRes.data);
      setTopFunds(topRes.data.data);
      setBottomFunds(bottomRes.data.data);
    } catch (err) {
      console.error('Dashboard load error:', err);
    }
    setLoading(false);
  }

  if (loading && !summary) {
    return (
      <Stack gap="lg">
        <Title order={2}>Dashboard</Title>
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} h={120} radius="md" />)}
        </SimpleGrid>
        <Skeleton h={300} radius="md" />
      </Stack>
    );
  }

  const sharpeHistogram = summary?.sharpe_distribution
    ? buildHistogramData(summary.sharpe_distribution)
    : [];

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <div>
          <Title order={2} c="white">Dashboard</Title>
          <Text size="sm" c="dimmed">Mutual Fund Performance Overview</Text>
        </div>
        <SegmentedControl
          size="sm"
          value={period}
          onChange={setPeriod}
          data={['3Y', '5Y', '7Y']}
          color="indigo"
        />
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
        <StatCard
          title="Total Funds"
          value={summary?.total_funds?.toLocaleString()}
          subtitle={`${summary?.funds_with_metrics || 0} with metrics`}
          icon={IconUsers}
          color="indigo"
        />
        <StatCard
          title="Avg Sharpe (3Y)"
          value={summary?.avg_sharpe_3y?.toFixed(3)}
          subtitle="Across all computed funds"
          icon={IconChartBar}
          color="teal"
        />
        <StatCard
          title="Avg Alpha (3Y)"
          value={summary?.avg_alpha_3y ? `${summary.avg_alpha_3y.toFixed(2)}%` : '—'}
          subtitle="Jensen's Alpha"
          icon={IconTrendingUp}
          color="violet"
        />
        <StatCard
          title="Benchmarks"
          value={summary?.mapped_benchmarks}
          subtitle={`of ${summary?.total_benchmarks} total mapped`}
          icon={IconScale}
          color="orange"
        />
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
        {/* Sharpe Distribution */}
        <Card p="lg" radius="md" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <Text fw={600} mb="md" c="white">Sharpe Ratio Distribution (3Y)</Text>
          {sharpeHistogram.length > 0 ? (
            <BarChart
              h={250}
              data={sharpeHistogram}
              dataKey="range"
              series={[{ name: 'count', color: 'indigo.6' }]}
              tickLine="y"
              gridAxis="y"
            />
          ) : (
            <Text c="dimmed" ta="center" py="xl">No data available. Run metrics computation first.</Text>
          )}
        </Card>

        {/* Category Distribution */}
        <Card p="lg" radius="md" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <Text fw={600} mb="md" c="white">Top Fund Categories</Text>
          {summary?.category_distribution?.length > 0 ? (
            <BarChart
              h={250}
              data={summary.category_distribution.slice(0, 10)}
              dataKey="category"
              series={[{ name: 'count', color: 'violet.6' }]}
              tickLine="y"
              gridAxis="y"
              orientation="vertical"
            />
          ) : (
            <Text c="dimmed" ta="center" py="xl">No category data yet. Fetch NAV data first.</Text>
          )}
        </Card>
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
        {/* Top Funds */}
        <Card p="lg" radius="md" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <Group justify="space-between" mb="md">
            <Text fw={600} c="white">Top 10 by Sharpe ({period})</Text>
            <Badge color="teal" variant="light" size="sm">Best</Badge>
          </Group>
          <Stack gap={6}>
            {topFunds.map((f, i) => (
              <Group key={f.id} justify="space-between" py={4} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <Group gap="xs">
                  <Badge size="xs" variant="outline" color="gray" w={28}>{i + 1}</Badge>
                  <Text size="xs" c="white" lineClamp={1} maw={280}>{f.fund_name}</Text>
                </Group>
                <Text size="xs" fw={600} c="teal">{f.metric_value?.toFixed(3)}</Text>
              </Group>
            ))}
            {topFunds.length === 0 && <Text c="dimmed" size="sm" ta="center" py="md">No data</Text>}
          </Stack>
        </Card>

        {/* Bottom Funds */}
        <Card p="lg" radius="md" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <Group justify="space-between" mb="md">
            <Text fw={600} c="white">Bottom 10 by Sharpe ({period})</Text>
            <Badge color="red" variant="light" size="sm">Worst</Badge>
          </Group>
          <Stack gap={6}>
            {bottomFunds.map((f, i) => (
              <Group key={f.id} justify="space-between" py={4} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <Group gap="xs">
                  <Badge size="xs" variant="outline" color="gray" w={28}>{i + 1}</Badge>
                  <Text size="xs" c="white" lineClamp={1} maw={280}>{f.fund_name}</Text>
                </Group>
                <Text size="xs" fw={600} c="red">{f.metric_value?.toFixed(3)}</Text>
              </Group>
            ))}
            {bottomFunds.length === 0 && <Text c="dimmed" size="sm" ta="center" py="md">No data</Text>}
          </Stack>
        </Card>
      </SimpleGrid>
    </Stack>
  );
}

function buildHistogramData(values) {
  if (!values.length) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const buckets = 15;
  const step = (max - min) / buckets;

  const histogram = [];
  for (let i = 0; i < buckets; i++) {
    const lo = min + i * step;
    const hi = lo + step;
    const count = values.filter(v => v >= lo && (i === buckets - 1 ? v <= hi : v < hi)).length;
    histogram.push({
      range: `${lo.toFixed(1)}`,
      count,
    });
  }
  return histogram;
}
