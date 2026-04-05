import { useState, useEffect } from 'react';
import {
  Title, Text, Group, Stack, Card, SegmentedControl, Button,
  TextInput, Badge, Table, Tooltip, ActionIcon, MultiSelect,
} from '@mantine/core';
import { RadarChart } from '@mantine/charts';
import { IconSearch, IconPlus, IconX, IconScale } from '@tabler/icons-react';
import { compareFunds, listMetrics } from '../api/client';

export default function ComparisonPage() {
  const [selectedIds, setSelectedIds] = useState([]);
  const [compData, setCompData] = useState([]);
  const [period, setPeriod] = useState('3Y');
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (selectedIds.length >= 2) {
      loadComparison();
    }
  }, [selectedIds, period]);

  async function loadComparison() {
    setLoading(true);
    try {
      const { data } = await compareFunds({
        fund_ids: selectedIds.join(','),
        period,
      });
      setCompData(data.data);
    } catch (err) {
      console.error('Comparison failed:', err);
    }
    setLoading(false);
  }

  async function searchFunds() {
    if (!search.trim()) return;
    try {
      const { data } = await listMetrics({
        search,
        period,
        page: 1,
        page_size: 10,
      });
      setSearchResults(data.data);
    } catch {}
  }

  function addFund(id) {
    if (selectedIds.length < 5 && !selectedIds.includes(id)) {
      setSelectedIds([...selectedIds, id]);
    }
  }

  function removeFund(id) {
    setSelectedIds(selectedIds.filter(x => x !== id));
    setCompData(compData.filter(x => x.id !== id));
  }

  const metrics = ['sharpe_ratio', 'sortino_ratio', 'alpha', 'up_capture', 'fund_cagr'];
  const metricLabels = {
    sharpe_ratio: 'Sharpe',
    sortino_ratio: 'Sortino',
    alpha: 'Alpha (%)',
    up_capture: 'Up Capture (%)',
    fund_cagr: 'CAGR (%)',
  };

  // Radar chart data
  const radarData = metrics.map(m => {
    const entry = { metric: metricLabels[m] };
    compData.forEach(f => {
      entry[f.fund_name.slice(0, 20)] = f[m] || 0;
    });
    return entry;
  });

  const radarSeries = compData.map((f, i) => ({
    name: f.fund_name.slice(0, 20),
    color: ['indigo.6', 'teal.6', 'violet.6', 'orange.6', 'pink.6'][i],
    opacity: 0.2,
  }));

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <div>
          <Title order={2} c="white">Fund Comparison</Title>
          <Text size="sm" c="dimmed">Compare up to 5 funds side-by-side</Text>
        </div>
        <SegmentedControl
          size="sm"
          value={period}
          onChange={setPeriod}
          data={['3Y', '5Y', '7Y']}
          color="indigo"
        />
      </Group>

      <Card p="md" radius="md" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
        <Group gap="sm" mb="sm">
          <TextInput
            placeholder="Search fund to add..."
            leftSection={<IconSearch size={16} />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && searchFunds()}
            style={{ flex: 1 }}
            size="sm"
          />
          <Button size="sm" onClick={searchFunds} variant="light">Search</Button>
        </Group>

        {searchResults.length > 0 && (
          <Stack gap={4} mb="md">
            {searchResults.map(f => (
              <Group key={f.id} justify="space-between" py={4} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <Text size="xs" lineClamp={1}>{f.fund_name}</Text>
                <Button
                  size="xs"
                  variant="subtle"
                  color="indigo"
                  leftSection={<IconPlus size={12} />}
                  onClick={() => addFund(f.id)}
                  disabled={selectedIds.includes(f.id)}
                >
                  Add
                </Button>
              </Group>
            ))}
          </Stack>
        )}

        <Group gap="xs">
          {compData.map((f, i) => (
            <Badge
              key={f.id}
              color={['indigo', 'teal', 'violet', 'orange', 'pink'][i]}
              variant="light"
              size="lg"
              rightSection={
                <ActionIcon size="xs" variant="subtle" onClick={() => removeFund(f.id)}>
                  <IconX size={12} />
                </ActionIcon>
              }
            >
              {f.fund_name.slice(0, 30)}
            </Badge>
          ))}
        </Group>
      </Card>

      {compData.length >= 2 && (
        <>
          {/* Comparison Table */}
          <Card p="lg" radius="md" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
            <Text fw={600} c="white" mb="md">Metrics Comparison ({period})</Text>
            <Table striped={false} withTableBorder={false} highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Metric</Table.Th>
                  {compData.map(f => (
                    <Table.Th key={f.id}>
                      <Text size="xs" lineClamp={1}>{f.fund_name.slice(0, 25)}</Text>
                    </Table.Th>
                  ))}
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {[
                  { key: 'rolling_return_avg', label: 'Rolling Return', fmt: 'pct' },
                  { key: 'sharpe_ratio', label: 'Sharpe Ratio', fmt: 'num' },
                  { key: 'sortino_ratio', label: 'Sortino Ratio', fmt: 'num' },
                  { key: 'alpha', label: 'Alpha', fmt: 'pct' },
                  { key: 'beta', label: 'Beta', fmt: 'num' },
                  { key: 'up_capture', label: 'Up Capture', fmt: 'pct' },
                  { key: 'down_capture', label: 'Down Capture', fmt: 'pct' },
                  { key: 'fund_cagr', label: 'Fund CAGR', fmt: 'pct' },
                  { key: 'benchmark_cagr', label: 'Benchmark CAGR', fmt: 'pct' },
                ].map(({ key, label, fmt }) => {
                  const values = compData.map(f => f[key]).filter(v => v !== null && v !== undefined);
                  const best = Math.max(...values);

                  return (
                    <Table.Tr key={key}>
                      <Table.Td><Text size="xs" fw={500}>{label}</Text></Table.Td>
                      {compData.map(f => {
                        const val = f[key];
                        const isBest = val === best && values.length > 1;
                        return (
                          <Table.Td key={f.id}>
                            <Text size="xs" fw={isBest ? 700 : 400} c={isBest ? 'teal' : undefined}>
                              {val != null ? (fmt === 'pct' ? `${val.toFixed(2)}%` : val.toFixed(3)) : '—'}
                            </Text>
                          </Table.Td>
                        );
                      })}
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          </Card>

          {/* Radar Chart */}
          <Card p="lg" radius="md" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
            <Text fw={600} c="white" mb="md">Visual Comparison</Text>
            <RadarChart
              h={350}
              data={radarData}
              dataKey="metric"
              series={radarSeries}
              withPolarGrid
              withPolarAngleAxis
              withPolarRadiusAxis
            />
          </Card>
        </>
      )}

      {compData.length < 2 && selectedIds.length < 2 && (
        <Card p="xl" radius="md" style={{ background: 'rgba(255,255,255,0.02)' }}>
          <Stack align="center" gap="md">
            <IconScale size={48} color="gray" />
            <Text c="dimmed">Search and add at least 2 funds to compare</Text>
          </Stack>
        </Card>
      )}
    </Stack>
  );
}
