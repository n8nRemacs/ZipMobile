import { Table } from 'antd'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'

interface Props<T> {
  columns: ColumnsType<T>
  data: T[]
  loading?: boolean
  rowKey: string | ((record: T) => string | number)
  pagination?: TablePaginationConfig | false
  onRow?: (record: T) => { onClick?: () => void }
}

export default function DataTable<T extends object>({
  columns,
  data,
  loading,
  rowKey,
  pagination,
  onRow,
}: Props<T>) {
  return (
    <Table<T>
      columns={columns}
      dataSource={data}
      loading={loading}
      rowKey={rowKey}
      pagination={pagination ?? { pageSize: 20, showSizeChanger: true }}
      onRow={onRow}
      size="middle"
      scroll={{ x: 'max-content' }}
    />
  )
}
