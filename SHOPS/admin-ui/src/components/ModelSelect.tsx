import { useState } from 'react'
import { Select } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { getModels } from '../api/client'

interface Props {
  brandId?: number
  value?: number[]
  onChange?: (values: number[]) => void
}

export default function ModelSelect({ brandId, value, onChange }: Props) {
  const [search, setSearch] = useState('')

  const { data: models = [] } = useQuery({
    queryKey: ['models', brandId, search],
    queryFn: () => getModels(brandId, search || undefined),
    enabled: !!brandId,
  })

  return (
    <Select
      mode="multiple"
      showSearch
      value={value}
      placeholder={brandId ? 'Select models' : 'Select brand first'}
      disabled={!brandId}
      filterOption={false}
      onSearch={setSearch}
      onChange={(vals) => onChange?.(vals)}
      options={models.map((m) => ({ value: m.id, label: m.name }))}
      style={{ width: '100%' }}
      allowClear
    />
  )
}
