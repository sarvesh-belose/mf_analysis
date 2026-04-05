import { useState, useEffect } from 'react';
import {
  Title, Text, Group, Stack, Card, Badge, Tabs, Select, Button,
  Modal, Textarea, CopyButton, ActionIcon, Tooltip, Table,
  FileInput, Notification,
} from '@mantine/core';
import {
  IconDatabase, IconRefresh, IconCopy, IconCheck, IconUpload,
  IconDownload, IconAlertCircle,
} from '@tabler/icons-react';
import {
  listBenchmarks, updateBenchmark, getTriFiles, getTriCoverage,
  getRefreshPrompt, uploadTriCsv, getTriFetchLog,
} from '../api/client';

export default function BenchmarkPage() {
  const [benchmarks, setBenchmarks] = useState([]);
  const [triFiles, setTriFiles] = useState([]);
  const [coverage, setCoverage] = useState([]);
  const [fetchLog, setFetchLog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [promptModal, setPromptModal] = useState(false);
  const [promptText, setPromptText] = useState('');
  const [promptExchange, setPromptExchange] = useState('NSE');

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [bRes, fRes, cRes, lRes] = await Promise.all([
        listBenchmarks(),
        getTriFiles(),
        getTriCoverage(),
        getTriFetchLog(),
      ]);
      setBenchmarks(bRes.data.data || []);
      setTriFiles(fRes.data.files || []);
      setCoverage(cRes.data.data || []);
      setFetchLog(lRes.data.data || []);
    } catch (err) {
      console.error('Failed to load benchmarks:', err);
    }
    setLoading(false);
  }

  async function handleOverride(benchmarkId, triFile) {
    try {
      await updateBenchmark(benchmarkId, { tri_file_name: triFile, manually_verified: true });
      loadData();
    } catch {}
  }

  async function generatePrompt(exchange) {
    setPromptExchange(exchange);
    try {
      const { data } = await getRefreshPrompt(exchange);
      setPromptText(data.prompt);
      setPromptModal(true);
    } catch {}
  }

  async function handleUpload(file) {
    if (!file) return;
    try {
      await uploadTriCsv(file);
      loadData();
    } catch {}
  }

  function getStatusColor(status) {
    switch (status) {
      case 'mapped': return 'teal';
      case 'low_confidence': return 'yellow';
      case 'unmapped': return 'red';
      case 'no_benchmark': return 'gray';
      case 'international': return 'blue';
      case 'composite': return 'violet';
      default: return 'gray';
    }
  }

  function getScoreColor(score) {
    if (score >= 90) return 'teal';
    if (score >= 75) return 'yellow';
    return 'red';
  }

  return (
    <Stack gap="lg">
      <Title order={2} c="white">Benchmarks & TRI Data</Title>

      <Tabs defaultValue="mapping">
        <Tabs.List>
          <Tabs.Tab value="mapping" leftSection={<IconDatabase size={16} />}>Benchmark Mapping</Tabs.Tab>
          <Tabs.Tab value="coverage" leftSection={<IconRefresh size={16} />}>TRI Coverage</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="mapping" pt="md">
          <Card p="md" radius="md" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
            <Table striped={false} withTableBorder={false}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Benchmark Name</Table.Th>
                  <Table.Th>TRI File</Table.Th>
                  <Table.Th w={80}>Score</Table.Th>
                  <Table.Th w={100}>Status</Table.Th>
                  <Table.Th w={80}>Funds</Table.Th>
                  <Table.Th w={120}>Override</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {benchmarks.map(b => (
                  <Table.Tr key={b.id}>
                    <Table.Td><Text size="xs" lineClamp={1}>{b.name_in_excel}</Text></Table.Td>
                    <Table.Td><Text size="xs" c="dimmed" lineClamp={1}>{b.tri_file_name || '—'}</Text></Table.Td>
                    <Table.Td>
                      <Badge size="xs" color={getScoreColor(b.match_score)} variant="light">
                        {b.match_score?.toFixed(0)}%
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Badge size="xs" color={getStatusColor(b.status)} variant="light">
                        {b.status}
                      </Badge>
                    </Table.Td>
                    <Table.Td><Text size="xs">{b.fund_count}</Text></Table.Td>
                    <Table.Td>
                      <Select
                        size="xs"
                        placeholder="Override"
                        data={triFiles}
                        searchable
                        clearable
                        onChange={(val) => val && handleOverride(b.id, val)}
                        w={120}
                      />
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>
        </Tabs.Panel>

        <Tabs.Panel value="coverage" pt="md">
          <Stack gap="md">
            <Group>
              <Button
                size="sm"
                variant="light"
                color="indigo"
                leftSection={<IconRefresh size={16} />}
                onClick={() => generatePrompt('NSE')}
              >
                NSE Refresh Prompt
              </Button>
              <Button
                size="sm"
                variant="light"
                color="orange"
                leftSection={<IconRefresh size={16} />}
                onClick={() => generatePrompt('BSE')}
              >
                BSE Refresh Prompt
              </Button>
              <FileInput
                size="sm"
                placeholder="Upload TRI CSV"
                leftSection={<IconUpload size={16} />}
                accept=".csv"
                onChange={handleUpload}
                w={200}
              />
            </Group>

            <Card p="md" radius="md" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <Text fw={600} c="white" mb="sm">TRI Data Coverage</Text>
              <Table striped={false} withTableBorder={false}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Benchmark</Table.Th>
                    <Table.Th>Exchange</Table.Th>
                    <Table.Th>From</Table.Th>
                    <Table.Th>To</Table.Th>
                    <Table.Th>Rows</Table.Th>
                    <Table.Th>Status</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {coverage.map(c => (
                    <Table.Tr key={c.benchmark_id}>
                      <Table.Td><Text size="xs" lineClamp={1}>{c.name}</Text></Table.Td>
                      <Table.Td><Badge size="xs" color={c.exchange === 'NSE' ? 'blue' : 'orange'} variant="light">{c.exchange}</Badge></Table.Td>
                      <Table.Td><Text size="xs">{c.min_date || '—'}</Text></Table.Td>
                      <Table.Td><Text size="xs">{c.max_date || '—'}</Text></Table.Td>
                      <Table.Td><Text size="xs">{c.row_count}</Text></Table.Td>
                      <Table.Td>
                        <Badge size="xs" color={c.needs_refresh ? 'yellow' : 'teal'} variant="light">
                          {c.needs_refresh ? 'Needs Refresh' : 'OK'}
                        </Badge>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Card>
          </Stack>
        </Tabs.Panel>
      </Tabs>

      {/* Prompt Modal */}
      <Modal
        opened={promptModal}
        onClose={() => setPromptModal(false)}
        title={`Browser-Use Prompt (${promptExchange})`}
        size="lg"
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Copy this prompt and run it on{' '}
            <a href="https://cloud.browser-use.com/" target="_blank" rel="noreferrer" style={{ color: '#748ffc' }}>
              cloud.browser-use.com
            </a>
          </Text>
          <Textarea
            value={promptText}
            readOnly
            minRows={15}
            maxRows={25}
            autosize
            styles={{ input: { fontFamily: 'monospace', fontSize: 12 } }}
          />
          <CopyButton value={promptText}>
            {({ copied, copy }) => (
              <Button
                color={copied ? 'teal' : 'indigo'}
                onClick={copy}
                leftSection={copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
              >
                {copied ? 'Copied!' : 'Copy Prompt'}
              </Button>
            )}
          </CopyButton>
        </Stack>
      </Modal>
    </Stack>
  );
}
