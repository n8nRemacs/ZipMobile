import { useState } from 'react'
import { Select, Space, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import type { ModerationItem } from '../types'
import { getModerationList } from '../api/client'
import DataTable from '../components/DataTable'
import StatusBadge from '../components/StatusBadge'
import ModerationModal from '../components/ModerationModal'

const { Title } = Typography

const ENTITY_TYPES = [
  { value: '', label: 'All types' },
  { value: 'brand', label: 'Brand' },
  { value: 'model', label: 'Model' },
  { value: 'part_type', label: 'Part Type' },
  { value: 'color', label: 'Color' },
]

export default function ModerationListPage() {
  const [entityType, setEntityType] = useState('')
  const [shopCode, setShopCode] = useState('')
  const [selected, setSelected] = useState<ModerationItem | null>(null)

  const { data = [], isLoading } = useQuery({
    queryKey: ['moderation', entityType, shopCode],
    queryFn: () =>
      getModerationList({
        entity_type: entityType || undefined,
        shop_code: shopCode || undefined,
        limit: 100,
      }),
  })

  const columns: ColumnsType<ModerationItem> = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: 'Type', dataIndex: 'entity_type', width: 80 },
    { title: 'Proposed', dataIndex: 'proposed_name', width: 200 },
    { title: 'Source Name', dataIndex: 'source_name', ellipsis: true },
    { title: 'Article', dataIndex: 'source_article', width: 120 },
    { title: 'Shop', dataIndex: 'source_shop', width: 100 },
    {
      title: 'Confidence',
      dataIndex: 'ai_confidence',
      width: 100,
      render: (v: number | null) => v?.toFixed(2) ?? '-',
      sorter: (a, b) => (a.ai_confidence ?? 0) - (b.ai_confidence ?? 0),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      width: 100,
      render: (s: string) => <StatusBadge status={s} />,
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      width: 140,
      render: (v: string) => dayjs(v).format('DD.MM.YY HH:mm'),
      sorter: (a, b) => dayjs(a.created_at).unix() - dayjs(b.created_at).unix(),
    },
  ]

  return (
    <>
      <Title level={3}>Moderation Queue</Title>
      <Space style={{ marginBottom: 16 }}>
        <Select
          value={entityType}
          onChange={setEntityType}
          options={ENTITY_TYPES}
          style={{ width: 150 }}
        />
        <Select
          value={shopCode}
          onChange={setShopCode}
          placeholder="Shop"
          allowClear
          style={{ width: 150 }}
          options={[
            { value: '', label: 'All shops' },
            { value: 'profi', label: 'Profi' },
            { value: '05gsm', label: '05GSM' },
            { value: 'greenspark', label: 'GreenSpark' },
            { value: 'liberti', label: 'Liberti' },
            { value: 'moba', label: 'Moba' },
            { value: 'taggsm', label: 'TagGSM' },
            { value: 'signal23', label: 'Signal23' },
            { value: 'memstech', label: 'Memstech' },
          ]}
        />
      </Space>
      <DataTable
        columns={columns}
        data={data}
        loading={isLoading}
        rowKey="id"
        onRow={(record) => ({ onClick: () => setSelected(record) })}
      />
      <ModerationModal
        item={selected}
        open={!!selected}
        onClose={() => setSelected(null)}
      />
    </>
  )
}
