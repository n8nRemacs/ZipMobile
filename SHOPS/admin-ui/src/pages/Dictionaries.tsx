import { useState } from 'react'
import { Tabs, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { getBrands, getModels, getPartTypes, getColors } from '../api/client'
import DataTable from '../components/DataTable'

const { Title } = Typography

export default function DictionariesPage() {
  const [activeTab, setActiveTab] = useState('brands')

  const { data: brands = [], isLoading: brandsLoading } = useQuery({
    queryKey: ['brands'],
    queryFn: () => getBrands(),
    enabled: activeTab === 'brands',
  })

  const { data: models = [], isLoading: modelsLoading } = useQuery({
    queryKey: ['models-all'],
    queryFn: () => getModels(),
    enabled: activeTab === 'models',
  })

  const { data: partTypes = [], isLoading: ptLoading } = useQuery({
    queryKey: ['part-types'],
    queryFn: getPartTypes,
    enabled: activeTab === 'part_types',
  })

  const { data: colors = [], isLoading: colorsLoading } = useQuery({
    queryKey: ['colors'],
    queryFn: getColors,
    enabled: activeTab === 'colors',
  })

  return (
    <>
      <Title level={3}>Dictionaries</Title>
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
        {
          key: 'brands',
          label: `Brands (${brands.length})`,
          children: (
            <DataTable
              columns={[
                { title: 'ID', dataIndex: 'id', width: 80 },
                { title: 'Name', dataIndex: 'name' },
              ]}
              data={brands}
              loading={brandsLoading}
              rowKey="id"
            />
          ),
        },
        {
          key: 'models',
          label: `Models (${models.length})`,
          children: (
            <DataTable
              columns={[
                { title: 'ID', dataIndex: 'id', width: 80 },
                { title: 'Name', dataIndex: 'name' },
                { title: 'Brand ID', dataIndex: 'brand_id', width: 100 },
              ]}
              data={models}
              loading={modelsLoading}
              rowKey="id"
            />
          ),
        },
        {
          key: 'part_types',
          label: `Part Types (${partTypes.length})`,
          children: (
            <DataTable
              columns={[
                { title: 'ID', dataIndex: 'id', width: 80 },
                { title: 'Name', dataIndex: 'name' },
              ]}
              data={partTypes}
              loading={ptLoading}
              rowKey="id"
            />
          ),
        },
        {
          key: 'colors',
          label: `Colors (${colors.length})`,
          children: (
            <DataTable
              columns={[
                { title: 'ID', dataIndex: 'id', width: 80 },
                { title: 'Name', dataIndex: 'name' },
              ]}
              data={colors}
              loading={colorsLoading}
              rowKey="id"
            />
          ),
        },
      ]} />
    </>
  )
}
