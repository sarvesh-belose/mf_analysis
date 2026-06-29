import { useState, useEffect, useCallback } from 'react';
import {
  Title, Text, Group, Stack, SegmentedControl, TextInput, Select,
  Badge, ActionIcon, Tooltip, Card, Button, Drawer, NumberInput, Divider,
  Collapse, UnstyledButton,
} from '@mantine/core';
import { DataTable } from 'mantine-datatable';
import { IconSearch, IconDownload, IconEye, IconArrowsSort, IconFilter, IconSparkles, IconX, IconChevronDown } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { listMetrics, getFundFilters } from '../api/client';

const PAGE_SIZE = 50;

function MetricCell({ value, format = 'number', invert = false }) {
  if (value === null || value === undefined) return <Text size="xs" c="dimmed">—</Text>;
  const isGood = invert ? value < 100 : value > 0;
  const color = isGood ? 'teal' : value < 0 || (invert && value > 100) ? 'red' : 'gray';
  const formatted = format === 'pct' ? `${value.toFixed(2)}%` : value.toFixed(3);
  return <Text size="xs" fw={600} c={color}>{formatted}</Text>;
}

export default function MetricsPage() {
  const navigate = useNavigate();
  const [period, setPeriod] = useState('3Y');
  const [data, setData] = useState([]);
  const [groups, setGroups] = useState(null); // non-null => grouped (top-N per category) view
  const [groupTopN, setGroupTopN] = useState(null); // requested funds-per-category in grouped mode
  const [collapsed, setCollapsed] = useState({}); // { [category]: true } => collapsed
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('sharpe_ratio');
  const [sortOrder, setSortOrder] = useState('desc');
  const [search, setSearch] = useState('');
  // Natural-language search: `nlInput` is the live text field, `nlQuery` is the
  // applied value (only changes on submit so we don't query on every keystroke).
  const [nlInput, setNlInput] = useState('');
  const [nlQuery, setNlQuery] = useState('');
  const [nlInfo, setNlInfo] = useState(null);
  const [fundHouse, setFundHouse] = useState('');
  const [category, setCategory] = useState('');
  const [filters, setFilters] = useState({ fund_houses: [], categories: [] });

  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);

  // Advanced Filters
  const [minRollingReturn, setMinRollingReturn] = useState('');
  const [minSortino, setMinSortino] = useState('');
  const [minAlpha, setMinAlpha] = useState('');
  const [minUpCapture, setMinUpCapture] = useState('');
  const [maxDownCapture, setMaxDownCapture] = useState('');

  useEffect(() => {
    loadFilters();
  }, []);

  useEffect(() => {
    loadData();
  }, [period, page, sortBy, sortOrder, nlQuery, search, fundHouse, category, minRollingReturn, minSortino, minAlpha, minUpCapture, maxDownCapture]);

  async function loadFilters() {
    try {
      const { data } = await getFundFilters();
      setFilters(data);
    } catch {}
  }

  async function loadData() {
    setLoading(true);
    try {
      const params = {
        period,
        page,
        page_size: PAGE_SIZE,
        sort_by: sortBy,
        sort_order: sortOrder,
      };
      if (nlQuery) params.q = nlQuery;
      if (search) params.search = search;
      if (fundHouse) params.fund_house = fundHouse;
      if (category) params.scheme_category = category;
      if (minRollingReturn !== '') params.min_rolling_return = minRollingReturn;
      if (minSortino !== '') params.min_sortino = minSortino;
      if (minAlpha !== '') params.min_alpha = minAlpha;
      if (minUpCapture !== '') params.min_up_capture = minUpCapture;
      if (maxDownCapture !== '') params.max_down_capture = maxDownCapture;

      const { data: result } = await listMetrics(params);
      if (result.grouped) {
        setGroups(result.groups || []);
        setGroupTopN(result.top_n ?? null);
        setCollapsed({}); // default everything expanded for a fresh query
        setData([]);
      } else {
        setGroups(null);
        setGroupTopN(null);
        setData(result.data);
      }
      setTotal(result.total);
      setNlInfo(result.nl || null);
    } catch (err) {
      console.error('Failed to load metrics:', err);
    }
    setLoading(false);
  }

  function applyNlQuery() {
    setNlQuery(nlInput.trim());
    setPage(1);
  }

  function toggleGroup(category) {
    setCollapsed((prev) => ({ ...prev, [category]: !prev[category] }));
  }

  function setAllCollapsed(value) {
    if (!groups) return;
    setCollapsed(value ? Object.fromEntries(groups.map((g) => [g.category, true])) : {});
  }

  function clearNlQuery() {
    setNlInput('');
    setNlQuery('');
    setNlInfo(null);
    setGroups(null);
    setPage(1);
  }

  function handleSort(col) {
    if (sortBy === col) {
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(col);
      setSortOrder('desc');
    }
    setPage(1);
  }

  function exportCsv() {
    const headers = ['Fund Name', 'Fund House', 'Category', 'Benchmark', 'Rolling Return', 'Sharpe', 'Sortino', 'Alpha', 'Beta', 'Up Capture', 'Down Capture', 'CAGR'];
    // In grouped mode, flatten all category groups into one export.
    const exportRows = groups ? groups.flatMap(g => g.funds) : data;
    const rows = exportRows.map(d => [
      d.fund_name, d.fund_house, d.scheme_category, d.benchmark_name,
      d.rolling_return_avg, d.sharpe_ratio, d.sortino_ratio,
      d.alpha, d.beta, d.up_capture, d.down_capture, d.fund_cagr,
    ]);
    const csv = [headers, ...rows].map(r => r.map(v => `"${v ?? ''}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `mf_metrics_${period}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  }

  const columns = [
    {
      accessor: 'fund_name',
      title: 'Fund Name',
      width: 300,
      sortable: true,
      render: (row) => (
        <Tooltip label="View details" position="right">
          <Text
            size="xs"
            fw={500}
            lineClamp={1}
            style={{ cursor: 'pointer' }}
            onClick={() => navigate(`/funds/${row.id}`)}
            c="indigo.4"
          >
            {row.fund_name}
          </Text>
        </Tooltip>
      ),
    },
    { accessor: 'fund_house', title: 'AMC', width: 160, render: (r) => <Text size="xs" lineClamp={1}>{r.fund_house || '—'}</Text> },
    { accessor: 'scheme_category', title: 'Category', width: 150, render: (r) => <Text size="xs" lineClamp={1}>{r.scheme_category || '—'}</Text> },
    { accessor: 'benchmark_name', title: 'Benchmark', width: 160, render: (r) => <Text size="xs" lineClamp={1}>{r.benchmark_name || '—'}</Text> },
    { accessor: 'rolling_return_avg', title: 'Rolling Ret', sortable: true, width: 90, render: (r) => <MetricCell value={r.rolling_return_avg} format="pct" /> },
    { accessor: 'sharpe_ratio', title: 'Sharpe', sortable: true, width: 80, render: (r) => <MetricCell value={r.sharpe_ratio} /> },
    { accessor: 'sortino_ratio', title: 'Sortino', sortable: true, width: 80, render: (r) => <MetricCell value={r.sortino_ratio} /> },
    { accessor: 'alpha', title: 'Alpha', sortable: true, width: 80, render: (r) => <MetricCell value={r.alpha} format="pct" /> },
    { accessor: 'beta', title: 'Beta', sortable: true, width: 70, render: (r) => <MetricCell value={r.beta} /> },
    { accessor: 'up_capture', title: 'Up Cap', sortable: true, width: 80, render: (r) => <MetricCell value={r.up_capture} format="pct" /> },
    { accessor: 'down_capture', title: 'Down Cap', sortable: true, width: 80, render: (r) => <MetricCell value={r.down_capture} format="pct" invert /> },
    { accessor: 'fund_cagr', title: 'CAGR', sortable: true, width: 80, render: (r) => <MetricCell value={r.fund_cagr} format="pct" /> },
    {
      accessor: 'data_sufficiency',
      title: '',
      width: 50,
      render: (r) => r.data_sufficiency === 'insufficient' ? (
        <Badge size="xs" color="yellow" variant="light">Low</Badge>
      ) : null,
    },
  ];

  // Grouped view: rank badge up front, no per-column sorting inside a group.
  const groupColumns = [
    {
      accessor: 'rank',
      title: '#',
      width: 40,
      render: (r) => <Badge size="sm" variant="light" color="indigo">{r.rank}</Badge>,
    },
    ...columns.filter(c => c.accessor !== 'data_sufficiency').map(c => ({ ...c, sortable: false })),
  ];

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <div>
          <Title order={2} c="white">Fund Explorer</Title>
          <Text size="sm" c="dimmed">
            {groups
              ? `${groups.length} categories • ${total.toLocaleString()} funds • Period: ${period}`
              : `${total.toLocaleString()} funds • Period: ${period}`}
          </Text>
        </div>
        <Group gap="sm">
          <SegmentedControl
            size="sm"
            value={period}
            onChange={(v) => { setPeriod(v); setPage(1); }}
            data={['3Y', '5Y', '7Y']}
            color="indigo"
          />
          <Tooltip label="Export CSV">
            <ActionIcon variant="subtle" size="lg" onClick={exportCsv}>
              <IconDownload size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      <Card withBorder padding="md" radius="md" style={{ background: 'rgba(99,102,241,0.05)', borderColor: 'rgba(99,102,241,0.25)' }}>
        <Stack gap="xs">
          <TextInput
            placeholder="Ask in plain English — e.g. 'top 3 in each category, sortino more'"
            leftSection={<IconSparkles size={16} color="var(--mantine-color-indigo-4)" />}
            value={nlInput}
            onChange={(e) => setNlInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') applyNlQuery(); }}
            size="sm"
            rightSectionWidth={nlQuery ? 120 : 80}
            rightSection={
              <Group gap={4} wrap="nowrap">
                {nlQuery && (
                  <Tooltip label="Clear">
                    <ActionIcon variant="subtle" color="gray" size="sm" onClick={clearNlQuery}>
                      <IconX size={14} />
                    </ActionIcon>
                  </Tooltip>
                )}
                <Button size="xs" variant="light" color="indigo" onClick={applyNlQuery}>
                  Search
                </Button>
              </Group>
            }
          />
          {nlInfo && nlInfo.matched && nlInfo.interpreted.length > 0 && (
            <Group gap="xs">
              <Text size="xs" c="dimmed">Interpreted as:</Text>
              {nlInfo.interpreted.map((chip, i) => (
                <Badge key={i} size="sm" variant="light" color="indigo">{chip}</Badge>
              ))}
            </Group>
          )}
          {nlQuery && nlInfo && !nlInfo.matched && (
            <Text size="xs" c="dimmed">
              No metric conditions recognized — searching fund / AMC names for "{nlQuery}".
            </Text>
          )}
          {!nlQuery && (
            <Text size="xs" c="dimmed">
              Try: "top 3 in each category sortino more", "3 year rolling returns over 10", "upcapture higher than 100 and downcapture lower than 100".
            </Text>
          )}
        </Stack>
      </Card>

      <Group gap="sm">
        <TextInput
          placeholder="Search funds..."
          leftSection={<IconSearch size={16} />}
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          style={{ flex: 1, maxWidth: 300 }}
          size="sm"
        />
        <Select
          placeholder="Fund House"
          data={filters.fund_houses || []}
          value={fundHouse}
          onChange={(v) => { setFundHouse(v || ''); setPage(1); }}
          clearable
          searchable
          size="sm"
          w={200}
        />
        <Select
          placeholder="Category"
          data={filters.categories || []}
          value={category}
          onChange={(v) => { setCategory(v || ''); setPage(1); }}
          clearable
          searchable
          size="sm"
          w={220}
        />
        <Button 
          variant="light" 
          color="indigo" 
          leftSection={<IconFilter size={16} />} 
          onClick={() => setFilterDrawerOpen(true)}
          size="sm"
        >
          Advanced Filters 
          {(minRollingReturn !== '' || minSortino !== '' || minAlpha !== '' || minUpCapture !== '' || maxDownCapture !== '') && (
            <Badge size="xs" circle color="indigo" ml={4}>!</Badge>
          )}
        </Button>
      </Group>

      <Drawer
        opened={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        title={<Text fw={600} size="lg">Advanced Filters</Text>}
        position="right"
        padding="xl"
        size="md"
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">Fine-tune your fund discovery using precise numerical thresholds across available metrics.</Text>
          
          <Divider my="sm" />
          
          <NumberInput
            label="Min Rolling Return Avg (%)"
            description="Minimum 3Y average rolling return."
            placeholder="e.g. 12"
            value={minRollingReturn}
            onChange={(v) => { setMinRollingReturn(v === '' ? '' : Number(v)); setPage(1); }}
            min={-50} max={100}
          />

          <NumberInput
            label="Min Sortino Ratio"
            description="Minimum Sortino ratio (downside risk-adjusted return)."
            placeholder="e.g. 1.0"
            value={minSortino}
            onChange={(v) => { setMinSortino(v === '' ? '' : Number(v)); setPage(1); }}
            step={0.1} min={-5} max={10}
          />

          <NumberInput
            label="Min Alpha (%)"
            description="Minimum outperformance over the benchmark."
            placeholder="e.g. 2.0"
            value={minAlpha}
            onChange={(v) => { setMinAlpha(v === '' ? '' : Number(v)); setPage(1); }}
            step={0.5} min={-50} max={50}
          />

          <NumberInput
            label="Min Up Capture (%)"
            description="Minimum upside capture ratio (higher is better)."
            placeholder="e.g. 100"
            value={minUpCapture}
            onChange={(v) => { setMinUpCapture(v === '' ? '' : Number(v)); setPage(1); }}
            step={5} min={0} max={300}
          />

          <NumberInput
            label="Max Down Capture (%)"
            description="Maximum downside capture ratio (lower is better)."
            placeholder="e.g. 90"
            value={maxDownCapture}
            onChange={(v) => { setMaxDownCapture(v === '' ? '' : Number(v)); setPage(1); }}
            step={5} min={0} max={300}
          />

          <Button 
            mt="xl" 
            variant="outline" 
            color="red" 
            onClick={() => {
              setMinRollingReturn('');
              setMinSortino('');
              setMinAlpha('');
              setMinUpCapture('');
              setMaxDownCapture('');
              setPage(1);
            }}
          >
            Clear Filters
          </Button>
        </Stack>
      </Drawer>

      {groups ? (
        <Stack gap="md">
          {groups.length === 0 && (
            <Text c="dimmed" size="sm" ta="center" py="xl">
              No funds match this query. Try relaxing the conditions.
            </Text>
          )}
          {groups.length > 0 && (
            <Group justify="space-between" gap="xs">
              <Text size="xs" c="dimmed">
                Showing up to {groupTopN} fund{groupTopN === 1 ? '' : 's'} per category, ranked by {sortBy.replace(/_/g, ' ')}.
                {groups.some(g => g.funds.length < groupTopN) && ' Some categories have fewer — the filters exclude the rest.'}
              </Text>
              <Group gap="xs">
                <Button size="compact-xs" variant="subtle" color="gray" onClick={() => setAllCollapsed(false)}>
                  Expand all
                </Button>
                <Button size="compact-xs" variant="subtle" color="gray" onClick={() => setAllCollapsed(true)}>
                  Collapse all
                </Button>
              </Group>
            </Group>
          )}
          {groups.map((g) => {
            const isCollapsed = !!collapsed[g.category];
            return (
              <Card
                key={g.category}
                withBorder
                padding="md"
                radius="md"
                style={{ background: 'rgba(255,255,255,0.02)', borderColor: 'rgba(255,255,255,0.06)' }}
              >
                <UnstyledButton onClick={() => toggleGroup(g.category)} style={{ width: '100%' }}>
                  <Group justify="space-between" mb={isCollapsed ? 0 : 'sm'} wrap="nowrap">
                    <Group gap="xs" wrap="nowrap">
                      <IconChevronDown
                        size={16}
                        style={{
                          color: 'var(--mantine-color-dimmed)',
                          transition: 'transform 0.15s ease',
                          transform: isCollapsed ? 'rotate(-90deg)' : 'none',
                        }}
                      />
                      <Text fw={600} c="white">{g.category}</Text>
                    </Group>
                    <Badge variant="light" color={g.funds.length < groupTopN ? 'yellow' : 'indigo'}>
                      {g.funds.length < groupTopN
                        ? `${g.funds.length} of ${groupTopN}`
                        : `Top ${g.funds.length}`}
                    </Badge>
                  </Group>
                </UnstyledButton>
                <Collapse in={!isCollapsed}>
                  <DataTable
                    records={g.funds}
                    columns={groupColumns}
                    idAccessor="id"
                    fetching={loading}
                    highlightOnHover
                    withTableBorder={false}
                    borderRadius="sm"
                    minHeight={0}
                    styles={{ header: { background: 'rgba(255,255,255,0.03)' } }}
                    rowStyle={() => ({ borderBottom: '1px solid rgba(255,255,255,0.04)' })}
                  />
                </Collapse>
              </Card>
            );
          })}
        </Stack>
      ) : (
        <DataTable
          records={data}
          columns={columns}
          totalRecords={total}
          recordsPerPage={PAGE_SIZE}
          page={page}
          onPageChange={setPage}
          sortStatus={{ columnAccessor: sortBy, direction: sortOrder }}
          onSortStatusChange={({ columnAccessor, direction }) => {
            setSortBy(columnAccessor);
            setSortOrder(direction);
            setPage(1);
          }}
          fetching={loading}
          highlightOnHover
          withTableBorder={false}
          borderRadius="md"
          minHeight={400}
          noRecordsText="No funds found. Try adjusting filters or run setup."
          styles={{
            root: { background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8 },
            header: { background: 'rgba(255,255,255,0.03)' },
          }}
          rowStyle={() => ({
            borderBottom: '1px solid rgba(255,255,255,0.04)',
          })}
        />
      )}
    </Stack>
  );
}
