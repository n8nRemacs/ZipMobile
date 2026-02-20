import { useState } from 'react'
import { Modal, Typography, Space, Button, Input, Divider, Alert } from 'antd'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { ModerationItem } from '../types'
import { resolveModeration } from '../api/client'
import BrandSelect from './BrandSelect'
import ModelSelect from './ModelSelect'
import StatusBadge from './StatusBadge'

const { Text, Title } = Typography

interface Props {
  item: ModerationItem | null
  open: boolean
  onClose: () => void
}

export default function ModerationModal({ item, open, onClose }: Props) {
  const queryClient = useQueryClient()
  const [existingId, setExistingId] = useState<number | undefined>()
  const [createNew, setCreateNew] = useState(false)
  const [newName, setNewName] = useState('')
  const [brandIdForModel, setBrandIdForModel] = useState<number | undefined>()

  const mutation = useMutation({
    mutationFn: (data: { id: number; existing_id?: number; create_new?: boolean; new_name?: string; new_data?: Record<string, unknown> }) =>
      resolveModeration(data.id, {
        existing_id: data.existing_id,
        create_new: data.create_new,
        new_name: data.new_name,
        new_data: data.new_data,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['moderation'] })
      resetAndClose()
    },
  })

  function resetAndClose() {
    setExistingId(undefined)
    setCreateNew(false)
    setNewName('')
    setBrandIdForModel(undefined)
    onClose()
  }

  if (!item) return null

  function handleResolveExisting() {
    if (!item || !existingId) return
    mutation.mutate({ id: item.id, existing_id: existingId })
  }

  function handleCreateNew() {
    if (!item || !newName) return
    const newData: Record<string, unknown> = {}
    if (item.entity_type === 'model' && brandIdForModel) {
      newData.brand_id = brandIdForModel
    }
    mutation.mutate({ id: item.id, create_new: true, new_name: newName, new_data: newData })
  }

  return (
    <Modal
      title="Moderation"
      open={open}
      onCancel={resetAndClose}
      footer={null}
      width={640}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <div>
          <Text type="secondary">Source:</Text>
          <Title level={5} style={{ margin: '4px 0' }}>{item.source_name}</Title>
          <Text type="secondary">Article: {item.source_article} | Shop: {item.source_shop}</Text>
        </div>

        <Alert
          type="info"
          message={`AI proposes: ${item.proposed_name}`}
          description={
            <>
              <Text>Type: {item.entity_type} | Confidence: {item.ai_confidence?.toFixed(2) ?? 'N/A'}</Text>
              {item.ai_reasoning && <div><Text type="secondary">{item.ai_reasoning}</Text></div>}
            </>
          }
        />

        <StatusBadge status={item.status} />

        {item.status === 'pending' && (
          <>
            <Divider>Use existing</Divider>
            {item.entity_type === 'brand' && (
              <BrandSelect value={existingId} onChange={(val) => setExistingId(val)} />
            )}
            {item.entity_type === 'model' && (
              <>
                <BrandSelect onChange={(val) => setBrandIdForModel(val)} />
                <ModelSelect
                  brandId={brandIdForModel ?? (item.proposed_data?.brand_id as number)}
                  value={existingId ? [existingId] : []}
                  onChange={(vals) => setExistingId(vals[0])}
                />
              </>
            )}
            <Button type="primary" disabled={!existingId} onClick={handleResolveExisting} loading={mutation.isPending}>
              Use existing
            </Button>

            <Divider>Or create new</Divider>
            <Input
              placeholder={`New ${item.entity_type} name`}
              value={newName || item.proposed_name}
              onChange={(e) => { setNewName(e.target.value); setCreateNew(true) }}
            />
            {item.entity_type === 'model' && (
              <BrandSelect value={brandIdForModel} onChange={(val) => setBrandIdForModel(val)} />
            )}
            <Button type="default" disabled={!newName && !createNew} onClick={handleCreateNew} loading={mutation.isPending}>
              Create new
            </Button>
          </>
        )}
      </Space>
    </Modal>
  )
}
