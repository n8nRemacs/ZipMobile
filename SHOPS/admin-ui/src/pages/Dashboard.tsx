import { Card, Col, Row, Statistic, Typography, Table, Button, message } from 'antd'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getNormalizeStatus, getModerationStats, normalizeShop } from '../api/client'
import StatusBadge from '../components/StatusBadge'

const { Title } = Typography

export default function DashboardPage() {
  const { data: shopStats = [], isLoading } = useQuery({
    queryKey: ['normalize-status'],
    queryFn: getNormalizeStatus,
  })

  const { data: modStats = {} } = useQuery({
    queryKey: ['moderation-stats'],
    queryFn: getModerationStats,
  })

  const normalizeMutation = useMutation({
    mutationFn: (shopCode: string) => normalizeShop(shopCode),
    onSuccess: (data) => {
      message.success(`Task started: ${data.task_id} (${data.total} items)`)
    },
  })

  const totalAll = shopStats.reduce((s, r) => s + r.total, 0)
  const normalizedAll = shopStats.reduce((s, r) => s + r.normalized, 0)
  const pendingAll = shopStats.reduce((s, r) => s + r.pending, 0)

  const modPending = Object.values(modStats).reduce(
    (s, v) => s + ((v as Record<string, number>)['pending'] ?? 0),
    0,
  )

  return (
    <>
      <Title level={3}>Dashboard</Title>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card><Statistic title="Total products" value={totalAll} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Normalized" value={normalizedAll} valueStyle={{ color: '#3f8600' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Pending normalization" value={pendingAll} valueStyle={{ color: '#cf1322' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="In moderation" value={modPending} valueStyle={{ color: '#d46b08' }} /></Card>
        </Col>
      </Row>

      <Title level={4}>By shop</Title>
      <Table
        dataSource={shopStats}
        loading={isLoading}
        rowKey="shop_code"
        size="middle"
        pagination={false}
        columns={[
          { title: 'Shop', dataIndex: 'shop_name' },
          { title: 'Code', dataIndex: 'shop_code' },
          { title: 'Total', dataIndex: 'total' },
          { title: 'Normalized', dataIndex: 'normalized' },
          { title: 'Pending', dataIndex: 'pending' },
          {
            title: 'Coverage',
            render: (_, r) =>
              r.total > 0 ? `${((r.normalized / r.total) * 100).toFixed(1)}%` : '-',
          },
          {
            title: 'Action',
            render: (_, r) =>
              r.pending > 0 ? (
                <Button
                  size="small"
                  type="primary"
                  loading={normalizeMutation.isPending}
                  onClick={() => normalizeMutation.mutate(r.shop_code)}
                >
                  Normalize ({r.pending})
                </Button>
              ) : (
                <StatusBadge status="normalized" />
              ),
          },
        ]}
      />

      <Title level={4} style={{ marginTop: 24 }}>Moderation stats</Title>
      <Table
        dataSource={Object.entries(modStats).map(([type, counts]) => ({
          type,
          ...(counts as Record<string, number>),
        }))}
        rowKey="type"
        size="middle"
        pagination={false}
        columns={[
          { title: 'Entity type', dataIndex: 'type' },
          { title: 'Pending', dataIndex: 'pending', render: (v: number) => v ?? 0 },
          { title: 'Resolved', dataIndex: 'resolved', render: (v: number) => v ?? 0 },
        ]}
      />
    </>
  )
}
