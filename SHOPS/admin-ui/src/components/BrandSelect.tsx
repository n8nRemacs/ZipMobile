import { useState } from 'react'
import { Select } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { getBrands } from '../api/client'

interface Props {
  value?: number
  onChange?: (value: number, label: string) => void
}

export default function BrandSelect({ value, onChange }: Props) {
  const [search, setSearch] = useState('')

  const { data: brands = [] } = useQuery({
    queryKey: ['brands', search],
    queryFn: () => getBrands(search || undefined),
  })

  return (
    <Select
      showSearch
      value={value}
      placeholder="Select brand"
      filterOption={false}
      onSearch={setSearch}
      onChange={(val) => {
        const brand = brands.find((b) => b.id === val)
        if (brand && onChange) onChange(val, brand.name)
      }}
      options={brands.map((b) => ({ value: b.id, label: b.name }))}
      style={{ width: '100%' }}
      allowClear
    />
  )
}
